from __future__ import annotations

import importlib
import threading
from dataclasses import dataclass
from enum import StrEnum
from types import SimpleNamespace

from interview_copilot.cue_retrieval import CueRetrievalConfig, InterviewCue
from interview_copilot.knowledge.embeddings import DeterministicHashEmbedding
from interview_copilot.knowledge.models import (
    ExperienceStatus,
    KnowledgeChunk,
    SearchResult,
    StoreHealth,
    StoreStats,
)
from interview_copilot.query_boundaries import BoundaryConfig, RemoteUtteranceAssembler
from interview_copilot.session import (
    HearsayHostAdapter,
    HostPreflight,
    HostSessionPolicy,
    InterviewCopilotSession,
    SessionState,
)


@dataclass(frozen=True)
class FakeHostEvent:
    session_id: str
    sequence: int
    source: str
    text: str
    final: bool = True


class FakeSubscription:
    def __init__(self, name: str, closed: list[str]) -> None:
        self.name = name
        self.closed = closed
        self.is_closed = False

    def close(self) -> None:
        if not self.is_closed:
            self.is_closed = True
            self.closed.append(self.name)


class FakeHost:
    def __init__(self, *, fail_local_registration: bool = False) -> None:
        self.policy: HostSessionPolicy | None = None
        self.handlers: dict[str, object] = {}
        self.closed: list[str] = []
        self.fail_local_registration = fail_local_registration

    def preflight(self, policy: HostSessionPolicy) -> HostPreflight:
        self.policy = policy
        return HostPreflight(
            ok=True,
            output_mode="live-only",
            transcription_profile="live",
            detail="fake Hearsay ready",
        )

    def register_transcript_handler(
        self,
        name: str,
        handler: object,
        *,
        sources: tuple[str, ...],
        queue_size: int,
    ) -> FakeSubscription:
        assert queue_size > 0
        source = sources[0]
        if source == "Local" and self.fail_local_registration:
            raise RuntimeError("local registration failed")
        self.handlers[source] = handler
        return FakeSubscription(name, self.closed)

    def emit(self, event: FakeHostEvent) -> None:
        handler = self.handlers.get(event.source)
        if handler is not None:
            handler(event)


class FakeStore:
    provider_name = "fake"

    def __init__(self, *, healthy: bool = True, chunks: int = 1) -> None:
        self.healthy = healthy
        self.chunks = chunks
        self.query_count = 0
        self.closed = False
        self._chunk = KnowledgeChunk(
            chunk_id="chunk-1",
            source_uri="career://rag",
            ordinal=0,
            content="Built a source-code RAG system exposed through an MCP server.",
            content_hash="hash",
            title="Source-code RAG",
            experience_status=ExperienceStatus.IMPLEMENTED,
            project="DataFactory",
            topics=("rag", "mcp"),
            skills=("python",),
            metadata={},
        )

    def health(self) -> StoreHealth:
        return StoreHealth(healthy=self.healthy, provider="fake", detail=None)

    def stats(self, collections: tuple[str, ...] | None = None) -> StoreStats:
        assert collections is not None
        return StoreStats(collections=1, documents=1, chunks=self.chunks)

    def query(self, request: object) -> list[SearchResult]:
        self.query_count += 1
        return [SearchResult(score=0.9, collection="career", chunk=self._chunk)]

    def close(self) -> None:
        self.closed = True


class FakeOverlay:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []
        self.cues: list[InterviewCue] = []
        self.cue_ready = threading.Event()

    def begin_session(self, session_id: str) -> None:
        self.calls.append(("begin", session_id))

    def set_listening(self, session_id: str) -> None:
        self.calls.append(("listening", session_id))

    def set_retrieving(self, session_id: str, generation: int, question: str) -> None:
        self.calls.append(("retrieving", session_id, generation, question))

    def publish_cue(self, cue: InterviewCue) -> None:
        self.cues.append(cue)
        self.calls.append(("cue", cue.session_id, cue.generation, cue.state.value))
        self.cue_ready.set()

    def clear(self) -> None:
        self.calls.append(("clear",))


class FailingPublishOverlay(FakeOverlay):
    def publish_cue(self, cue: InterviewCue) -> None:
        self.cue_ready.set()
        raise RuntimeError("overlay unavailable")


def _session(
    *,
    host: FakeHost | None = None,
    store: FakeStore | None = None,
    overlay: FakeOverlay | None = None,
    on_local_segment: object | None = None,
) -> tuple[InterviewCopilotSession, FakeHost, FakeStore, FakeOverlay]:
    fake_host = host or FakeHost()
    fake_store = store or FakeStore()
    fake_overlay = overlay or FakeOverlay()
    assembler = RemoteUtteranceAssembler(
        BoundaryConfig(punctuation_debounce_seconds=0.0, pause_seconds=60.0)
    )
    session = InterviewCopilotSession(
        store=fake_store,
        embedder=DeterministicHashEmbedding(),
        overlay=fake_overlay,
        host=fake_host,
        assembler=assembler,
        cue_config=CueRetrievalConfig(collections=("career",), min_score=0.1),
        on_local_segment=on_local_segment,
    )
    return session, fake_host, fake_store, fake_overlay


