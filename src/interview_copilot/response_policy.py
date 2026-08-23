from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import StrEnum

from .knowledge.models import ExperienceStatus
from .response import EvidenceReference, ResponseEligibility, ResponseMode

_SCRIPT_TRUTH_STATUSES = frozenset(
    {ExperienceStatus.IMPLEMENTED, ExperienceStatus.PROTOTYPE}
)


class RetrievalOutcome(StrEnum):
    """Normalized retrieval result consumed by response-mode policy."""

    READY = "ready"
    NO_MATCH = "no-match"
    UNAVAILABLE = "unavailable"


class StaleQueryGenerationError(RuntimeError):
    """Raised when an older query generation attempts to produce or activate guidance."""


class DuplicateQueryGenerationError(RuntimeError):
    """Raised when one generation is evaluated with conflicting policy inputs."""


@dataclass(frozen=True)
class ResponsePolicyConfig:
    """Deterministic confidence gates for response assistance modes."""

    generated_script_min_confidence: float = 0.65
    cue_only_min_confidence: float = 0.25

    def __post_init__(self) -> None:
        if not 0.0 <= self.cue_only_min_confidence <= 1.0:
            raise ValueError("cue_only_min_confidence must be between 0 and 1")
        if not 0.0 <= self.generated_script_min_confidence <= 1.0:
            raise ValueError("generated_script_min_confidence must be between 0 and 1")
        if self.cue_only_min_confidence > self.generated_script_min_confidence:
            raise ValueError(
                "cue_only_min_confidence must not exceed generated_script_min_confidence"
            )


@dataclass(frozen=True)
class ResponsePolicyInput:
    """Bounded evidence state for exactly one interviewer query generation."""

    session_id: str
    query_generation: int
    retrieval_outcome: RetrievalOutcome
    retrieval_confidence: float
    evidence: tuple[EvidenceReference, ...] = ()
    question_ambiguous: bool = False
    evidence_conflict: bool = False
    generated_script_enabled: bool = True
    detail: str | None = None

    def __post_init__(self) -> None:
        if not self.session_id.strip():
            raise ValueError("session_id must be non-empty")
        if self.query_generation <= 0:
            raise ValueError("query_generation must be positive")
        if not 0.0 <= self.retrieval_confidence <= 1.0:
            raise ValueError("retrieval_confidence must be between 0 and 1")

        keys = [item.key for item in self.evidence]
        if len(keys) != len(set(keys)):
            raise ValueError("policy evidence references must be unique")

        if self.retrieval_outcome is RetrievalOutcome.READY and not self.evidence:
            raise ValueError("ready retrieval outcome requires evidence")
        if self.retrieval_outcome is not RetrievalOutcome.READY and self.evidence:
            raise ValueError("terminal retrieval outcomes must not carry evidence")


@dataclass(frozen=True)
class ResponseDecision:
    """One generation-bound response-mode decision before content composition."""

    session_id: str
    query_generation: int
    mode: ResponseMode
    eligibility: ResponseEligibility
    evidence: tuple[EvidenceReference, ...] = ()
    clarification: str | None = None
    detail: str | None = None

    def __post_init__(self) -> None:
        if not self.session_id.strip():
            raise ValueError("session_id must be non-empty")
        if self.query_generation <= 0:
            raise ValueError("query_generation must be positive")
        if self.mode is ResponseMode.CLARIFICATION:
            if self.clarification is None or not self.clarification.strip():
                raise ValueError("clarification decision requires clarification text")
        elif self.clarification is not None:
            raise ValueError("only clarification decisions may carry clarification text")
        if self.mode is ResponseMode.UNAVAILABLE:
            if self.detail is None or not self.detail.strip():
                raise ValueError("unavailable decision requires detail")


