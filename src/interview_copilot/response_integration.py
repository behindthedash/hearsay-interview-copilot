from __future__ import annotations

from dataclasses import dataclass

from .cue_retrieval import CueEvidence, CueState, InterviewCue
from .grounded_composer import (
    CompositionEvidence,
    CompositionStatus,
    GroundedScriptComposer,
    ScriptCompositionRequest,
)
from .response import EvidenceReference, ResponseCue, ResponseMode, ResponsePackage
from .response_policy import (
    ResponseCoordinator,
    ResponseDecision,
    ResponsePolicyInput,
    RetrievalOutcome,
)


@dataclass(frozen=True)
class ResponseAssemblyContext:
    """Per-turn response-policy inputs that are not owned by retrieval."""

    generated_script_enabled: bool = True
    question_ambiguous: bool = False
    evidence_conflict: bool = False


@dataclass(frozen=True)
class CueResponseAssemblerConfig:
    """Presentation-safe bounds for response-package cue projection."""

    max_cues: int = ResponsePackage.MAX_CUES
    max_cue_chars: int = 180

    def __post_init__(self) -> None:
        if not 1 <= self.max_cues <= ResponsePackage.MAX_CUES:
            raise ValueError(
                f"max_cues must be between 1 and {ResponsePackage.MAX_CUES}"
            )
        if self.max_cue_chars < 40:
            raise ValueError("max_cue_chars must be at least 40")


@dataclass(frozen=True)
class ResponseAssemblyResult:
    """Traceable bridge from one retrieval cue to one final response package."""

    source_cue: InterviewCue
    decision: ResponseDecision
    package: ResponsePackage
    composition_status: CompositionStatus | None = None

    def __post_init__(self) -> None:
        if self.package.session_id != self.source_cue.session_id:
            raise ValueError("response package session must match source cue")
        if self.package.query_generation != self.source_cue.generation:
            raise ValueError("response package generation must match source cue")
        if self.decision.session_id != self.source_cue.session_id:
            raise ValueError("response decision session must match source cue")
        if self.decision.query_generation != self.source_cue.generation:
            raise ValueError("response decision generation must match source cue")


