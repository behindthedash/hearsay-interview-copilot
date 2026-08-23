from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from .knowledge.models import ExperienceStatus
from .response import EvidenceReference, ResponseCue, ResponseMode
from .response_policy import ResponseDecision

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_+#.-]+")
_NON_PRODUCTION_ASSERTION = re.compile(
    r"\b(?:i|we)\s+(?:built|implemented|deployed|shipped|launched|delivered|operated|ran)\b",
    re.IGNORECASE,
)
_PRODUCTION_MARKER = re.compile(
    r"\b(?:production|prod|shipped|launched|deployed\s+to\s+production)\b",
    re.IGNORECASE,
)
_STATUS_PRIORITY = {
    ExperienceStatus.IMPLEMENTED: 4,
    ExperienceStatus.PROTOTYPE: 3,
    ExperienceStatus.DESIGN: 2,
    ExperienceStatus.HYPOTHETICAL: 1,
}


class CompositionStatus(StrEnum):
    COMPOSED = "composed"
    FALLBACK_REQUIRED = "fallback-required"


@dataclass(frozen=True)
class CompositionEvidence:
    """Selected evidence text paired with provenance approved by response policy."""

    reference: EvidenceReference
    text: str

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("composition evidence text must be non-empty")


@dataclass(frozen=True)
class ScriptCompositionRequest:
    """Bounded inputs for composing one generated interview response."""

    question: str
    intent: str
    decision: ResponseDecision
    evidence: tuple[CompositionEvidence, ...]

    def __post_init__(self) -> None:
        if not self.question.strip():
            raise ValueError("question must be non-empty")
        if not self.intent.strip():
            raise ValueError("intent must be non-empty")
        if self.decision.mode is not ResponseMode.GENERATED_SCRIPT:
            raise ValueError("script composition requires a generated-script decision")
        if not self.decision.eligibility.script_eligible:
            raise ValueError("script composition requires script-eligible policy state")
        if not self.evidence:
            raise ValueError("script composition requires selected evidence")

        request_keys = [item.reference.key for item in self.evidence]
        if len(request_keys) != len(set(request_keys)):
            raise ValueError("composition evidence references must be unique")

        decision_keys = {item.key for item in self.decision.evidence}
        if set(request_keys) != decision_keys:
            raise ValueError("composer evidence must exactly match the policy-selected evidence")


@dataclass(frozen=True)
class ScriptClaim:
    """One speech-ready claim and the evidence reference that supports it."""

    text: str
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("claim text must be non-empty")
        if not self.evidence:
            raise ValueError("claim must retain supporting evidence")


@dataclass(frozen=True)
class GroundedScriptComposition:
    """Composition output with explicit fallback and claim provenance."""

    session_id: str
    query_generation: int
    status: CompositionStatus
    evidence: tuple[EvidenceReference, ...]
    script: str | None = None
    claims: tuple[ScriptClaim, ...] = ()
    supporting_cues: tuple[ResponseCue, ...] = ()
    detail: str | None = None

    def __post_init__(self) -> None:
        if not self.session_id.strip():
            raise ValueError("session_id must be non-empty")
        if self.query_generation <= 0:
            raise ValueError("query_generation must be positive")

        evidence_keys = {item.key for item in self.evidence}
        for claim in self.claims:
            if any(item.key not in evidence_keys for item in claim.evidence):
                raise ValueError("claim evidence must belong to the selected evidence package")
        for cue in self.supporting_cues:
            if any(item.key not in evidence_keys for item in cue.evidence):
                raise ValueError("cue evidence must belong to the selected evidence package")

        if self.status is CompositionStatus.COMPOSED:
            if self.script is None or not self.script.strip():
                raise ValueError("composed result requires script text")
            if not self.claims:
                raise ValueError("composed result requires traceable claims")
        else:
            if self.script is not None:
                raise ValueError("fallback result must not carry script text")
            if self.claims:
                raise ValueError("fallback result must not carry generated claims")
            if self.detail is None or not self.detail.strip():
                raise ValueError("fallback result requires detail")


class GroundedScriptComposer(Protocol):
    def compose(self, request: ScriptCompositionRequest) -> GroundedScriptComposition: ...


@dataclass(frozen=True)
class GroundedScriptComposerConfig:
    max_script_claims: int = 2
    max_supporting_cues: int = 3
    max_claim_chars: int = 240
    max_script_chars: int = 640

    def __post_init__(self) -> None:
        if self.max_script_claims <= 0:
            raise ValueError("max_script_claims must be positive")
        if self.max_supporting_cues < 0:
            raise ValueError("max_supporting_cues must be non-negative")
        if self.max_claim_chars < 80:
            raise ValueError("max_claim_chars must be at least 80")
        if self.max_script_chars < self.max_claim_chars:
            raise ValueError("max_script_chars must not be smaller than max_claim_chars")


