import pytest

from interview_copilot.knowledge.models import ExperienceStatus
from interview_copilot.response import (
    EvidenceReference,
    ResponseCue,
    ResponseEligibility,
    ResponseLifecycle,
    ResponseMode,
    ResponsePackage,
)


def evidence(
    chunk_id: str = "chunk-1",
    *,
    status: ExperienceStatus = ExperienceStatus.IMPLEMENTED,
) -> EvidenceReference:
    return EvidenceReference(
        source_uri="projects/example.md",
        collection="career",
        chunk_id=chunk_id,
        experience_status=status,
        title="Example project",
        project="example",
    )


def eligibility(
    *,
    confidence: float = 0.82,
    script_eligible: bool = True,
    conflict: bool = False,
) -> ResponseEligibility:
    return ResponseEligibility(
        retrieval_confidence=confidence,
        script_eligible=script_eligible,
        evidence_conflict=conflict,
    )


def generated_package() -> ResponsePackage:
    item = evidence()
    return ResponsePackage(
        session_id="session-a",
        query_generation=7,
        mode=ResponseMode.GENERATED_SCRIPT,
        eligibility=eligibility(),
        evidence=(item,),
        script="I implemented the retrieval layer and validated it with deterministic tests.",
        cues=(ResponseCue("Mention deterministic validation.", evidence=(item,)),),
    )


def test_response_mode_contains_exact_supported_values():
    assert {mode.value for mode in ResponseMode} == {
        "generated-script",
        "cue-only",
        "clarification",
        "unavailable",
    }
    assert {state.value for state in ResponseLifecycle} == {
        "pending",
        "active",
        "dismissed",
        "superseded",
    }


def test_generated_script_package_is_immutable_and_preserves_truth_metadata():
    package = generated_package()

    assert package.lifecycle is ResponseLifecycle.PENDING
    assert package.experience_statuses == (ExperienceStatus.IMPLEMENTED,)
    assert package.cues[0].evidence[0].source_uri == "projects/example.md"

    with pytest.raises(AttributeError):
        package.query_generation = 8  # type: ignore[misc]


def test_lifecycle_change_returns_new_package_without_alignment_state():
    package = generated_package()
    active = package.with_lifecycle(ResponseLifecycle.ACTIVE)

    assert package.lifecycle is ResponseLifecycle.PENDING
    assert active.lifecycle is ResponseLifecycle.ACTIVE
    assert active.query_generation == package.query_generation
    assert "alignment" not in active.to_dict()


@pytest.mark.parametrize(
    ("mode", "kwargs", "message"),
    [
        (
            ResponseMode.GENERATED_SCRIPT,
            {"script": None, "evidence": (evidence(),)},
            "requires script text",
        ),
        (
            ResponseMode.GENERATED_SCRIPT,
            {"script": "Supported answer", "evidence": ()},
            "requires evidence",
        ),
        (
            ResponseMode.GENERATED_SCRIPT,
            {"script": "Supported answer", "evidence": (evidence(),), "eligible": False},
            "requires script eligibility",
        ),
        (
            ResponseMode.CUE_ONLY,
            {"cues": ()},
            "requires at least one usable cue",
        ),
        (
            ResponseMode.CLARIFICATION,
            {"clarification": None},
            "requires clarification text",
        ),
        (
            ResponseMode.UNAVAILABLE,
            {"detail": None},
            "requires a detail message",
        ),
    ],
)
def test_invalid_mode_combinations_are_rejected(mode, kwargs, message):
    eligible = kwargs.pop("eligible", True)
    with pytest.raises(ValueError, match=message):
        ResponsePackage(
            session_id="session-a",
            query_generation=1,
            mode=mode,
            eligibility=eligibility(script_eligible=eligible),
            **kwargs,
        )


def test_non_generated_modes_reject_script_content():
    with pytest.raises(ValueError, match="only generated-script"):
        ResponsePackage(
            session_id="session-a",
            query_generation=1,
            mode=ResponseMode.CUE_ONLY,
            eligibility=eligibility(script_eligible=False),
            script="This should not be here.",
            cues=(ResponseCue("Use the architecture example."),),
        )


def test_generated_content_requires_positive_query_generation():
    with pytest.raises(ValueError, match="query_generation must be positive"):
        ResponsePackage(
            session_id="session-a",
            query_generation=0,
            mode=ResponseMode.GENERATED_SCRIPT,
            eligibility=eligibility(),
            evidence=(evidence(),),
            script="Supported answer",
        )


def test_cues_are_bounded():
    cues = tuple(ResponseCue(f"Point {index}") for index in range(ResponsePackage.MAX_CUES + 1))

    with pytest.raises(ValueError, match="at most"):
        ResponsePackage(
            session_id="session-a",
            query_generation=2,
            mode=ResponseMode.CUE_ONLY,
            eligibility=eligibility(script_eligible=False),
            cues=cues,
        )


def test_cue_evidence_must_be_in_package_evidence():
    item = evidence("chunk-in-cue")
    with pytest.raises(ValueError, match="cue evidence"):
        ResponsePackage(
            session_id="session-a",
            query_generation=2,
            mode=ResponseMode.CUE_ONLY,
            eligibility=eligibility(script_eligible=False),
            evidence=(),
            cues=(ResponseCue("Use the project example.", evidence=(item,)),),
        )


def test_hypothetical_and_implemented_statuses_survive_serialization_roundtrip():
    implemented = evidence("chunk-implemented", status=ExperienceStatus.IMPLEMENTED)
    hypothetical = evidence("chunk-hypothetical", status=ExperienceStatus.HYPOTHETICAL)
    package = ResponsePackage(
        session_id="session-a",
        query_generation=3,
        mode=ResponseMode.CUE_ONLY,
        eligibility=eligibility(script_eligible=False),
        evidence=(implemented, hypothetical),
        cues=(
            ResponseCue("Implemented example.", evidence=(implemented,)),
            ResponseCue("Proposed approach.", evidence=(hypothetical,)),
        ),
    )

    restored = ResponsePackage.from_dict(package.to_dict())

    assert restored == package
    assert restored.experience_statuses == (
        ExperienceStatus.IMPLEMENTED,
        ExperienceStatus.HYPOTHETICAL,
    )
    assert restored.cues[1].evidence[0].experience_status is ExperienceStatus.HYPOTHETICAL


def test_clarification_and_unavailable_are_explicit_valid_modes():
    clarification = ResponsePackage(
        session_id="session-a",
        query_generation=4,
        mode=ResponseMode.CLARIFICATION,
        eligibility=eligibility(script_eligible=False, confidence=0.3),
        clarification="Do you mean the retrieval architecture or the deployment model?",
    )
    unavailable = ResponsePackage(
        session_id="session-a",
        query_generation=5,
        mode=ResponseMode.UNAVAILABLE,
        eligibility=eligibility(script_eligible=False, confidence=0.0),
        detail="No trustworthy supporting evidence is available.",
    )

    assert clarification.mode is ResponseMode.CLARIFICATION
    assert unavailable.mode is ResponseMode.UNAVAILABLE


def test_duplicate_package_evidence_is_rejected():
    item = evidence()
    with pytest.raises(ValueError, match="must be unique"):
        ResponsePackage(
            session_id="session-a",
            query_generation=6,
            mode=ResponseMode.CUE_ONLY,
            eligibility=eligibility(script_eligible=False),
            evidence=(item, item),
            cues=(ResponseCue("Use the example.", evidence=(item,)),),
        )


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_eligibility_confidence_is_bounded(confidence):
    with pytest.raises(ValueError, match="between 0 and 1"):
        eligibility(confidence=confidence)
