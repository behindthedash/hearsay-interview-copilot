from __future__ import annotations

from dataclasses import replace

import pytest

from interview_copilot.knowledge.models import ExperienceStatus
from interview_copilot.response import EvidenceReference, ResponseMode
from interview_copilot.response_policy import (
    DuplicateQueryGenerationError,
    ResponseCoordinator,
    ResponsePolicyConfig,
    ResponsePolicyInput,
    RetrievalOutcome,
    StaleQueryGenerationError,
)


def _evidence(
    status: ExperienceStatus = ExperienceStatus.IMPLEMENTED,
    *,
    chunk_id: str = "chunk-1",
) -> EvidenceReference:
    return EvidenceReference(
        source_uri=f"career://{chunk_id}",
        collection="career",
        chunk_id=chunk_id,
        experience_status=status,
        title="Interview evidence",
        project="Example project",
    )


def _input(
    *,
    generation: int = 1,
    outcome: RetrievalOutcome = RetrievalOutcome.READY,
    confidence: float = 0.9,
    evidence: tuple[EvidenceReference, ...] | None = None,
    ambiguous: bool = False,
    conflict: bool = False,
    enabled: bool = True,
    detail: str | None = None,
) -> ResponsePolicyInput:
    if evidence is None:
        evidence = (_evidence(),) if outcome is RetrievalOutcome.READY else ()
    return ResponsePolicyInput(
        session_id="session-1",
        query_generation=generation,
        retrieval_outcome=outcome,
        retrieval_confidence=confidence,
        evidence=evidence,
        question_ambiguous=ambiguous,
        evidence_conflict=conflict,
        generated_script_enabled=enabled,
        detail=detail,
    )


@pytest.mark.parametrize(
    ("policy_input", "expected_mode", "reason"),
    [
        (_input(), ResponseMode.GENERATED_SCRIPT, None),
        (
            _input(confidence=0.45),
            ResponseMode.CUE_ONLY,
            "confidence-below-script-threshold",
        ),
        (
            _input(enabled=False),
            ResponseMode.CUE_ONLY,
            "generated-script-disabled",
        ),
        (
            _input(evidence=(_evidence(ExperienceStatus.HYPOTHETICAL),)),
            ResponseMode.CUE_ONLY,
            "no-implemented-or-prototype-evidence",
        ),
        (
            _input(evidence=(_evidence(ExperienceStatus.DESIGN),)),
            ResponseMode.CUE_ONLY,
            "no-implemented-or-prototype-evidence",
        ),
        (
            _input(conflict=True),
            ResponseMode.CLARIFICATION,
            "evidence-conflict",
        ),
        (
            _input(ambiguous=True),
            ResponseMode.CLARIFICATION,
            "question-ambiguous",
        ),
        (
            _input(outcome=RetrievalOutcome.NO_MATCH, confidence=0.0),
            ResponseMode.UNAVAILABLE,
            "retrieval-no-match",
        ),
        (
            _input(
                outcome=RetrievalOutcome.UNAVAILABLE,
                confidence=0.0,
                detail="provider failed",
            ),
            ResponseMode.UNAVAILABLE,
            "retrieval-unavailable",
        ),
        (
            _input(confidence=0.1),
            ResponseMode.UNAVAILABLE,
            "confidence-below-script-threshold",
        ),
    ],
)
def test_response_policy_selects_exactly_one_mode(
    policy_input: ResponsePolicyInput,
    expected_mode: ResponseMode,
    reason: str | None,
) -> None:
    decision = ResponseCoordinator().evaluate(policy_input)

    assert decision.mode is expected_mode
    assert decision.session_id == policy_input.session_id
    assert decision.query_generation == policy_input.query_generation
    assert decision.eligibility.retrieval_confidence == policy_input.retrieval_confidence
    if reason is not None:
        assert reason in decision.eligibility.reasons


@pytest.mark.parametrize(
    "status",
    [ExperienceStatus.IMPLEMENTED, ExperienceStatus.PROTOTYPE],
)
def test_strong_actual_or_prototype_evidence_is_script_eligible(
    status: ExperienceStatus,
) -> None:
    decision = ResponseCoordinator().evaluate(_input(evidence=(_evidence(status),)))

    assert decision.mode is ResponseMode.GENERATED_SCRIPT
    assert decision.eligibility.script_eligible


def test_mixed_truth_status_can_generate_when_grounded_actual_evidence_exists() -> None:
    evidence = (
        _evidence(ExperienceStatus.IMPLEMENTED, chunk_id="implemented"),
        _evidence(ExperienceStatus.HYPOTHETICAL, chunk_id="hypothetical"),
    )

    decision = ResponseCoordinator().evaluate(_input(evidence=evidence))

    assert decision.mode is ResponseMode.GENERATED_SCRIPT
    assert decision.eligibility.script_eligible
    assert decision.evidence == evidence


