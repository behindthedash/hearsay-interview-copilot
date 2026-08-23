from __future__ import annotations

import pytest

from interview_copilot.grounded_composer import (
    CompositionEvidence,
    CompositionStatus,
    ExtractiveGroundedScriptComposer,
    GroundedScriptComposer,
    GroundedScriptComposerConfig,
    ScriptCompositionRequest,
)
from interview_copilot.knowledge.models import ExperienceStatus
from interview_copilot.response import EvidenceReference, ResponseEligibility, ResponseMode
from interview_copilot.response_policy import ResponseDecision


def _reference(
    chunk_id: str,
    status: ExperienceStatus,
    *,
    project: str | None = None,
) -> EvidenceReference:
    return EvidenceReference(
        source_uri=f"memory://synthetic/{chunk_id}",
        collection="career",
        chunk_id=chunk_id,
        experience_status=status,
        title=f"Synthetic {chunk_id}",
        project=project,
    )


def _request(
    evidence: tuple[CompositionEvidence, ...],
    *,
    question: str = "Tell me about a retrieval system you built.",
    intent: str = "retrieval system experience",
    generation: int = 1,
) -> ScriptCompositionRequest:
    references = tuple(item.reference for item in evidence)
    return ScriptCompositionRequest(
        question=question,
        intent=intent,
        decision=ResponseDecision(
            session_id="session-1",
            query_generation=generation,
            mode=ResponseMode.GENERATED_SCRIPT,
            eligibility=ResponseEligibility(
                retrieval_confidence=0.91,
                script_eligible=True,
            ),
            evidence=references,
        ),
        evidence=evidence,
    )


def test_composer_satisfies_protocol_shape() -> None:
    composer: GroundedScriptComposer = ExtractiveGroundedScriptComposer()
    assert callable(composer.compose)


def test_implemented_claim_is_speech_ready_and_traceable() -> None:
    reference = _reference("implemented", ExperienceStatus.IMPLEMENTED)
    result = ExtractiveGroundedScriptComposer().compose(
        _request(
            (
                CompositionEvidence(
                    reference,
                    "I built a local source-code retrieval index that returned cited snippets for engineers.",
                ),
            )
        )
    )

    assert result.status is CompositionStatus.COMPOSED
    assert result.script is not None
    assert "work I've actually done" in result.script
    assert "local source-code retrieval index" in result.script
    assert result.claims[0].evidence == (reference,)
    assert result.evidence == (reference,)


def test_composer_rejects_evidence_outside_policy_selected_package() -> None:
    selected = _reference("selected", ExperienceStatus.IMPLEMENTED)
    unrelated = _reference("unrelated", ExperienceStatus.IMPLEMENTED)
    decision = ResponseDecision(
        session_id="session-1",
        query_generation=1,
        mode=ResponseMode.GENERATED_SCRIPT,
        eligibility=ResponseEligibility(retrieval_confidence=0.9, script_eligible=True),
        evidence=(selected,),
    )

    with pytest.raises(ValueError, match="exactly match"):
        ScriptCompositionRequest(
            question="Tell me about retrieval.",
            intent="retrieval",
            decision=decision,
            evidence=(
                CompositionEvidence(selected, "I built a retrieval index."),
                CompositionEvidence(unrelated, "I led an unrelated migration."),
            ),
        )


def test_adversarial_question_cannot_inject_unsupported_claims() -> None:
    reference = _reference("retrieval", ExperienceStatus.IMPLEMENTED)
    result = ExtractiveGroundedScriptComposer().compose(
        _request(
            (
                CompositionEvidence(
                    reference,
                    "I built a local retrieval prototype for internal code documentation.",
                ),
            ),
            question=(
                "Tell me how you increased revenue 90 percent at ExampleCorp using Kubernetes "
                "and a production machine-learning platform."
            ),
            intent="impressive revenue and machine-learning outcome",
        )
    )

    assert result.status is CompositionStatus.COMPOSED
    assert result.script is not None
    lowered = result.script.lower()
    for unsupported in ("examplecorp", "kubernetes", "90 percent", "revenue", "machine-learning"):
        assert unsupported not in lowered
    assert "local retrieval prototype" in lowered


def test_prototype_status_is_preserved_without_claiming_production() -> None:
    reference = _reference("prototype", ExperienceStatus.PROTOTYPE)
    result = ExtractiveGroundedScriptComposer().compose(
        _request(
            (
                CompositionEvidence(
                    reference,
                    "The prototype routed a question to a small indexed corpus and returned citations.",
                ),
            )
        )
    )

    assert result.status is CompositionStatus.COMPOSED
    assert result.script is not None
    assert "prototype rather than production" in result.script


