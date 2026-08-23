from __future__ import annotations

from dataclasses import replace

import pytest

from interview_copilot.alignment import (
    AlignmentConfig,
    AlignmentTransition,
    LocalSpeechAligner,
)
from interview_copilot.knowledge.models import ExperienceStatus
from interview_copilot.local_speech import LocalSpeechSignal
from interview_copilot.response import EvidenceReference
from interview_copilot.teleprompter_content import (
    TeleprompterContentLoader,
    TeleprompterDocument,
    TeleprompterFormat,
    TeleprompterOrigin,
    TeleprompterSection,
)

SCRIPT = """# Source mapping
I started by mapping the source system and identifying the business rules that mattered.

# Retrieval
Then I built a small retrieval layer that indexed source code and returned grounded excerpts.

# Tool boundary
The MCP server exposed that retrieval capability as a tool the development workflow could call.

# Grounding
Finally I added citations and explicit limits so answers stayed grounded in the available evidence.

# Human gates
For a legal workflow I would keep human approval gates around high risk decisions.
"""

SECTION_SPEECH = (
    "I started by mapping the source system and identifying the business rules that mattered",
    "Then I built a small retrieval layer that indexed source code and returned grounded excerpts",
    "The MCP server exposed that retrieval capability as a tool the development workflow could call",
    "Finally I added citations and explicit limits so answers stayed grounded in the available evidence",
    "For a legal workflow I would keep human approval gates around high risk decisions",
)


def prepared_document() -> TeleprompterDocument:
    return TeleprompterContentLoader().load_prepared(
        SCRIPT,
        source_uri="file:///synthetic/interview.md",
        content_format=TeleprompterFormat.MARKDOWN,
    )


def generated_document() -> TeleprompterDocument:
    prepared = prepared_document()
    source_uri = "response://synthetic-session/1"
    sections = tuple(
        TeleprompterSection(
            section_id=f"generated-{section.ordinal}",
            ordinal=section.ordinal,
            source_uri=source_uri,
            display_text=section.display_text,
            match_text=section.match_text,
            title=section.title,
        )
        for section in prepared.sections
    )
    evidence = EvidenceReference(
        source_uri="memory://synthetic",
        collection="synthetic",
        chunk_id="chunk-1",
        experience_status=ExperienceStatus.IMPLEMENTED,
    )
    return TeleprompterDocument(
        document_id="generated-synthetic-document",
        origin=TeleprompterOrigin.GENERATED,
        source_uri=source_uri,
        sections=sections,
        response_session_id="synthetic-session",
        query_generation=1,
        evidence=(evidence,),
    )


@pytest.fixture(params=[prepared_document, generated_document], ids=["prepared", "generated"])
def document(request: pytest.FixtureRequest) -> TeleprompterDocument:
    factory = request.param
    return factory()


def signal(text: str, sequence: int = 1) -> LocalSpeechSignal:
    return LocalSpeechSignal(
        provider_name="synthetic-local",
        session_id="interview-session",
        sequence=sequence,
        text=text,
        received_at=float(sequence),
        final=True,
    )


def test_same_alignment_contract_runs_for_prepared_and_generated_documents(
    document: TeleprompterDocument,
) -> None:
    aligner = LocalSpeechAligner()
    state = aligner.activate(document)

    assert state.section_index == 0
    assert state.document_id == document.document_id

    state = aligner.process(signal(SECTION_SPEECH[1]))

    assert state.section_index == 1
    assert state.transition is AlignmentTransition.ALIGNED
    assert state.confidence >= aligner.config.accept_threshold


def test_pause_and_weak_speech_hold_position(document: TeleprompterDocument) -> None:
    aligner = LocalSpeechAligner()
    aligner.activate(document)
    paused = aligner.pause()

    state = aligner.process(signal(SECTION_SPEECH[2]))

    assert paused.automatic_paused
    assert state.section_index == 0
    assert state.transition is AlignmentTransition.HELD
    assert state.detail == "manual-pause"

    aligner.resume()
    weak = aligner.process(signal("weather coffee calendar purple"))
    assert weak.section_index == 0
    assert weak.transition is AlignmentTransition.HELD


def test_natural_paraphrase_advances_without_verbatim_delivery(
    document: TeleprompterDocument,
) -> None:
    aligner = LocalSpeechAligner()
    aligner.activate(document)

    state = aligner.process(
        signal(
            "Then I built the retrieval layer by indexing source code and returning grounded excerpts"
        )
    )

    assert state.section_index == 1
    assert state.transition is AlignmentTransition.ALIGNED


def test_repetition_of_current_material_does_not_run_away_forward(
    document: TeleprompterDocument,
) -> None:
    aligner = LocalSpeechAligner()
    aligner.activate(document)

    first = aligner.process(signal(SECTION_SPEECH[0], 1))
    repeated = aligner.process(signal(SECTION_SPEECH[0], 2))
    repeated_again = aligner.process(signal(SECTION_SPEECH[0], 3))

    assert first.section_index == 0
    assert repeated.section_index == 0
    assert repeated_again.section_index == 0
    assert repeated_again.transition is AlignmentTransition.HELD