def test_synthetic_host_event_journey_routes_remote_only() -> None:
    local_segments: list[object] = []
    session, host, store, overlay = _session(on_local_segment=local_segments.append)

    result = session.start("session-1")

    assert result.started
    assert session.state is SessionState.LISTENING
    assert host.policy == HostSessionPolicy()
    assert set(host.handlers) == {"Remote", "Local"}

    host.emit(FakeHostEvent("session-1", 1, "Remote", "Tell me about your RAG system?"))
    assert session.poll() == 1
    assert overlay.cue_ready.wait(2.0)
    assert len(overlay.cues) == 1
    assert overlay.cues[0].question == "Tell me about your RAG system?"
    assert overlay.cues[0].primary_story is not None
    assert store.query_count == 1

    host.emit(FakeHostEvent("session-1", 2, "Local", "I built a source-code RAG system."))
    assert len(local_segments) == 1
    assert store.query_count == 1

    host.emit(FakeHostEvent("old-session", 3, "Remote", "This must be ignored?"))
    assert session.poll() == 0
    assert store.query_count == 1

    session.stop()
    assert session.state is SessionState.STOPPED
    assert store.closed
    assert host.closed == ["interview-copilot-local", "interview-copilot-remote"]
    assert overlay.calls[-1] == ("clear",)


def test_manual_retrieval_flushes_current_remote_buffer() -> None:
    session, host, store, overlay = _session()
    assert session.start("session-1").started

    host.emit(FakeHostEvent("session-1", 1, "Remote", "Tell me about MCP"))

    assert session.retrieve_current_remote_buffer()
    assert overlay.cue_ready.wait(2.0)
    assert store.query_count == 1
    assert overlay.cues[0].question == "Tell me about MCP"
    assert not session.retrieve_current_remote_buffer()

    session.stop()


def test_preflight_requires_healthy_indexed_knowledge_provider() -> None:
    session, host, _, _ = _session(store=FakeStore(healthy=False, chunks=0))

    result = session.start("session-1")

    assert not result.started
    assert result.state is SessionState.PREFLIGHT_FAILED
    assert host.handlers == {}
    assert any(
        check.name == "knowledge_store" and not check.ok for check in result.preflight.checks
    )


def test_overlay_failure_degrades_consumer_without_stopping_host() -> None:
    overlay = FailingPublishOverlay()
    session, host, store, _ = _session(overlay=overlay)
    assert session.start("session-1").started

    host.emit(FakeHostEvent("session-1", 1, "Remote", "Tell me about RAG?"))
    assert session.poll() == 1
    assert overlay.cue_ready.wait(2.0)

    assert session.state is SessionState.DEGRADED
    assert store.query_count == 1
    assert set(host.handlers) == {"Remote", "Local"}
    assert not any(subscription.endswith("remote") for subscription in host.closed)

    session.stop()


def test_partial_host_attachment_is_rolled_back() -> None:
    host = FakeHost(fail_local_registration=True)
    session, _, _, overlay = _session(host=host)

    result = session.start("session-1")

    assert not result.started
    assert result.state is SessionState.PREFLIGHT_FAILED
    assert host.closed == ["interview-copilot-remote"]
    assert overlay.calls[-1] == ("clear",)


def test_hearsay_adapter_uses_only_public_contract(monkeypatch: object) -> None:
    registrations: list[tuple[object, ...]] = []

    class HostSource(StrEnum):
        REMOTE = "Remote"
        LOCAL = "Local"

    class OutputMode(StrEnum):
        LIVE_ONLY = "live-only"

    def register(
        name: str,
        handler: object,
        *,
        sources: list[HostSource],
        queue_size: int,
    ) -> object:
        registrations.append((name, handler, tuple(sources), queue_size))
        return SimpleNamespace(close=lambda: None)

    events_module = SimpleNamespace(
        TranscriptSource=HostSource,
        register_transcript_handler=register,
    )
    host_module = SimpleNamespace(
        SessionOutputMode=OutputMode,
        LIVE_TRANSCRIPTION_PROFILE=SimpleNamespace(name="live"),
    )
    original_import = importlib.import_module

    def fake_import(name: str) -> object:
        if name == "hearsay.events":
            return events_module
        if name == "hearsay.host":
            return host_module
        return original_import(name)

    monkeypatch.setattr(importlib, "import_module", fake_import)
    adapter = HearsayHostAdapter()

    preflight = adapter.preflight(HostSessionPolicy())
    subscription = adapter.register_transcript_handler(
        "consumer",
        lambda event: None,
        sources=("Remote",),
        queue_size=8,
    )

    assert preflight.ok
    assert preflight.output_mode == "live-only"
    assert preflight.transcription_profile == "live"
    assert registrations[0][0] == "consumer"
    assert registrations[0][2] == (HostSource.REMOTE,)
    assert registrations[0][3] == 8
    subscription.close()