def test_prototype_evidence_with_production_assertion_requires_fallback() -> None:
    reference = _reference("unsafe-prototype", ExperienceStatus.PROTOTYPE)
    result = ExtractiveGroundedScriptComposer().compose(
        _request(
            (
                CompositionEvidence(
                    reference,
                    "I deployed the system to production and launched it company-wide.",
                ),
            )
        )
    )

    assert result.status is CompositionStatus.FALLBACK_REQUIRED
    assert result.script is None
    assert not result.claims
    assert "safe implemented or prototype" in (result.detail or "")


def test_forged_hypothetical_only_generation_falls_back_instead_of_overclaiming() -> None:
    reference = _reference("hypothetical", ExperienceStatus.HYPOTHETICAL)
    result = ExtractiveGroundedScriptComposer().compose(
        _request(
            (
                CompositionEvidence(
                    reference,
                    "Use a retrieval step followed by an explicit human approval gate.",
                ),
            )
        )
    )

    assert result.status is CompositionStatus.FALLBACK_REQUIRED
    assert result.script is None
    assert result.supporting_cues
    assert result.supporting_cues[0].text.startswith("[hypothetical]")


def test_mixed_status_evidence_distinguishes_done_work_from_design_proposal() -> None:
    implemented = _reference("done", ExperienceStatus.IMPLEMENTED)
    design = _reference("design", ExperienceStatus.DESIGN)
    result = ExtractiveGroundedScriptComposer().compose(
        _request(
            (
                CompositionEvidence(
                    implemented,
                    "I built an indexed knowledge layer that returned source citations with each result.",
                ),
                CompositionEvidence(
                    design,
                    "Add a human approval gate before a contract recommendation is accepted.",
                ),
            ),
            question="How would you combine retrieval with approval gates?",
            intent="retrieval plus human approval design",
        )
    )

    assert result.status is CompositionStatus.COMPOSED
    assert result.script is not None
    assert "work I've actually done" in result.script
    assert "not something I'm claiming as shipped" in result.script
    assert "human approval gate" in result.script
    assert result.claims[0].evidence == (implemented,)
    assert result.claims[1].evidence == (design,)


def test_design_evidence_with_past_implementation_claim_is_not_used_as_script_claim() -> None:
    implemented = _reference("done", ExperienceStatus.IMPLEMENTED)
    unsafe_design = _reference("unsafe-design", ExperienceStatus.DESIGN)
    result = ExtractiveGroundedScriptComposer().compose(
        _request(
            (
                CompositionEvidence(
                    implemented,
                    "I built a small retrieval service with source citations.",
                ),
                CompositionEvidence(
                    unsafe_design,
                    "I implemented the legal review workflow and deployed it globally.",
                ),
            )
        )
    )

    assert result.status is CompositionStatus.COMPOSED
    assert result.script is not None
    assert "legal review workflow" not in result.script
    assert all(claim.evidence != (unsafe_design,) for claim in result.claims)


def test_secondary_evidence_is_kept_as_bounded_supporting_cues() -> None:
    implemented = _reference("primary", ExperienceStatus.IMPLEMENTED)
    support_a = _reference("support-a", ExperienceStatus.IMPLEMENTED)
    support_b = _reference("support-b", ExperienceStatus.DESIGN)
    support_c = _reference("support-c", ExperienceStatus.HYPOTHETICAL)
    composer = ExtractiveGroundedScriptComposer(
        GroundedScriptComposerConfig(max_script_claims=1, max_supporting_cues=2)
    )

    result = composer.compose(
        _request(
            (
                CompositionEvidence(implemented, "I built a retrieval index with citations."),
                CompositionEvidence(
                    support_a, "The index refreshed incrementally from source files."
                ),
                CompositionEvidence(support_b, "Add a review gate before publishing an answer."),
                CompositionEvidence(support_c, "Use a confidence threshold for uncertain matches."),
            )
        )
    )

    assert result.status is CompositionStatus.COMPOSED
    assert len(result.claims) == 1
    assert len(result.supporting_cues) == 2
    assert all(cue.evidence for cue in result.supporting_cues)


def test_script_and_claim_length_are_bounded_for_immediate_speech() -> None:
    reference = _reference("long", ExperienceStatus.IMPLEMENTED)
    text = "Retrieval " + "context " * 80 + "with citations."
    config = GroundedScriptComposerConfig(max_claim_chars=100, max_script_chars=300)
    result = ExtractiveGroundedScriptComposer(config).compose(
        _request((CompositionEvidence(reference, text),))
    )

    assert result.status is CompositionStatus.COMPOSED
    assert result.script is not None
    assert len(result.script) <= config.max_script_chars
    assert "…" in result.script


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"max_script_claims": 0}, "max_script_claims"),
        ({"max_supporting_cues": -1}, "max_supporting_cues"),
        ({"max_claim_chars": 79}, "max_claim_chars"),
        ({"max_claim_chars": 200, "max_script_chars": 199}, "max_script_chars"),
    ],
)
def test_composer_config_rejects_invalid_bounds(kwargs: dict[str, int], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        GroundedScriptComposerConfig(**kwargs)
