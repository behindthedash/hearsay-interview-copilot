from __future__ import annotations

from pathlib import Path

import pytest

from interview_copilot.knowledge.models import ExperienceStatus
from interview_copilot.response import (
    EvidenceReference,
    ResponseEligibility,
    ResponseMode,
    ResponsePackage,
)
from interview_copilot.teleprompter_content import (
    PreparedContentStore,
    TeleprompterContentError,
    TeleprompterContentLoader,
    TeleprompterContentSession,
    TeleprompterFormat,
    TeleprompterOrigin,
    generated_document_from_response,
    normalize_match_text,
)


def evidence(chunk_id: str = "retrieval") -> EvidenceReference:
    return EvidenceReference(
        source_uri=f"memory://synthetic/{chunk_id}",
        collection="career",
        chunk_id=chunk_id,
        experience_status=ExperienceStatus.IMPLEMENTED,
        title=f"Synthetic {chunk_id}",
        project="synthetic-project",
    )


def generated_package(
    generation: int = 3,
    *,
    script: str = "I built a retrieval index. It returned source citations.",
) -> ResponsePackage:
    return ResponsePackage(
        session_id="session-a",
        query_generation=generation,
        mode=ResponseMode.GENERATED_SCRIPT,
        eligibility=ResponseEligibility(
            retrieval_confidence=0.91,
            script_eligible=True,
        ),
        evidence=(evidence(),),
        script=script,
    )


class RecordingStore:
    def __init__(self) -> None:
        self.saved = []

    def save(self, document) -> None:
        self.saved.append(document)


def test_prepared_markdown_normalizes_into_ordered_stable_sections() -> None:
    loader = TeleprompterContentLoader()
    text = """
# Introduction
I build data systems people can trust.

## Example
I used **retrieval** with source citations.
"""

    first = loader.load_prepared(
        text,
        source_uri="file:///scripts/interview.md",
        content_format=TeleprompterFormat.MARKDOWN,
    )
    second = loader.load_prepared(
        text,
        source_uri="file:///scripts/interview.md",
        content_format=TeleprompterFormat.MARKDOWN,
    )

    assert first.origin is TeleprompterOrigin.PREPARED
    assert first.document_id == second.document_id
    assert len(first.sections) == 2
    assert [section.ordinal for section in first.sections] == [0, 1]
    assert [section.section_id for section in first.sections] == [
        section.section_id for section in second.sections
    ]
    assert first.sections[0].title == "Introduction"
    assert first.sections[0].display_text == "I build data systems people can trust."
    assert first.sections[1].title == "Example"
    assert first.sections[1].display_text == "I used **retrieval** with source citations."
    assert first.sections[1].match_text == "i used retrieval with source citations"
    assert all(section.source_uri == first.source_uri for section in first.sections)


def test_plain_text_produces_one_section_and_keeps_display_separate_from_match_text() -> None:
    document = TeleprompterContentLoader().load_prepared(
        "  Hello, WORLD!\nThis_is a test.  ",
        source_uri="memory://prepared/intro",
    )

    assert len(document.sections) == 1
    section = document.sections[0]
    assert section.display_text == "Hello, WORLD!\nThis_is a test."
    assert section.match_text == "hello world this is a test"
    assert normalize_match_text("Résumé — DATA_factory") == "résumé data factory"


def test_changed_prepared_section_changes_identity_but_unchanged_reload_does_not() -> None:
    loader = TeleprompterContentLoader()
    original = loader.load_prepared("Same answer.", source_uri="memory://prepared/answer")
    unchanged = loader.load_prepared("Same answer.", source_uri="memory://prepared/answer")
    changed = loader.load_prepared("Changed answer.", source_uri="memory://prepared/answer")

    assert original.sections[0].section_id == unchanged.sections[0].section_id
    assert original.document_id == unchanged.document_id
    assert original.sections[0].section_id != changed.sections[0].section_id
    assert original.document_id != changed.document_id


@pytest.mark.parametrize(
    "text",
    ["", "   \n\t", "# Heading\n---"],
)
def test_empty_or_non_speech_content_fails_clearly(text: str) -> None:
    loader = TeleprompterContentLoader()
    content_format = (
        TeleprompterFormat.MARKDOWN if text.startswith("#") else TeleprompterFormat.TEXT
    )

    if text.startswith("#"):
        document = loader.load_prepared(
            text,
            source_uri="memory://prepared/empty",
            content_format=content_format,
        )
        assert document.sections[0].display_text == "---"
    else:
        with pytest.raises(TeleprompterContentError, match="no usable text"):
            loader.load_prepared(
                text,
                source_uri="memory://prepared/empty",
                content_format=content_format,
            )


