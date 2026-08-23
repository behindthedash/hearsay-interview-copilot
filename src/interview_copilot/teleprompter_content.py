from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from .response import EvidenceReference, ResponseMode, ResponsePackage

_MARKDOWN_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
_MATCH_SEPARATORS = re.compile(r"[\W_]+", re.UNICODE)
_SUPPORTED_MARKDOWN_SUFFIXES = frozenset({".md", ".markdown"})
_SUPPORTED_TEXT_SUFFIXES = frozenset({".txt"})


class TeleprompterOrigin(StrEnum):
    PREPARED = "prepared"
    GENERATED = "generated"


class TeleprompterFormat(StrEnum):
    MARKDOWN = "markdown"
    TEXT = "text"


class TeleprompterContentError(ValueError):
    """Raised when source material cannot produce usable teleprompter content."""


@dataclass(frozen=True)
class TeleprompterSection:
    section_id: str
    ordinal: int
    source_uri: str
    display_text: str
    match_text: str
    title: str | None = None

    def __post_init__(self) -> None:
        if not self.section_id.strip():
            raise ValueError("section_id must be non-empty")
        if self.ordinal < 0:
            raise ValueError("section ordinal must be non-negative")
        if not self.source_uri.strip():
            raise ValueError("section source_uri must be non-empty")
        if not self.display_text.strip():
            raise ValueError("section display_text must be non-empty")
        if not self.match_text.strip():
            raise ValueError("section match_text must be non-empty")


@dataclass(frozen=True)
class TeleprompterDocument:
    document_id: str
    origin: TeleprompterOrigin
    source_uri: str
    sections: tuple[TeleprompterSection, ...]
    response_session_id: str | None = None
    query_generation: int | None = None
    evidence: tuple[EvidenceReference, ...] = ()

    def __post_init__(self) -> None:
        if not self.document_id.strip():
            raise ValueError("document_id must be non-empty")
        if not self.source_uri.strip():
            raise ValueError("document source_uri must be non-empty")
        if not self.sections:
            raise ValueError("teleprompter document must contain at least one section")

        expected_ordinals = tuple(range(len(self.sections)))
        ordinals = tuple(section.ordinal for section in self.sections)
        if ordinals != expected_ordinals:
            raise ValueError("teleprompter section ordinals must be contiguous and ordered")
        if any(section.source_uri != self.source_uri for section in self.sections):
            raise ValueError("all teleprompter sections must share document source provenance")

        if self.origin is TeleprompterOrigin.GENERATED:
            if self.response_session_id is None or not self.response_session_id.strip():
                raise ValueError("generated document requires response_session_id")
            if self.query_generation is None or self.query_generation <= 0:
                raise ValueError("generated document requires positive query_generation")
            if not self.evidence:
                raise ValueError("generated document requires provenance evidence")
        else:
            if self.response_session_id is not None:
                raise ValueError("prepared document must not carry response_session_id")
            if self.query_generation is not None:
                raise ValueError("prepared document must not carry query_generation")
            if self.evidence:
                raise ValueError("prepared document must not carry transient response evidence")

    @property
    def ephemeral(self) -> bool:
        return self.origin is TeleprompterOrigin.GENERATED

    @property
    def display_text(self) -> str:
        return "\n\n".join(section.display_text for section in self.sections)


class PreparedContentStore(Protocol):
    """Persistence boundary used only by an explicit user save action."""

    def save(self, document: TeleprompterDocument) -> None: ...


class TeleprompterContentLoader:
    """Normalize user-owned prepared content into stable ordered sections."""

    def load_path(self, path: str | Path) -> TeleprompterDocument:
        source = Path(path)
        suffix = source.suffix.casefold()
        if suffix in _SUPPORTED_MARKDOWN_SUFFIXES:
            content_format = TeleprompterFormat.MARKDOWN
        elif suffix in _SUPPORTED_TEXT_SUFFIXES:
            content_format = TeleprompterFormat.TEXT
        else:
            raise TeleprompterContentError(
                f"unsupported teleprompter content type: {source.suffix or '<none>'}"
            )
        return self.load_prepared(
            source.read_text(encoding="utf-8"),
            source_uri=source.resolve().as_uri(),
            content_format=content_format,
        )

    def load_prepared(
        self,
        text: str,
        *,
        source_uri: str,
        content_format: TeleprompterFormat = TeleprompterFormat.TEXT,
    ) -> TeleprompterDocument:
        if not source_uri.strip():
            raise ValueError("source_uri must be non-empty")
        raw_sections = (
            _markdown_sections(text)
            if content_format is TeleprompterFormat.MARKDOWN
            else ((None, _clean_display(text)),)
        )
        sections = _build_sections(source_uri, raw_sections)
        return TeleprompterDocument(
            document_id=_document_id(TeleprompterOrigin.PREPARED, source_uri, sections),
            origin=TeleprompterOrigin.PREPARED,
            source_uri=source_uri,
            sections=sections,
        )