def test_conflict_prefers_clarification_over_polished_answer() -> None:
    decision = ResponseCoordinator().evaluate(_input(conflict=True))

    assert decision.mode is ResponseMode.CLARIFICATION
    assert decision.clarification is not None
    assert "conflicting evidence" in decision.clarification
    assert not decision.eligibility.script_eligible


def test_ambiguous_question_prefers_clarification() -> None:
    decision = ResponseCoordinator().evaluate(_input(ambiguous=True))

    assert decision.mode is ResponseMode.CLARIFICATION
    assert decision.clarification is not None
    assert "Clarify" in decision.clarification


def test_provider_failure_preserves_secret_safe_detail() -> None:
    decision = ResponseCoordinator().evaluate(
        _input(
            outcome=RetrievalOutcome.UNAVAILABLE,
            confidence=0.0,
            detail="retrieval unavailable (ConnectionError)",
        )
    )

    assert decision.mode is ResponseMode.UNAVAILABLE
    assert decision.detail == "retrieval unavailable (ConnectionError)"


def test_no_match_is_unavailable_without_fabricating_guidance() -> None:
    decision = ResponseCoordinator().evaluate(
        _input(outcome=RetrievalOutcome.NO_MATCH, confidence=0.0)
    )

    assert decision.mode is ResponseMode.UNAVAILABLE
    assert decision.evidence == ()
    assert decision.detail == "no trustworthy supporting evidence was found"


def test_custom_thresholds_are_deterministic() -> None:
    coordinator = ResponseCoordinator(
        ResponsePolicyConfig(
            generated_script_min_confidence=0.8,
            cue_only_min_confidence=0.5,
        )
    )

    cue = coordinator.evaluate(_input(generation=1, confidence=0.7))
    unavailable = coordinator.evaluate(_input(generation=2, confidence=0.4))

    assert cue.mode is ResponseMode.CUE_ONLY
    assert unavailable.mode is ResponseMode.UNAVAILABLE


def test_same_generation_replay_returns_same_decision() -> None:
    coordinator = ResponseCoordinator()
    policy_input = _input()

    first = coordinator.evaluate(policy_input)
    second = coordinator.evaluate(policy_input)

    assert second is first


def test_same_generation_with_changed_inputs_is_rejected() -> None:
    coordinator = ResponseCoordinator()
    policy_input = _input()
    coordinator.evaluate(policy_input)

    with pytest.raises(DuplicateQueryGenerationError):
        coordinator.evaluate(replace(policy_input, retrieval_confidence=0.7))


def test_older_generation_cannot_be_evaluated_after_newer_generation() -> None:
    coordinator = ResponseCoordinator()
    coordinator.evaluate(_input(generation=2))

    with pytest.raises(StaleQueryGenerationError):
        coordinator.evaluate(_input(generation=1))


def test_superseded_decision_cannot_be_activated() -> None:
    coordinator = ResponseCoordinator()
    first = coordinator.evaluate(_input(generation=1))
    second = coordinator.evaluate(_input(generation=2, confidence=0.4))

    with pytest.raises(StaleQueryGenerationError):
        coordinator.activate(first)

    assert coordinator.activate(second) is second


def test_forged_current_generation_decision_cannot_be_activated() -> None:
    coordinator = ResponseCoordinator()
    decision = coordinator.evaluate(_input())
    forged = replace(decision, mode=ResponseMode.CUE_ONLY)

    with pytest.raises(StaleQueryGenerationError):
        coordinator.activate(forged)


def test_reset_session_releases_generation_state() -> None:
    coordinator = ResponseCoordinator()
    first = coordinator.evaluate(_input(generation=3))
    coordinator.reset_session("session-1")

    with pytest.raises(StaleQueryGenerationError):
        coordinator.activate(first)

    restarted = coordinator.evaluate(_input(generation=1))
    assert restarted.query_generation == 1


@pytest.mark.parametrize(
    "config",
    [
        ResponsePolicyConfig,
    ],
)
def test_policy_config_defaults_are_ordered(config: type[ResponsePolicyConfig]) -> None:
    value = config()
    assert 0.0 <= value.cue_only_min_confidence <= value.generated_script_min_confidence <= 1.0


def test_policy_input_rejects_inconsistent_retrieval_state() -> None:
    with pytest.raises(ValueError, match="ready retrieval outcome requires evidence"):
        _input(outcome=RetrievalOutcome.READY, evidence=())

    with pytest.raises(ValueError, match="terminal retrieval outcomes must not carry evidence"):
        _input(outcome=RetrievalOutcome.NO_MATCH, evidence=(_evidence(),))


def test_policy_config_rejects_inverted_thresholds() -> None:
    with pytest.raises(ValueError, match="must not exceed"):
        ResponsePolicyConfig(
            generated_script_min_confidence=0.4,
            cue_only_min_confidence=0.5,
        )