def test_path_loader_supports_markdown_and_text_without_rewriting_source(tmp_path: Path) -> None:
    markdown = tmp_path / "answer.md"
    markdown.write_text("# Answer\nPrepared response.", encoding="utf-8")
    plain = tmp_path / "intro.txt"
    plain.write_text("Prepared introduction.", encoding="utf-8")
    before_markdown = markdown.read_text(encoding="utf-8")
    before_plain = plain.read_text(encoding="utf-8")

    loader = TeleprompterContentLoader()
    markdown_document = loader.load_path(markdown)
    plain_document = loader.load_path(plain)

    assert markdown_document.sections[0].title == "Answer"
    assert plain_document.sections[0].display_text == "Prepared introduction."
    assert markdown.read_text(encoding="utf-8") == before_markdown
    assert plain.read_text(encoding="utf-8") == before_plain

    unsupported = tmp_path / "answer.docx"
    unsupported.write_text("not really a docx", encoding="utf-8")
    with pytest.raises(TeleprompterContentError, match="unsupported"):
        loader.load_path(unsupported)


def test_generated_response_uses_same_section_model_and_retains_provenance() -> None:
    package = generated_package()

    document = generated_document_from_response(package)

    assert document.origin is TeleprompterOrigin.GENERATED
    assert document.ephemeral is True
    assert document.response_session_id == package.session_id
    assert document.query_generation == package.query_generation
    assert document.evidence == package.evidence
    assert document.source_uri == "response://session-a/3"
    assert len(document.sections) == 1
    assert document.sections[0].display_text == package.script
    assert document.sections[0].match_text.startswith("i built a retrieval index")


def test_generated_conversion_rejects_non_script_response_mode() -> None:
    package = ResponsePackage(
        session_id="session-a",
        query_generation=1,
        mode=ResponseMode.CUE_ONLY,
        eligibility=ResponseEligibility(
            retrieval_confidence=0.7,
            script_eligible=False,
        ),
        evidence=(evidence(),),
        cues=(),
    )

    with pytest.raises(ValueError, match="cue-only response requires"):
        _ = package


def test_generated_projection_is_stable_and_reuses_unchanged_document_instance() -> None:
    session = TeleprompterContentSession()
    package = generated_package()

    first = session.document_for_response(package)
    second = session.document_for_response(package)
    deterministic_copy = generated_document_from_response(package)

    assert first is second
    assert first.document_id == deterministic_copy.document_id
    assert first.sections[0].section_id == deterministic_copy.sections[0].section_id


def test_generated_content_is_not_persisted_without_explicit_save() -> None:
    session = TeleprompterContentSession()
    store: PreparedContentStore = RecordingStore()
    generated = session.document_for_response(generated_package())

    assert generated.ephemeral is True
    assert isinstance(store, RecordingStore)
    assert store.saved == []


def test_explicit_save_creates_prepared_copy_without_transient_response_provenance() -> None:
    session = TeleprompterContentSession()
    store = RecordingStore()
    generated = session.document_for_response(generated_package())

    prepared = session.save_generated(
        session_id="session-a",
        query_generation=3,
        source_uri="memory://prepared/saved-answer",
        store=store,
    )

    assert len(store.saved) == 1
    assert store.saved[0] is prepared
    assert prepared.origin is TeleprompterOrigin.PREPARED
    assert prepared.ephemeral is False
    assert prepared.display_text == generated.display_text
    assert prepared.response_session_id is None
    assert prepared.query_generation is None
    assert prepared.evidence == ()
    assert generated.evidence


def test_teardown_clears_generated_documents_and_transient_provenance_but_saved_copy_survives() -> None:
    session = TeleprompterContentSession()
    store = RecordingStore()
    session.document_for_response(generated_package())
    saved = session.save_generated(
        session_id="session-a",
        query_generation=3,
        source_uri="memory://prepared/saved-answer",
        store=store,
    )

    session.teardown()

    assert session.generated_documents == ()
    assert store.saved == [saved]
    assert saved.evidence == ()


def test_save_requires_generated_document_to_exist_in_current_session() -> None:
    session = TeleprompterContentSession()

    with pytest.raises(KeyError, match="not available"):
        session.save_generated(
            session_id="session-a",
            query_generation=99,
            source_uri="memory://prepared/missing",
            store=RecordingStore(),
        )
