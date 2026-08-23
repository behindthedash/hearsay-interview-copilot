from __future__ import annotations

import queue
import re
import threading
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from .knowledge.embeddings import EmbeddingModel
from .knowledge.models import ExperienceStatus, QueryRequest, SearchResult
from .knowledge.provider import KnowledgeStore
from .query_boundaries import QueryCandidate

_TOKEN_PATTERN: Final = re.compile(r"[A-Za-z0-9_+#.-]+")
_PRIMARY_STATUSES: Final = frozenset({ExperienceStatus.IMPLEMENTED, ExperienceStatus.PROTOTYPE})
_BRIDGE_STATUSES: Final = frozenset({ExperienceStatus.DESIGN, ExperienceStatus.HYPOTHETICAL})
_SENTINEL: Final = object()


class CueState(StrEnum):
    READY = "ready"
    NO_MATCH = "no_match"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class CueEvidence:
    text: str
    source_uri: str
    title: str
    experience_status: ExperienceStatus
    collection: str
    chunk_id: str
    score: float
    project: str | None = None


@dataclass(frozen=True)
class InterviewCue:
    session_id: str
    generation: int
    question: str
    intent: str
    state: CueState
    primary_story: CueEvidence | None = None
    supporting_points: tuple[CueEvidence, ...] = ()
    role_bridge: CueEvidence | None = None
    confidence: float = 0.0
    latency_ms: float = 0.0
    detail: str | None = None


@dataclass(frozen=True)
class CueRetrievalConfig:
    collections: tuple[str, ...] = ("career",)
    semantic_top_k: int = 8
    max_supporting_points: int = 3
    min_score: float = 0.15
    lexical_boost: float = 0.12
    metadata_boost: float = 0.10
    worker_queue_size: int = 1

    def __post_init__(self) -> None:
        if not self.collections or any(not value.strip() for value in self.collections):
            raise ValueError("collections must contain at least one non-empty scope")
        if self.semantic_top_k <= 0:
            raise ValueError("semantic_top_k must be positive")
        if self.max_supporting_points < 0:
            raise ValueError("max_supporting_points must be non-negative")
        if self.worker_queue_size <= 0:
            raise ValueError("worker_queue_size must be positive")
        if self.lexical_boost < 0 or self.metadata_boost < 0:
            raise ValueError("ranking boosts must be non-negative")


