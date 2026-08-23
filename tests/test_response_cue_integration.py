from __future__ import annotations

import pytest

from interview_copilot.cue_retrieval import CueEvidence, CueState, InterviewCue
from interview_copilot.grounded_composer import (
    CompositionStatus,
    ExtractiveGroundedScriptComposer,
    GroundedScriptComposerConfig,
)
from interview_copilot.knowledge.models import ExperienceStatus
from interview_copilot.response import ResponseMode
from interview_copilot.response_integration import (
    CueResponseAssemblerConfig,
    InterviewCueResponseAssembler,
    ResponseAssemblyContext,
)
from interview_copilot.response_policy import (
    ResponseCoordinator,
    StaleQueryGenerationError,
)


def evidence(
    chunk_id: str,
    status: ExperienceStatus,
    text: str,
    *,
    score: float = 0.9,
) -> CueEvidence:
    return CueEvidence(
        text=text,
        source_uri=f"memory://synthetic/{chunk_id}",
        title=f"Synthetic {chunk_id}",
        experience_status=status,
        collection="career",
        chunk_id=chunk_id,
        score=score,
        project="synthetic-project",
    )


def ready_cue(
    generation: int = 1,
    *,
    primary: CueEvidence | None = None,
    supporting: tuple[CueEvidence, ...] = (),
    bridge: CueEvidence | None = None,
    confidence: float = 0.9,
    question: str = "Tell me about a retrieval system you built.",
) -> InterviewCue:
    return InterviewCue(
        session_id="session-a",
        generation=generation,
        question=question,
        intent=question,
        state=CueState.READY,
        primary_story=primary,
        supporting_points=supporting,
        role_bridge=bridge,
        confidence=confidence,
    )


def assembler(*, max_script_claims: int = 2) -> InterviewCueResponseAssembler:
    return InterviewCueResponseAssembler(
        ResponseCoordinator(),
        ExtractiveGroundedScriptComposer(
            GroundedScriptComposerConfig(max_script_claims=max_script_claims)
        ),
    )


def test_generated_script_package_keeps_only_supporting_cues() -> None:
    primary = evidence(
        "implemented",
        ExperienceStatus.IMPLEMENTED,
        "I built a local retrieval index that returned source citations for engineers.",
    )
    support = evidence(
        "support",
        ExperienceStatus.IMPLEMENTED,
        "The index refreshed incrementally when source documents changed.",
    )
    bridge = evidence(
        "bridge",
        ExperienceStatus.DESIGN,
        "Add an explicit human approval gate before accepting a legal recommendation.",
    )

    result = assembler(max_script_claims=1).assemble(
        ready_cue(primary=primary, supporting=(support,), bridge=bridge)
    )

    assert result.package.mode is ResponseMode.GENERATED_SCRIPT
    assert result.composition_status is CompositionStatus.COMPOSED
    assert result.package.script is not None
    assert "local retrieval index" in result.package.script
    assert result.package.cues
    assert all(primary.chunk_id != cue.evidence[0].chunk_id for cue in result.package.cues)
    assert all(cue.text not in result.package.script for cue in result.package.cues)
    assert result.package.evidence[0].source_uri == primary.source_uri
    assert result.package.evidence[0].experience_status is ExperienceStatus.IMPLEMENTED


def test_cue_only_mode_remains_usable_without_teleprompter_script() -> None:
    primary = evidence(
        "implemented",
        ExperienceStatus.IMPLEMENTED,
        "I built a retrieval index with deterministic source citations.",
    )
    support = evidence(
        "design",
        ExperienceStatus.DESIGN,
        "Use an approval gate when confidence is below the acceptance threshold.",
    )

    result = assembler().assemble(
        ready_cue(primary=primary, supporting=(support,)),
        ResponseAssemblyContext(generated_script_enabled=False),
    )

    assert result.package.mode is ResponseMode.CUE_ONLY
    assert result.package.script is None
    assert len(result.package.cues) == 2
    assert result.package.cues[0].text.startswith("[implemented]")
    assert result.package.cues[1].text.startswith("[design]")
    assert result.package.cues[0].evidence[0].chunk_id == "implemented"