class ExtractiveGroundedScriptComposer:
    """Compose concise scripts only from selected evidence text.

    Material claim content is extractive. Generated text is limited to generic,
    truth-status-preserving transitions. The composer has no store or retrieval
    dependency, so it cannot silently widen the selected evidence boundary.
    """

    def __init__(self, config: GroundedScriptComposerConfig | None = None) -> None:
        self.config = config or GroundedScriptComposerConfig()

    def compose(self, request: ScriptCompositionRequest) -> GroundedScriptComposition:
        candidates = self._rank_candidates(request)
        primary = [
            item
            for item in candidates
            if item.safe_for_script
            and item.reference.experience_status
            in {ExperienceStatus.IMPLEMENTED, ExperienceStatus.PROTOTYPE}
        ]

        if not primary:
            return self._fallback(
                request,
                "selected evidence does not contain safe implemented or prototype experience",
                candidates,
            )

        script_candidates = [primary[0]]
        secondary = next(
            (
                item
                for item in candidates
                if item.reference.key != primary[0].reference.key and item.safe_for_script
            ),
            None,
        )
        if secondary is not None and self.config.max_script_claims > 1:
            script_candidates.append(secondary)

        claims: list[ScriptClaim] = []
        script_parts: list[str] = []
        used: set[tuple[str, str]] = set()

        for candidate in script_candidates[: self.config.max_script_claims]:
            rendered = self._render_claim(candidate)
            projected = " ".join((*script_parts, rendered)).strip()
            if len(projected) > self.config.max_script_chars:
                continue
            claims.append(ScriptClaim(text=rendered, evidence=(candidate.reference,)))
            script_parts.append(rendered)
            used.add(candidate.reference.key)

        if not claims:
            return self._fallback(
                request,
                "selected evidence could not be phrased without overstating its truth status",
                candidates,
            )

        cues = tuple(
            ResponseCue(text=self._cue_text(candidate), evidence=(candidate.reference,))
            for candidate in candidates
            if candidate.reference.key not in used and candidate.safe_for_script
        )[: self.config.max_supporting_cues]

        return GroundedScriptComposition(
            session_id=request.decision.session_id,
            query_generation=request.decision.query_generation,
            status=CompositionStatus.COMPOSED,
            evidence=request.decision.evidence,
            script=" ".join(script_parts),
            claims=tuple(claims),
            supporting_cues=cues,
        )

    def _rank_candidates(self, request: ScriptCompositionRequest) -> list[_Candidate]:
        query_tokens = _tokens(f"{request.question} {request.intent}")
        candidates: list[_Candidate] = []

        for ordinal, evidence in enumerate(request.evidence):
            for sentence_index, sentence in enumerate(_sentences(evidence.text)):
                excerpt = _bounded_excerpt(sentence, self.config.max_claim_chars)
                if not excerpt:
                    continue
                candidates.append(
                    _Candidate(
                        reference=evidence.reference,
                        text=excerpt,
                        overlap=len(query_tokens & _tokens(excerpt)),
                        ordinal=ordinal,
                        sentence_index=sentence_index,
                        safe_for_script=_status_safe(
                            evidence.reference.experience_status,
                            excerpt,
                        ),
                    )
                )

        return sorted(
            candidates,
            key=lambda item: (
                -int(item.safe_for_script),
                -item.overlap,
                -_STATUS_PRIORITY[item.reference.experience_status],
                item.ordinal,
                item.sentence_index,
            ),
        )

    @staticmethod
    def _render_claim(candidate: _Candidate) -> str:
        status = candidate.reference.experience_status
        if status is ExperienceStatus.IMPLEMENTED:
            prefix = "One example from work I've actually done is:"
        elif status is ExperienceStatus.PROTOTYPE:
            prefix = "In a prototype rather than production, the relevant example is:"
        elif status is ExperienceStatus.DESIGN:
            prefix = "For the design side—not something I'm claiming as shipped—I would propose:"
        else:
            prefix = "As a hypothetical approach—not production experience—I would frame it as:"
        return f"{prefix} {candidate.text}"

    @staticmethod
    def _cue_text(candidate: _Candidate) -> str:
        return f"[{candidate.reference.experience_status.value}] {candidate.text}"

    def _fallback(
        self,
        request: ScriptCompositionRequest,
        detail: str,
        candidates: list[_Candidate],
    ) -> GroundedScriptComposition:
        cues = tuple(
            ResponseCue(text=self._cue_text(candidate), evidence=(candidate.reference,))
            for candidate in candidates
            if candidate.safe_for_script
        )[: self.config.max_supporting_cues]
        return GroundedScriptComposition(
            session_id=request.decision.session_id,
            query_generation=request.decision.query_generation,
            status=CompositionStatus.FALLBACK_REQUIRED,
            evidence=request.decision.evidence,
            supporting_cues=cues,
            detail=detail,
        )


@dataclass(frozen=True)
class _Candidate:
    reference: EvidenceReference
    text: str
    overlap: int
    ordinal: int
    sentence_index: int
    safe_for_script: bool


def _status_safe(status: ExperienceStatus, text: str) -> bool:
    if status is ExperienceStatus.IMPLEMENTED:
        return True
    if status is ExperienceStatus.PROTOTYPE:
        return _PRODUCTION_MARKER.search(text) is None
    return _NON_PRODUCTION_ASSERTION.search(text) is None


def _sentences(text: str) -> tuple[str, ...]:
    parts = []
    for raw in _SENTENCE_SPLIT.split(text):
        cleaned = " ".join(raw.strip().lstrip("-*• ").split())
        if cleaned:
            parts.append(cleaned)
    return tuple(parts)


def _bounded_excerpt(text: str, limit: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    clipped = normalized[: limit + 1].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return f"{clipped}…"


def _tokens(text: str) -> frozenset[str]:
    return frozenset(token.lower() for token in _TOKEN_PATTERN.findall(text))
