from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any, ClassVar

from .knowledge.models import ExperienceStatus


class ResponseMode(StrEnum):
    GENERATED_SCRIPT = "generated-script"
    CUE_ONLY = "cue-only"
    CLARIFICATION = "clarification"
    UNAVAILABLE = "unavailable"


class ResponseLifecycle(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    DISMISSED = "dismissed"
    SUPERSEDED = "superseded"


@dataclass(frozen=True)
class EvidenceReference:
    source_uri: str
    collection: str
    chunk_id: str
    experience_status: ExperienceStatus
    title: str | None = None
    project: str | None = None

    def __post_init__(self) -> None:
        if not self.source_uri.strip():
            raise ValueError("source_uri must be non-empty")
        if not self.collection.strip():
            raise ValueError("collection must be non-empty")
        if not self.chunk_id.strip():
            raise ValueError("chunk_id must be non-empty")

    @property
    def key(self) -> tuple[str, str]:
        return (self.collection, self.chunk_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_uri": self.source_uri,
            "collection": self.collection,
            "chunk_id": self.chunk_id,
            "experience_status": self.experience_status.value,
            "title": self.title,
            "project": self.project,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> EvidenceReference:
        return cls(
            source_uri=str(payload["source_uri"]),
            collection=str(payload["collection"]),
            chunk_id=str(payload["chunk_id"]),
            experience_status=ExperienceStatus(str(payload["experience_status"])),
            title=_optional_text(payload.get("title")),
            project=_optional_text(payload.get("project")),
        )


@dataclass(frozen=True)
class ResponseCue:
    text: str
    evidence: tuple[EvidenceReference, ...] = ()

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("cue text must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "evidence": [item.to_dict() for item in self.evidence],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ResponseCue:
        return cls(
            text=str(payload["text"]),
            evidence=tuple(
                EvidenceReference.from_dict(item) for item in payload.get("evidence", [])
            ),
        )


@dataclass(frozen=True)
class ResponseEligibility:
    retrieval_confidence: float
    script_eligible: bool
    evidence_conflict: bool = False
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not 0.0 <= self.retrieval_confidence <= 1.0:
            raise ValueError("retrieval_confidence must be between 0 and 1")
        if any(not reason.strip() for reason in self.reasons):
            raise ValueError("eligibility reasons must be non-empty when provided")

    def to_dict(self) -> dict[str, Any]:
        return {
            "retrieval_confidence": self.retrieval_confidence,
            "script_eligible": self.script_eligible,
            "evidence_conflict": self.evidence_conflict,
            "reasons": list(self.reasons),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ResponseEligibility:
        return cls(
            retrieval_confidence=float(payload["retrieval_confidence"]),
            script_eligible=bool(payload["script_eligible"]),
            evidence_conflict=bool(payload.get("evidence_conflict", False)),
            reasons=tuple(str(reason) for reason in payload.get("reasons", [])),
        )


@dataclass(frozen=True)
class ResponsePackage:
    MAX_CUES: ClassVar[int] = 3

    session_id: str
    query_generation: int
    mode: ResponseMode
    eligibility: ResponseEligibility
    lifecycle: ResponseLifecycle = ResponseLifecycle.PENDING
    evidence: tuple[EvidenceReference, ...] = ()
    script: str | None = None
    cues: tuple[ResponseCue, ...] = ()
    clarification: str | None = None
    detail: str | None = None

    def __post_init__(self) -> None:
        if not self.session_id.strip():
            raise ValueError("session_id must be non-empty")
        if self.query_generation <= 0:
            raise ValueError("query_generation must be positive")
        if len(self.cues) > self.MAX_CUES:
            raise ValueError(f"response package may contain at most {self.MAX_CUES} cues")

        evidence_keys = [item.key for item in self.evidence]
        if len(evidence_keys) != len(set(evidence_keys)):
            raise ValueError("response package evidence references must be unique")

        package_keys = set(evidence_keys)
        for cue in self.cues:
            missing = [item.key for item in cue.evidence if item.key not in package_keys]
            if missing:
                raise ValueError("cue evidence must also be present in package evidence")

        script = _optional_text(self.script)
        clarification = _optional_text(self.clarification)
        detail = _optional_text(self.detail)

        if self.mode is ResponseMode.GENERATED_SCRIPT:
            if script is None:
                raise ValueError("generated-script response requires script text")
            if not self.evidence:
                raise ValueError("generated-script response requires evidence")
            if not self.eligibility.script_eligible:
                raise ValueError("generated-script response requires script eligibility")
        elif script is not None:
            raise ValueError("only generated-script responses may carry script text")

        if self.mode is ResponseMode.CUE_ONLY and not self.cues:
            raise ValueError("cue-only response requires at least one usable cue")

        if self.mode is ResponseMode.CLARIFICATION:
            if clarification is None:
                raise ValueError("clarification response requires clarification text")
        elif clarification is not None:
            raise ValueError("only clarification responses may carry clarification text")

        if self.mode is ResponseMode.UNAVAILABLE and detail is None:
            raise ValueError("unavailable response requires a detail message")

    @property
    def experience_statuses(self) -> tuple[ExperienceStatus, ...]:
        return tuple(dict.fromkeys(item.experience_status for item in self.evidence))

    def with_lifecycle(self, lifecycle: ResponseLifecycle) -> ResponsePackage:
        return replace(self, lifecycle=lifecycle)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "query_generation": self.query_generation,
            "mode": self.mode.value,
            "eligibility": self.eligibility.to_dict(),
            "lifecycle": self.lifecycle.value,
            "evidence": [item.to_dict() for item in self.evidence],
            "script": self.script,
            "cues": [cue.to_dict() for cue in self.cues],
            "clarification": self.clarification,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ResponsePackage:
        return cls(
            session_id=str(payload["session_id"]),
            query_generation=int(payload["query_generation"]),
            mode=ResponseMode(str(payload["mode"])),
            eligibility=ResponseEligibility.from_dict(dict(payload["eligibility"])),
            lifecycle=ResponseLifecycle(str(payload.get("lifecycle", ResponseLifecycle.PENDING))),
            evidence=tuple(
                EvidenceReference.from_dict(item) for item in payload.get("evidence", [])
            ),
            script=_optional_text(payload.get("script")),
            cues=tuple(ResponseCue.from_dict(item) for item in payload.get("cues", [])),
            clarification=_optional_text(payload.get("clarification")),
            detail=_optional_text(payload.get("detail")),
        )


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text.strip() else None
