from __future__ import annotations

import threading

import numpy as np

from interview_copilot.cue_retrieval import (
    CueRetrievalConfig,
    CueState,
    InterviewCue,
    InterviewCueRetriever,
    LatestQueryWinsWorker,
)
from interview_copilot.knowledge.models import (
    ExperienceStatus,
    KnowledgeChunk,
    SearchResult,
)
from interview_copilot.query_boundaries import BoundaryReason, QueryCandidate


class FakeEmbedder:
    model_id = "fixture-v1"
    dimension = 3

    def embed_query(self, text: str) -> np.ndarray:
        return np.asarray([1.0, 0.0, 0.0], dtype=np.float32)


class FakeStore:
    provider_name = "fake"

    def __init__(self, results: list[SearchResult] | None = None, *, fail: bool = False):
        self.results = results or []
        self.fail = fail
        self.requests = []

    def query(self, request):
        self.requests.append(request)
        if self.fail:
            raise RuntimeError("secret database url should not escape")
        return self.results[: request.top_k]


def candidate(generation: int = 1, text: str = "How did you use Ruff?") -> QueryCandidate:
    return QueryCandidate(
        session_id="session-a",
        generation=generation,
        text=text,
        boundary_reason=BoundaryReason.MANUAL,
        first_order=generation,
        last_order=generation,
        started_at=0.0,
        completed_at=1.0,
    )


def result(
    chunk_id: str,
    score: float,
    *,
    status: ExperienceStatus = ExperienceStatus.IMPLEMENTED,
    content: str = "Built a production validation workflow.",
    project: str | None = "agentic-sdlc",
    skills: tuple[str, ...] = (),
    topics: tuple[str, ...] = (),
    collection: str = "career",
) -> SearchResult:
    return SearchResult(
        score=score,
        collection=collection,
        chunk=KnowledgeChunk(
            chunk_id=chunk_id,
            source_uri=f"projects/{chunk_id}.md",
            ordinal=0,
            content=content,
            content_hash=f"hash-{chunk_id}",
            title=f"Story {chunk_id}",
            experience_status=status,
            project=project,
            topics=topics,
            skills=skills,
            metadata={"fixture": True},
        ),
    )


def test_queries_explicit_configured_scopes_and_preserves_embedding_identity():
    store = FakeStore([result("one", 0.8)])
    retriever = InterviewCueRetriever(
        store,
        FakeEmbedder(),
        CueRetrievalConfig(collections=("career", "target-role")),
    )

    cue = retriever.retrieve(candidate())

    assert cue.state is CueState.READY
    request = store.requests[0]
    assert request.collections == ("career", "target-role")
    assert request.embedding_model == "fixture-v1"
    assert request.embedding == (1.0, 0.0, 0.0)


def test_exact_metadata_terms_can_reinforce_semantic_ranking():
    store = FakeStore(
        [
            result("semantic", 0.50, content="Built a general quality workflow."),
            result("ruff", 0.46, content="Introduced automated checks.", skills=("Ruff",)),
        ]
    )
    retriever = InterviewCueRetriever(
        store,
        FakeEmbedder(),
        CueRetrievalConfig(metadata_boost=0.30, lexical_boost=0.0),
    )

    cue = retriever.retrieve(candidate(text="How did you use Ruff?"))

    assert cue.primary_story is not None
    assert cue.primary_story.chunk_id == "ruff"
    assert cue.primary_story.score > 0.50


def test_hypothetical_material_is_never_selected_as_primary_experience_story():
    store = FakeStore(
        [
            result(
                "future",
                0.95,
                status=ExperienceStatus.HYPOTHETICAL,
                content="Could apply this pattern to legal review.",
            ),
            result(
                "real",
                0.75,
                status=ExperienceStatus.IMPLEMENTED,
                content="Built the production retrieval workflow.",
            ),
        ]
    )
    retriever = InterviewCueRetriever(store, FakeEmbedder())

    cue = retriever.retrieve(candidate(text="How would you apply retrieval to legal review?"))

    assert cue.state is CueState.READY
    assert cue.primary_story is not None
    assert cue.primary_story.chunk_id == "real"
    assert cue.primary_story.experience_status is ExperienceStatus.IMPLEMENTED
    assert cue.role_bridge is not None
    assert cue.role_bridge.chunk_id == "future"
    assert cue.role_bridge.experience_status is ExperienceStatus.HYPOTHETICAL