class InterviewCueResponseAssembler:
    """Convert bounded retrieval evidence into one grounded response package.

    The assembler does not retrieve additional knowledge. It maps the evidence already
    selected by ``InterviewCueRetriever`` into response-policy inputs, invokes the
    grounded composer only for generated-script decisions, and keeps cue projection
    separate from script text.
    """

    def __init__(
        self,
        coordinator: ResponseCoordinator,
        composer: GroundedScriptComposer,
        config: CueResponseAssemblerConfig | None = None,
    ) -> None:
        self.coordinator = coordinator
        self.composer = composer
        self.config = config or CueResponseAssemblerConfig()

    def assemble(
        self,
        cue: InterviewCue,
        context: ResponseAssemblyContext | None = None,
    ) -> ResponseAssemblyResult:
        context = context or ResponseAssemblyContext()
        evidence = _cue_evidence(cue)
        references = tuple(_reference(item) for item in evidence)
        decision = self.coordinator.evaluate(
            ResponsePolicyInput(
                session_id=cue.session_id,
                query_generation=cue.generation,
                retrieval_outcome=_retrieval_outcome(cue.state),
                retrieval_confidence=cue.confidence,
                evidence=references if cue.state is CueState.READY else (),
                question_ambiguous=context.question_ambiguous,
                evidence_conflict=context.evidence_conflict,
                generated_script_enabled=context.generated_script_enabled,
                detail=cue.detail,
            )
        )

        if decision.mode is ResponseMode.GENERATED_SCRIPT:
            return self._generated(cue, decision, evidence)
        if decision.mode is ResponseMode.CUE_ONLY:
            package = ResponsePackage(
                session_id=cue.session_id,
                query_generation=cue.generation,
                mode=ResponseMode.CUE_ONLY,
                eligibility=decision.eligibility,
                evidence=decision.evidence,
                cues=self._evidence_cues(evidence),
            )
            return ResponseAssemblyResult(cue, decision, package)
        if decision.mode is ResponseMode.CLARIFICATION:
            package = ResponsePackage(
                session_id=cue.session_id,
                query_generation=cue.generation,
                mode=ResponseMode.CLARIFICATION,
                eligibility=decision.eligibility,
                evidence=decision.evidence,
                clarification=decision.clarification,
            )
            return ResponseAssemblyResult(cue, decision, package)

        package = ResponsePackage(
            session_id=cue.session_id,
            query_generation=cue.generation,
            mode=ResponseMode.UNAVAILABLE,
            eligibility=decision.eligibility,
            evidence=decision.evidence,
            detail=decision.detail or cue.detail or "response guidance is unavailable",
        )
        return ResponseAssemblyResult(cue, decision, package)

    def _generated(
        self,
        cue: InterviewCue,
        decision: ResponseDecision,
        evidence: tuple[CueEvidence, ...],
    ) -> ResponseAssemblyResult:
        evidence_by_key = {
            _reference(item).key: CompositionEvidence(_reference(item), item.text)
            for item in evidence
        }
        composition = self.composer.compose(
            ScriptCompositionRequest(
                question=cue.question,
                intent=cue.intent,
                decision=decision,
                evidence=tuple(evidence_by_key[item.key] for item in decision.evidence),
            )
        )

        if composition.status is CompositionStatus.COMPOSED:
            claimed_keys = {
                item.key for claim in composition.claims for item in claim.evidence
            }
            supporting = tuple(
                self._bounded_cue(item)
                for item in composition.supporting_cues
                if item.evidence
                and all(reference.key not in claimed_keys for reference in item.evidence)
            )[: self.config.max_cues]
            package = ResponsePackage(
                session_id=cue.session_id,
                query_generation=cue.generation,
                mode=ResponseMode.GENERATED_SCRIPT,
                eligibility=decision.eligibility,
                evidence=decision.evidence,
                script=composition.script,
                cues=supporting,
            )
            return ResponseAssemblyResult(
                cue,
                decision,
                package,
                composition_status=composition.status,
            )

        fallback_cues = tuple(
            self._bounded_cue(item) for item in composition.supporting_cues
        )[: self.config.max_cues]
        if fallback_cues:
            package = ResponsePackage(
                session_id=cue.session_id,
                query_generation=cue.generation,
                mode=ResponseMode.CUE_ONLY,
                eligibility=decision.eligibility,
                evidence=decision.evidence,
                cues=fallback_cues,
                detail=composition.detail,
            )
        else:
            package = ResponsePackage(
                session_id=cue.session_id,
                query_generation=cue.generation,
                mode=ResponseMode.UNAVAILABLE,
                eligibility=decision.eligibility,
                evidence=decision.evidence,
                detail=composition.detail or "grounded script composition was unavailable",
            )
        return ResponseAssemblyResult(
            cue,
            decision,
            package,
            composition_status=composition.status,
        )

    def _evidence_cues(self, evidence: tuple[CueEvidence, ...]) -> tuple[ResponseCue, ...]:
        return tuple(
            self._bounded_cue(
                ResponseCue(
                    text=f"[{item.experience_status.value}] {item.text}",
                    evidence=(_reference(item),),
                )
            )
            for item in evidence
        )[: self.config.max_cues]

    def _bounded_cue(self, cue: ResponseCue) -> ResponseCue:
        return ResponseCue(
            text=_bounded_text(cue.text, self.config.max_cue_chars),
            evidence=cue.evidence,
        )


def _cue_evidence(cue: InterviewCue) -> tuple[CueEvidence, ...]:
    ordered = tuple(
        item
        for item in (cue.primary_story, *cue.supporting_points, cue.role_bridge)
        if item is not None
    )
    deduplicated: list[CueEvidence] = []
    seen: set[tuple[str, str]] = set()
    for item in ordered:
        key = (item.collection, item.chunk_id)
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(item)

    if cue.state is CueState.READY and not deduplicated:
        raise ValueError("ready interview cue must carry retrieved evidence")
    return tuple(deduplicated)


def _reference(item: CueEvidence) -> EvidenceReference:
    return EvidenceReference(
        source_uri=item.source_uri,
        collection=item.collection,
        chunk_id=item.chunk_id,
        experience_status=item.experience_status,
        title=item.title,
        project=item.project,
    )


def _retrieval_outcome(state: CueState) -> RetrievalOutcome:
    if state is CueState.READY:
        return RetrievalOutcome.READY
    if state is CueState.NO_MATCH:
        return RetrievalOutcome.NO_MATCH
    return RetrievalOutcome.UNAVAILABLE


def _bounded_text(text: str, limit: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    budget = limit - 1
    clipped = normalized[: budget + 1].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return f"{clipped[:budget]}…"