def generated_document_from_response(package: ResponsePackage) -> TeleprompterDocument:
    """Convert a grounded generated-script response into teleprompter content."""

    if package.mode is not ResponseMode.GENERATED_SCRIPT:
        raise ValueError("only generated-script response packages can become generated content")
    if package.script is None:
        raise ValueError("generated-script response package is missing script text")

    source_uri = f"response://{package.session_id}/{package.query_generation}"
    sections = _build_sections(source_uri, ((None, _clean_display(package.script)),))
    return TeleprompterDocument(
        document_id=_document_id(TeleprompterOrigin.GENERATED, source_uri, sections),
        origin=TeleprompterOrigin.GENERATED,
        source_uri=source_uri,
        sections=sections,
        response_session_id=package.session_id,
        query_generation=package.query_generation,
        evidence=package.evidence,
    )


class TeleprompterContentSession:
    """Own transient generated documents for one application/interview session.

    Repeated projection of an unchanged response generation returns the same document
    instance. Generated content never crosses the persistence boundary unless
    ``save_generated`` is called explicitly.
    """

    def __init__(self, loader: TeleprompterContentLoader | None = None) -> None:
        self.loader = loader or TeleprompterContentLoader()
        self._generated: dict[tuple[str, int], TeleprompterDocument] = {}

    @property
    def generated_documents(self) -> tuple[TeleprompterDocument, ...]:
        return tuple(self._generated.values())

    def document_for_response(self, package: ResponsePackage) -> TeleprompterDocument:
        candidate = generated_document_from_response(package)
        key = (package.session_id, package.query_generation)
        existing = self._generated.get(key)
        if existing == candidate:
            return existing
        self._generated[key] = candidate
        return candidate

    def save_generated(
        self,
        *,
        session_id: str,
        query_generation: int,
        source_uri: str,
        store: PreparedContentStore,
    ) -> TeleprompterDocument:
        generated = self._generated.get((session_id, query_generation))
        if generated is None:
            raise KeyError("generated teleprompter document is not available")

        prepared = self.loader.load_prepared(
            generated.display_text,
            source_uri=source_uri,
            content_format=TeleprompterFormat.TEXT,
        )
        store.save(prepared)
        return prepared

    def teardown(self) -> None:
        self._generated.clear()


def normalize_match_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(_MATCH_SEPARATORS.sub(" ", normalized).split())


def _markdown_sections(text: str) -> tuple[tuple[str | None, str], ...]:
    sections: list[tuple[str | None, str]] = []
    current_title: str | None = None
    body: list[str] = []

    def flush() -> None:
        nonlocal body
        display = _clean_display("\n".join(body))
        if display or current_title:
            sections.append((current_title, display or current_title or ""))
        body = []

    for line in text.splitlines():
        match = _MARKDOWN_HEADING.match(line)
        if match:
            flush()
            current_title = _clean_display(match.group(2))
            continue
        body.append(line)
    flush()

    if not sections:
        return ((None, _clean_display(text)),)
    return tuple(sections)


def _build_sections(
    source_uri: str,
    raw_sections: tuple[tuple[str | None, str], ...],
) -> tuple[TeleprompterSection, ...]:
    sections: list[TeleprompterSection] = []
    for title, display in raw_sections:
        clean_display = _clean_display(display)
        match_text = normalize_match_text(clean_display)
        if not match_text:
            continue
        ordinal = len(sections)
        clean_title = _clean_display(title) if title else None
        sections.append(
            TeleprompterSection(
                section_id=_section_id(
                    source_uri,
                    ordinal,
                    clean_title,
                    match_text,
                ),
                ordinal=ordinal,
                source_uri=source_uri,
                title=clean_title,
                display_text=clean_display,
                match_text=match_text,
            )
        )

    if not sections:
        raise TeleprompterContentError("teleprompter content contains no usable text")
    return tuple(sections)


def _section_id(
    source_uri: str,
    ordinal: int,
    title: str | None,
    match_text: str,
) -> str:
    payload = "\x1f".join((source_uri, str(ordinal), title or "", match_text))
    return f"section-{_digest(payload)}"


def _document_id(
    origin: TeleprompterOrigin,
    source_uri: str,
    sections: tuple[TeleprompterSection, ...],
) -> str:
    payload = "\x1f".join((origin.value, source_uri, *(section.section_id for section in sections)))
    return f"document-{_digest(payload)}"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


def _clean_display(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines).strip()