def test_cue_output_is_bounded_and_every_point_retains_provenance_and_status():
    store = FakeStore(
        [
            result("primary", 0.9),
            result("support-1", 0.8, status=ExperienceStatus.DESIGN),
            result("support-2", 0.7, status=ExperienceStatus.IMPLEMENTED),
            result("support-3", 0.6, status=ExperienceStatus.PROTOTYPE),
            result("support-4", 0.5, status=ExperienceStatus.IMPLEMENTED),
        ]
    )
    retriever = InterviewCueRetriever(
        store,
        FakeEmbedder(),
        CueRetrievalConfig(max_supporting_points=2),
    )

    cue = retriever.retrieve(candidate(text="Tell me about architecture"))

    assert cue.primary_story is not None
    assert len(cue.supporting_points) <= 2
    evidence = (cue.primary_story, *cue.supporting_points)
    for item in evidence:
        assert item.source_uri.startswith("projects/")
        assert item.collection == "career"
        assert item.experience_status in ExperienceStatus


def test_low_quality_results_return_visible_no_match_state():
    store = FakeStore([result("weak", 0.02)])
    retriever = InterviewCueRetriever(
        store,
        FakeEmbedder(),
        CueRetrievalConfig(min_score=0.50, lexical_boost=0.0, metadata_boost=0.0),
    )

    cue = retriever.retrieve(candidate(text="Unrelated question"))

    assert cue.state is CueState.NO_MATCH
    assert cue.primary_story is None
    assert cue.supporting_points == ()
    assert cue.detail == "no sufficiently relevant evidence"


def test_provider_failure_returns_secret_safe_unavailable_state():
    retriever = InterviewCueRetriever(FakeStore(fail=True), FakeEmbedder())

    cue = retriever.retrieve(candidate())

    assert cue.state is CueState.UNAVAILABLE
    assert cue.detail == "retrieval unavailable (RuntimeError)"
    assert "database" not in cue.detail
    assert "secret" not in cue.detail


class BlockingRetriever:
    def __init__(self) -> None:
        self.config = CueRetrievalConfig(worker_queue_size=1)
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls: list[int] = []

    def retrieve(self, item: QueryCandidate) -> InterviewCue:
        self.calls.append(item.generation)
        if item.generation == 1:
            self.started.set()
            assert self.release.wait(timeout=2.0)
        return InterviewCue(
            session_id=item.session_id,
            generation=item.generation,
            question=item.text,
            intent=item.text,
            state=CueState.READY,
        )


def test_latest_query_wins_suppresses_stale_result_and_bounds_pending_work():
    retriever = BlockingRetriever()
    published: list[int] = []
    published_event = threading.Event()

    def on_cue(cue: InterviewCue) -> None:
        published.append(cue.generation)
        published_event.set()

    worker = LatestQueryWinsWorker(retriever, on_cue)
    try:
        worker.submit(candidate(1, "first"))
        assert retriever.started.wait(timeout=2.0)

        worker.submit(candidate(2, "second"))
        worker.submit(candidate(3, "third"))
        retriever.release.set()

        assert published_event.wait(timeout=2.0)
        assert published == [3]
        assert retriever.calls == [1, 3]
    finally:
        retriever.release.set()
        worker.close()


def test_worker_rejects_submit_after_close():
    retriever = BlockingRetriever()
    worker = LatestQueryWinsWorker(retriever, lambda cue: None)
    worker.close()

    try:
        worker.submit(candidate())
    except RuntimeError as exc:
        assert str(exc) == "retrieval worker is closed"
    else:
        raise AssertionError("closed worker accepted new work")