def test_sustained_skip_ahead_evidence_recovers_to_later_section(
    document: TeleprompterDocument,
) -> None:
    aligner = LocalSpeechAligner()
    aligner.activate(document)

    first = aligner.process(signal(SECTION_SPEECH[3], 1))
    second = aligner.process(signal(SECTION_SPEECH[3], 2))
    third = aligner.process(signal(SECTION_SPEECH[3], 3))

    assert first.section_index == 0
    assert second.section_index == 0
    assert second.detail == "recovery-pending"
    assert third.section_index == 3
    assert third.transition is AlignmentTransition.RECOVERED
    assert third.detail == "skip-ahead-recovery"


def test_off_script_speech_waits_then_rejoins_nearby(document: TeleprompterDocument) -> None:
    aligner = LocalSpeechAligner()
    aligner.activate(document)

    aligner.process(signal("unrelated words about lunch and traffic", 1))
    waiting = aligner.process(signal("still discussing something completely unrelated", 2))
    rejoined = aligner.process(signal(SECTION_SPEECH[1], 3))

    assert waiting.section_index == 0
    assert waiting.transition is AlignmentTransition.HELD
    assert rejoined.section_index == 1
    assert rejoined.transition is AlignmentTransition.ALIGNED


def test_sustained_backward_restart_can_recover(document: TeleprompterDocument) -> None:
    aligner = LocalSpeechAligner()
    aligner.activate(document, section_index=3)

    first = aligner.process(signal(SECTION_SPEECH[0], 1))
    second = aligner.process(signal(SECTION_SPEECH[0], 2))
    third = aligner.process(signal(SECTION_SPEECH[0], 3))

    assert first.section_index == 3
    assert second.section_index == 3
    assert second.detail == "recovery-pending"
    assert third.section_index == 0
    assert third.transition is AlignmentTransition.RECOVERED
    assert third.detail == "backward-recovery"


def test_manual_navigation_is_authoritative_and_reanchors_matching(
    document: TeleprompterDocument,
) -> None:
    aligner = LocalSpeechAligner()
    aligner.activate(document)
    aligner.process(signal(SECTION_SPEECH[0], 1))

    jumped = aligner.jump(3)
    stale = aligner.process(signal(SECTION_SPEECH[0], 2))
    previous = aligner.previous()
    next_state = aligner.next()

    assert jumped.section_index == 3
    assert jumped.transition is AlignmentTransition.MANUAL
    assert stale.section_index == 3
    assert previous.section_index == 2
    assert previous.transition is AlignmentTransition.MANUAL
    assert next_state.section_index == 3
    assert next_state.transition is AlignmentTransition.MANUAL


def test_manual_pause_remains_authoritative_after_navigation(
    document: TeleprompterDocument,
) -> None:
    aligner = LocalSpeechAligner()
    aligner.activate(document)
    aligner.pause()
    moved = aligner.jump(2)
    held = aligner.process(signal(SECTION_SPEECH[3]))

    assert moved.section_index == 2
    assert moved.automatic_paused
    assert held.section_index == 2
    assert held.detail == "manual-pause"


def test_remote_event_shape_is_structurally_ineligible(document: TeleprompterDocument) -> None:
    class RemoteTranscriptEvent:
        source = "Remote"
        text = SECTION_SPEECH[1]

    aligner = LocalSpeechAligner()
    before = aligner.activate(document)

    with pytest.raises(TypeError, match="LocalSpeechSignal"):
        aligner.process(RemoteTranscriptEvent())  # type: ignore[arg-type]

    assert aligner.state == before


def test_overlapping_finalized_chunks_do_not_duplicate_into_false_movement(
    document: TeleprompterDocument,
) -> None:
    aligner = LocalSpeechAligner()
    aligner.activate(document)

    aligner.process(signal("I started by mapping the source system", 1))
    state = aligner.process(
        signal("the source system and identifying the business rules that mattered", 2)
    )

    assert state.section_index == 0
    assert state.confidence >= aligner.config.accept_threshold


def test_recovery_requires_sustained_evidence(document: TeleprompterDocument) -> None:
    config = replace(AlignmentConfig(), recovery_confirmations=2)
    aligner = LocalSpeechAligner(config)
    aligner.activate(document)

    aligner.process(signal(SECTION_SPEECH[3], 1))
    pending = aligner.process(signal(SECTION_SPEECH[3], 2))
    diverted = aligner.process(signal("unrelated material interrupts the attempted recovery", 3))

    assert pending.detail == "recovery-pending"
    assert diverted.section_index == 0
    assert diverted.transition is AlignmentTransition.HELD


def test_clear_removes_document_and_alignment_state(document: TeleprompterDocument) -> None:
    aligner = LocalSpeechAligner()
    aligner.activate(document)
    aligner.process(signal(SECTION_SPEECH[0]))

    aligner.clear()

    assert aligner.document is None
    assert aligner.state is None
    with pytest.raises(RuntimeError, match="no active teleprompter document"):
        aligner.process(signal(SECTION_SPEECH[0]))


def test_invalid_manual_jump_is_rejected(document: TeleprompterDocument) -> None:
    aligner = LocalSpeechAligner()
    aligner.activate(document)

    with pytest.raises(IndexError):
        aligner.jump(len(document.sections))