def test_cue_projection_is_bounded_and_glanceable() -> None:
    long_text = "Evidence " + "detail " * 80
    items = tuple(
        evidence(f"support-{index}", ExperienceStatus.IMPLEMENTED, long_text) for index in range(5)
    )
    integration = InterviewCueResponseAssembler(
        ResponseCoordinator(),
        ExtractiveGroundedScriptComposer(),
        CueResponseAssemblerConfig(max_cues=2, max_cue_chars=90),
    )

    result = integration.assemble(
        ready_cue(primary=items[0], supporting=items[1:]),
        ResponseAssemblyContext(generated_script_enabled=False),
    )

    assert result.package.mode is ResponseMode.CUE_ONLY
    assert len(result.package.cues) == 2
    assert all(len(cue.text) <= 90 for cue in result.package.cues)
    assert all(cue.text.endswith("…") for cue in result.package.cues)


def test_ambiguous_question_maps_to_clarification_without_script() -> None:
    primary = evidence(
        "implemented",
        ExperienceStatus.IMPLEMENTED,
        "I built an indexed retrieval service for source-code documentation.",
    )

    result = assembler().assemble(
        ready_cue(primary=primary),
        ResponseAssemblyContext(question_ambiguous=True),
    )

    assert result.package.mode is ResponseMode.CLARIFICATION
    assert result.package.script is None
    assert result.package.clarification is not None
    assert result.package.evidence[0].chunk_id == primary.chunk_id


@pytest.mark.parametrize(
    ("state", "detail"),
    [
        (CueState.NO_MATCH, "no sufficiently relevant evidence"),
        (CueState.UNAVAILABLE, "retrieval unavailable (RuntimeError)"),
    ],
)
def test_terminal_retrieval_states_become_unavailable_packages(
    state: CueState,
    detail: str,
) -> None:
    cue = InterviewCue(
        session_id="session-a",
        generation=1,
        question="Tell me about legal automation.",
        intent="Tell me about legal automation.",
        state=state,
        detail=detail,
    )

    result = assembler().assemble(cue)

    assert result.package.mode is ResponseMode.UNAVAILABLE
    assert result.package.detail == detail
    assert result.package.script is None
    assert result.package.cues == ()


def test_composer_fallback_degrades_to_cue_only_when_safe_support_remains() -> None:
    unsafe_prototype = evidence(
        "prototype",
        ExperienceStatus.PROTOTYPE,
        "I deployed the prototype to production and launched it company-wide.",
    )
    design = evidence(
        "design",
        ExperienceStatus.DESIGN,
        "Add an explicit reviewer approval gate before the recommendation is accepted.",
    )

    result = assembler().assemble(
        ready_cue(primary=unsafe_prototype, bridge=design, confidence=0.95)
    )

    assert result.decision.mode is ResponseMode.GENERATED_SCRIPT
    assert result.composition_status is CompositionStatus.FALLBACK_REQUIRED
    assert result.package.mode is ResponseMode.CUE_ONLY
    assert result.package.script is None
    assert len(result.package.cues) == 1
    assert result.package.cues[0].text.startswith("[design]")
    assert result.package.cues[0].evidence[0].chunk_id == design.chunk_id


def test_stale_retrieval_result_cannot_replace_newer_response_guidance() -> None:
    integration = assembler()
    newer = evidence(
        "newer",
        ExperienceStatus.IMPLEMENTED,
        "I built the newer retrieval workflow with source citations.",
    )
    older = evidence(
        "older",
        ExperienceStatus.IMPLEMENTED,
        "I built the older retrieval workflow with source citations.",
    )

    latest = integration.assemble(ready_cue(2, primary=newer))
    assert latest.package.query_generation == 2

    with pytest.raises(StaleQueryGenerationError):
        integration.assemble(ready_cue(1, primary=older))


def test_ready_cue_without_evidence_is_rejected_before_policy() -> None:
    with pytest.raises(ValueError, match="must carry retrieved evidence"):
        assembler().assemble(ready_cue())


def test_duplicate_evidence_references_are_deduplicated_without_losing_provenance() -> None:
    primary = evidence(
        "same",
        ExperienceStatus.IMPLEMENTED,
        "I built a retrieval workflow with citations.",
    )

    result = assembler().assemble(
        ready_cue(primary=primary, supporting=(primary,)),
        ResponseAssemblyContext(generated_script_enabled=False),
    )

    assert result.package.mode is ResponseMode.CUE_ONLY
    assert len(result.package.evidence) == 1
    assert len(result.package.cues) == 1
    assert result.package.evidence[0].source_uri == primary.source_uri