class InterviewCueRetriever:
    """Retrieve and deterministically compose a concise cue for one query candidate."""

    def __init__(
        self,
        store: KnowledgeStore,
        embedder: EmbeddingModel,
        config: CueRetrievalConfig | None = None,
        *,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.store = store
        self.embedder = embedder
        self.config = config or CueRetrievalConfig()
        self._clock = clock

    def retrieve(self, candidate: QueryCandidate) -> InterviewCue:
        started = self._clock()
        try:
            vector = self.embedder.embed_query(candidate.text)
            results = self.store.query(
                QueryRequest(
                    collections=self.config.collections,
                    embedding_model=self.embedder.model_id,
                    embedding=tuple(float(value) for value in vector),
                    top_k=self.config.semantic_top_k,
                )
            )
        except Exception as exc:
            return self._terminal_cue(
                candidate,
                CueState.UNAVAILABLE,
                started,
                detail=f"retrieval unavailable ({type(exc).__name__})",
            )

        ranked = self._rerank(candidate.text, results)
        eligible = [item for item in ranked if item.score >= self.config.min_score]
        if not eligible:
            return self._terminal_cue(
                candidate,
                CueState.NO_MATCH,
                started,
                detail="no sufficiently relevant evidence",
            )

        primary_result = next(
            (
                result
                for result in eligible
                if result.result.chunk.experience_status in _PRIMARY_STATUSES
            ),
            None,
        )
        bridge_result = next(
            (
                result
                for result in eligible
                if result.result.chunk.experience_status in _BRIDGE_STATUSES
            ),
            None,
        )

        excluded_ids = {
            item.result.chunk.chunk_id
            for item in (primary_result, bridge_result)
            if item is not None
        }
        supporting = tuple(
            self._to_evidence(item)
            for item in eligible
            if item.result.chunk.chunk_id not in excluded_ids
        )[: self.config.max_supporting_points]

        top_score = eligible[0].score
        return InterviewCue(
            session_id=candidate.session_id,
            generation=candidate.generation,
            question=candidate.text,
            intent=candidate.text,
            state=CueState.READY,
            primary_story=(
                self._to_evidence(primary_result) if primary_result is not None else None
            ),
            supporting_points=supporting,
            role_bridge=(self._to_evidence(bridge_result) if bridge_result is not None else None),
            confidence=max(0.0, min(1.0, top_score)),
            latency_ms=self._elapsed_ms(started),
        )

    def _rerank(self, query: str, results: list[SearchResult]) -> list[_RankedResult]:
        query_tokens = _tokens(query)
        ranked: list[_RankedResult] = []
        for result in results:
            chunk = result.chunk
            content_tokens = _tokens(f"{chunk.title} {chunk.content}")
            metadata_tokens = _tokens(
                " ".join(
                    value
                    for value in (
                        chunk.project or "",
                        " ".join(chunk.topics),
                        " ".join(chunk.skills),
                    )
                    if value
                )
            )
            denominator = max(1, len(query_tokens))
            lexical_ratio = len(query_tokens & content_tokens) / denominator
            metadata_ratio = len(query_tokens & metadata_tokens) / denominator
            score = (
                float(result.score)
                + self.config.lexical_boost * lexical_ratio
                + self.config.metadata_boost * metadata_ratio
            )
            ranked.append(_RankedResult(result=result, score=score))

        return sorted(
            ranked,
            key=lambda item: (
                -item.score,
                item.result.collection,
                item.result.chunk.source_uri,
                item.result.chunk.ordinal,
            ),
        )

    def _to_evidence(self, item: _RankedResult) -> CueEvidence:
        chunk = item.result.chunk
        return CueEvidence(
            text=chunk.content,
            source_uri=chunk.source_uri,
            title=chunk.title,
            experience_status=chunk.experience_status,
            collection=item.result.collection,
            chunk_id=chunk.chunk_id,
            score=item.score,
            project=chunk.project,
        )

    def _terminal_cue(
        self,
        candidate: QueryCandidate,
        state: CueState,
        started: float,
        *,
        detail: str,
    ) -> InterviewCue:
        return InterviewCue(
            session_id=candidate.session_id,
            generation=candidate.generation,
            question=candidate.text,
            intent=candidate.text,
            state=state,
            latency_ms=self._elapsed_ms(started),
            detail=detail,
        )

    def _elapsed_ms(self, started: float) -> float:
        return max(0.0, (self._clock() - started) * 1000.0)


@dataclass(frozen=True)
class _RankedResult:
    result: SearchResult
    score: float


class LatestQueryWinsWorker:
    """Bounded background retrieval worker that never publishes stale generations."""

    def __init__(
        self,
        retriever: InterviewCueRetriever,
        on_cue: Callable[[InterviewCue], None],
        *,
        queue_size: int | None = None,
    ) -> None:
        self.retriever = retriever
        self.on_cue = on_cue
        self._queue: queue.Queue[QueryCandidate | object] = queue.Queue(
            maxsize=queue_size or retriever.config.worker_queue_size
        )
        self._lock = threading.Lock()
        self._latest_key: tuple[str, int] | None = None
        self._closed = False
        self._thread = threading.Thread(
            target=self._run,
            name="interview-cue-retrieval",
            daemon=True,
        )
        self._thread.start()

    def submit(self, candidate: QueryCandidate) -> None:
        key = (candidate.session_id, candidate.generation)
        with self._lock:
            if self._closed:
                raise RuntimeError("retrieval worker is closed")
            self._latest_key = key

        while True:
            try:
                self._queue.put_nowait(candidate)
                return
            except queue.Full:
                try:
                    self._queue.get_nowait()
                    self._queue.task_done()
                except queue.Empty:
                    continue

    def close(self, *, timeout: float = 2.0) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._latest_key = None

        while True:
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                break
        with suppress(queue.Full):
            self._queue.put_nowait(_SENTINEL)
        self._thread.join(timeout=timeout)

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if item is _SENTINEL:
                    return
                candidate = item
                if not isinstance(candidate, QueryCandidate):
                    continue
                cue = self.retriever.retrieve(candidate)
                key = (candidate.session_id, candidate.generation)
                with self._lock:
                    publish = not self._closed and self._latest_key == key
                if publish:
                    with suppress(Exception):
                        self.on_cue(cue)
            finally:
                self._queue.task_done()


def _tokens(text: str) -> set[str]:
    return {token.casefold() for token in _TOKEN_PATTERN.findall(text) if len(token) > 1}