class ResponseCoordinator:
    """Choose one safe response mode and enforce latest-query-wins activation."""

    def __init__(self, config: ResponsePolicyConfig | None = None) -> None:
        self.config = config or ResponsePolicyConfig()
        self._lock = threading.RLock()
        self._latest_inputs: dict[str, ResponsePolicyInput] = {}
        self._latest_decisions: dict[str, ResponseDecision] = {}

    def evaluate(self, policy_input: ResponsePolicyInput) -> ResponseDecision:
        """Evaluate one generation exactly once, returning the same decision on replay."""
        with self._lock:
            previous_input = self._latest_inputs.get(policy_input.session_id)
            previous_decision = self._latest_decisions.get(policy_input.session_id)
            if previous_input is not None:
                if policy_input.query_generation < previous_input.query_generation:
                    raise StaleQueryGenerationError(
                        "query generation was superseded by newer interviewer guidance"
                    )
                if policy_input.query_generation == previous_input.query_generation:
                    if policy_input != previous_input:
                        raise DuplicateQueryGenerationError(
                            "query generation already has different policy inputs"
                        )
                    assert previous_decision is not None
                    return previous_decision

            decision = self._decide(policy_input)
            self._latest_inputs[policy_input.session_id] = policy_input
            self._latest_decisions[policy_input.session_id] = decision
            return decision

    def activate(self, decision: ResponseDecision) -> ResponseDecision:
        """Accept only the current decision for presentation-layer activation."""
        with self._lock:
            latest = self._latest_decisions.get(decision.session_id)
            if latest is None or latest.query_generation != decision.query_generation:
                raise StaleQueryGenerationError(
                    "response decision was superseded by a newer query generation"
                )
            if latest != decision:
                raise StaleQueryGenerationError(
                    "response decision does not match the current generation result"
                )
            return decision

    def reset_session(self, session_id: str) -> None:
        """Forget transient policy state for one interview session."""
        with self._lock:
            self._latest_inputs.pop(session_id, None)
            self._latest_decisions.pop(session_id, None)

    def _decide(self, policy_input: ResponsePolicyInput) -> ResponseDecision:
        eligibility = self._eligibility(policy_input)

        if policy_input.retrieval_outcome is RetrievalOutcome.UNAVAILABLE:
            return self._unavailable(
                policy_input,
                eligibility,
                policy_input.detail or "retrieval is unavailable",
            )

        if policy_input.question_ambiguous:
            return ResponseDecision(
                session_id=policy_input.session_id,
                query_generation=policy_input.query_generation,
                mode=ResponseMode.CLARIFICATION,
                eligibility=eligibility,
                evidence=policy_input.evidence,
                clarification="Clarify which part of the question should be addressed first.",
            )

        if policy_input.retrieval_outcome is RetrievalOutcome.NO_MATCH:
            return self._unavailable(
                policy_input,
                eligibility,
                policy_input.detail or "no trustworthy supporting evidence was found",
            )

        if policy_input.evidence_conflict:
            return ResponseDecision(
                session_id=policy_input.session_id,
                query_generation=policy_input.query_generation,
                mode=ResponseMode.CLARIFICATION,
                eligibility=eligibility,
                evidence=policy_input.evidence,
                clarification=(
                    "Clarify the intended scope before choosing between conflicting evidence."
                ),
            )

        if eligibility.script_eligible:
            return ResponseDecision(
                session_id=policy_input.session_id,
                query_generation=policy_input.query_generation,
                mode=ResponseMode.GENERATED_SCRIPT,
                eligibility=eligibility,
                evidence=policy_input.evidence,
            )

        if policy_input.retrieval_confidence >= self.config.cue_only_min_confidence:
            return ResponseDecision(
                session_id=policy_input.session_id,
                query_generation=policy_input.query_generation,
                mode=ResponseMode.CUE_ONLY,
                eligibility=eligibility,
                evidence=policy_input.evidence,
            )

        return self._unavailable(
            policy_input,
            eligibility,
            "retrieved evidence is too weak for trustworthy guidance",
        )

    def _eligibility(self, policy_input: ResponsePolicyInput) -> ResponseEligibility:
        reasons: list[str] = []
        script_truth_available = any(
            item.experience_status in _SCRIPT_TRUTH_STATUSES
            for item in policy_input.evidence
        )

        if policy_input.retrieval_outcome is not RetrievalOutcome.READY:
            reasons.append(f"retrieval-{policy_input.retrieval_outcome.value}")
        if policy_input.question_ambiguous:
            reasons.append("question-ambiguous")
        if policy_input.evidence_conflict:
            reasons.append("evidence-conflict")
        if not policy_input.generated_script_enabled:
            reasons.append("generated-script-disabled")
        if not script_truth_available:
            reasons.append("no-implemented-or-prototype-evidence")
        if policy_input.retrieval_confidence < self.config.generated_script_min_confidence:
            reasons.append("confidence-below-script-threshold")

        script_eligible = (
            policy_input.retrieval_outcome is RetrievalOutcome.READY
            and not policy_input.question_ambiguous
            and not policy_input.evidence_conflict
            and policy_input.generated_script_enabled
            and script_truth_available
            and policy_input.retrieval_confidence
            >= self.config.generated_script_min_confidence
        )
        return ResponseEligibility(
            retrieval_confidence=policy_input.retrieval_confidence,
            script_eligible=script_eligible,
            evidence_conflict=policy_input.evidence_conflict,
            reasons=tuple(reasons),
        )

    @staticmethod
    def _unavailable(
        policy_input: ResponsePolicyInput,
        eligibility: ResponseEligibility,
        detail: str,
    ) -> ResponseDecision:
        return ResponseDecision(
            session_id=policy_input.session_id,
            query_generation=policy_input.query_generation,
            mode=ResponseMode.UNAVAILABLE,
            eligibility=eligibility,
            evidence=policy_input.evidence,
            detail=detail,
        )
