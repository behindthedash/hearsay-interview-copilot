from __future__ import annotations

import importlib
import threading
from collections.abc import Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from types import ModuleType
from typing import Protocol

from .cue_retrieval import (
    CueRetrievalConfig,
    CueState,
    InterviewCue,
    InterviewCueRetriever,
    LatestQueryWinsWorker,
)
from .knowledge.embeddings import EmbeddingModel
from .knowledge.provider import KnowledgeStore
from .query_boundaries import (
    QueryCandidate,
    RemoteUtteranceAssembler,
    TranscriptSegment,
    TranscriptSource,
)


class SessionState(StrEnum):
    NEW = "new"
    PREFLIGHT_FAILED = "preflight_failed"
    READY = "ready"
    LISTENING = "listening"
    DEGRADED = "degraded"
    STOPPED = "stopped"


@dataclass(frozen=True)
class HostSessionPolicy:
    """Privacy-sensitive Hearsay policy requested by interview sessions."""

    output_mode: str = "live-only"
    transcription_profile: str = "live"
    persist_transcript: bool = False

    def __post_init__(self) -> None:
        if not self.output_mode.strip() or not self.transcription_profile.strip():
            raise ValueError("host policy values must be non-empty")
        if self.persist_transcript and self.output_mode == "live-only":
            raise ValueError("live-only output cannot persist a transcript")


@dataclass(frozen=True)
class HostPreflight:
    ok: bool
    output_mode: str | None = None
    transcription_profile: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class PreflightResult:
    ok: bool
    checks: tuple[PreflightCheck, ...]
    requested_policy: HostSessionPolicy

    @property
    def failures(self) -> tuple[PreflightCheck, ...]:
        return tuple(check for check in self.checks if not check.ok)


@dataclass(frozen=True)
class SessionStartResult:
    started: bool
    preflight: PreflightResult
    state: SessionState
    detail: str | None = None


@dataclass(frozen=True)
class InterviewCopilotSessionConfig:
    subscription_prefix: str = "interview-copilot"
    subscription_queue_size: int = 100
    close_store_on_stop: bool = True
    host_policy: HostSessionPolicy = HostSessionPolicy()

    def __post_init__(self) -> None:
        if not self.subscription_prefix.strip():
            raise ValueError("subscription_prefix must be non-empty")
        if self.subscription_queue_size <= 0:
            raise ValueError("subscription_queue_size must be positive")


class TranscriptSubscriptionPort(Protocol):
    def close(self) -> None: ...


class HearsayHostPort(Protocol):
    def preflight(self, policy: HostSessionPolicy) -> HostPreflight: ...

    def register_transcript_handler(
        self,
        name: str,
        handler: Callable[[object], None],
        *,
        sources: Sequence[str],
        queue_size: int,
    ) -> TranscriptSubscriptionPort: ...


class CueOverlayPort(Protocol):
    def begin_session(self, session_id: str) -> None: ...

    def set_listening(self, session_id: str) -> None: ...

    def set_retrieving(self, session_id: str, generation: int, question: str) -> None: ...

    def publish_cue(self, cue: InterviewCue) -> None: ...

    def clear(self) -> None: ...


class HearsayHostAdapter:
    """Lazy adapter over Hearsay's documented public host/event imports.

    Hearsay currently exposes attach-mode transcript subscriptions and stable live
    policy constants, not a public function that starts the desktop host. This
    adapter therefore validates the requested policy and attaches handlers only.
    """

    def __init__(self) -> None:
        self._events: ModuleType | None = None

    def preflight(self, policy: HostSessionPolicy) -> HostPreflight:
        try:
            events = importlib.import_module("hearsay.events")
            host = importlib.import_module("hearsay.host")
            register = events.register_transcript_handler
            transcript_source = events.TranscriptSource
            output_mode = host.SessionOutputMode.LIVE_ONLY
            live_profile = host.LIVE_TRANSCRIPTION_PROFILE
            remote = transcript_source.REMOTE
            local = transcript_source.LOCAL
            actual_profile = str(live_profile.name)
        except (ImportError, AttributeError) as exc:
            return HostPreflight(
                ok=False,
                detail=f"Hearsay public host API unavailable ({type(exc).__name__})",
            )

        actual_output_mode = _enum_value(output_mode)
        if not callable(register) or not _enum_value(remote) or not _enum_value(local):
            return HostPreflight(ok=False, detail="Hearsay transcript subscription API is incomplete")
        if actual_output_mode != policy.output_mode:
            return HostPreflight(
                ok=False,
                output_mode=actual_output_mode,
                transcription_profile=actual_profile,
                detail="Hearsay LIVE_ONLY policy does not match requested output mode",
            )
        if actual_profile != policy.transcription_profile:
            return HostPreflight(
                ok=False,
                output_mode=actual_output_mode,
                transcription_profile=actual_profile,
                detail="Hearsay live transcription profile does not match requested profile",
            )
        if policy.persist_transcript:
            return HostPreflight(
                ok=False,
                output_mode=actual_output_mode,
                transcription_profile=actual_profile,
                detail="interview attach mode requires live-only/no-save behavior",
            )

        self._events = events
        return HostPreflight(
            ok=True,
            output_mode=actual_output_mode,
            transcription_profile=actual_profile,
            detail="public transcript subscriptions and live-only policy are available",
        )

    def register_transcript_handler(
        self,
        name: str,
        handler: Callable[[object], None],
        *,
        sources: Sequence[str],
        queue_size: int,
    ) -> TranscriptSubscriptionPort:
        if self._events is None:
            result = self.preflight(HostSessionPolicy())
            if not result.ok:
                raise RuntimeError(result.detail or "Hearsay public host API unavailable")
        assert self._events is not None
        transcript_source = self._events.TranscriptSource
        source_values = [transcript_source(source) for source in sources]
        register = self._events.register_transcript_handler
        return register(name, handler, sources=source_values, queue_size=queue_size)


class InterviewCopilotSession:
    """Consumer-owned orchestration for one attached live interview session."""

    def __init__(
        self,
        *,
        store: KnowledgeStore,
        embedder: EmbeddingModel,
        overlay: CueOverlayPort,
        host: HearsayHostPort | None = None,
        assembler: RemoteUtteranceAssembler | None = None,
        cue_config: CueRetrievalConfig | None = None,
        config: InterviewCopilotSessionConfig | None = None,
        on_local_segment: Callable[[TranscriptSegment], None] | None = None,
    ) -> None:
        self.store = store
        self.embedder = embedder
        self.overlay = overlay
        self.host = host or HearsayHostAdapter()
        self.assembler = assembler or RemoteUtteranceAssembler()
        self.cue_config = cue_config or CueRetrievalConfig()
        self.config = config or InterviewCopilotSessionConfig()
        self.on_local_segment = on_local_segment

        self._lock = threading.RLock()
        self._state = SessionState.NEW
        self._session_id: str | None = None
        self._latest_generation = 0
        self._accepting_results = False
        self._detail: str | None = None
        self._worker: LatestQueryWinsWorker | None = None
        self._remote_subscription: TranscriptSubscriptionPort | None = None
        self._local_subscription: TranscriptSubscriptionPort | None = None
        self._last_preflight: PreflightResult | None = None

    @property
    def state(self) -> SessionState:
        with self._lock:
            return self._state

    @property
    def session_id(self) -> str | None:
        with self._lock:
            return self._session_id

    @property
    def detail(self) -> str | None:
        with self._lock:
            return self._detail

    @property
    def last_preflight(self) -> PreflightResult | None:
        return self._last_preflight

    def preflight(self) -> PreflightResult:
        checks = (
            self._preflight_host(),
            self._preflight_store(),
            self._preflight_embedder(),
            self._preflight_overlay(),
        )
        result = PreflightResult(
            ok=all(check.ok for check in checks),
            checks=checks,
            requested_policy=self.config.host_policy,
        )
        self._last_preflight = result
        with self._lock:
            self._state = SessionState.READY if result.ok else SessionState.PREFLIGHT_FAILED
            self._detail = None if result.ok else "; ".join(check.detail for check in result.failures)
        return result

    def start(self, session_id: str) -> SessionStartResult:
        session_id = session_id.strip()
        if not session_id:
            raise ValueError("session_id must be non-empty")
        with self._lock:
            if self._accepting_results:
                raise RuntimeError("interview copilot session is already running")

        preflight = self.preflight()
        if not preflight.ok:
            return SessionStartResult(
                started=False,
                preflight=preflight,
                state=SessionState.PREFLIGHT_FAILED,
                detail=self.detail,
            )

        retriever = InterviewCueRetriever(self.store, self.embedder, self.cue_config)
        worker = LatestQueryWinsWorker(retriever, self._on_cue)
        remote_subscription: TranscriptSubscriptionPort | None = None
        local_subscription: TranscriptSubscriptionPort | None = None
        try:
            self.assembler.begin_session(session_id)
            self.overlay.begin_session(session_id)
            remote_subscription = self.host.register_transcript_handler(
                f"{self.config.subscription_prefix}-remote",
                self._on_remote_event,
                sources=(TranscriptSource.REMOTE.value,),
                queue_size=self.config.subscription_queue_size,
            )
            local_subscription = self.host.register_transcript_handler(
                f"{self.config.subscription_prefix}-local",
                self._on_local_event,
                sources=(TranscriptSource.LOCAL.value,),
                queue_size=self.config.subscription_queue_size,
            )
            self.overlay.set_listening(session_id)
        except Exception as exc:
            worker.close()
            if local_subscription is not None:
                with suppress(Exception):
                    local_subscription.close()
            if remote_subscription is not None:
                with suppress(Exception):
                    remote_subscription.close()
            self.assembler.teardown()
            with suppress(Exception):
                self.overlay.clear()
            with self._lock:
                self._state = SessionState.PREFLIGHT_FAILED
                self._detail = f"host attachment failed ({type(exc).__name__})"
            return SessionStartResult(
                started=False,
                preflight=preflight,
                state=SessionState.PREFLIGHT_FAILED,
                detail=self.detail,
            )

        with self._lock:
            self._session_id = session_id
            self._latest_generation = 0
            self._accepting_results = True
            self._worker = worker
            self._remote_subscription = remote_subscription
            self._local_subscription = local_subscription
            self._state = SessionState.LISTENING
            self._detail = None
        return SessionStartResult(
            started=True,
            preflight=preflight,
            state=SessionState.LISTENING,
        )

    def poll(self) -> int:
        if not self._is_running():
            return 0
        try:
            candidates = self.assembler.poll()
        except Exception as exc:
            self._mark_degraded(f"question boundary polling failed ({type(exc).__name__})")
            return 0
        for candidate in candidates:
            self._submit_candidate(candidate)
        return len(candidates)

    def retrieve_current_remote_buffer(self) -> bool:
        """Manually turn the current Remote buffer into a retrieval query."""
        if not self._is_running():
            return False
        try:
            candidates = self.assembler.manual_flush()
        except Exception as exc:
            self._mark_degraded(f"manual query flush failed ({type(exc).__name__})")
            return False
        for candidate in candidates:
            self._submit_candidate(candidate)
        return bool(candidates)

    def stop(self) -> None:
        with self._lock:
            self._accepting_results = False
            worker = self._worker
            local_subscription = self._local_subscription
            remote_subscription = self._remote_subscription
            self._worker = None
            self._local_subscription = None
            self._remote_subscription = None

        if worker is not None:
            with suppress(Exception):
                worker.close()
        if local_subscription is not None:
            with suppress(Exception):
                local_subscription.close()
        if remote_subscription is not None:
            with suppress(Exception):
                remote_subscription.close()

        self.assembler.teardown()
        with suppress(Exception):
            self.overlay.clear()
        if self.config.close_store_on_stop:
            close = getattr(self.store, "close", None)
            if callable(close):
                with suppress(Exception):
                    close()

        with self._lock:
            self._session_id = None
            self._latest_generation = 0
            self._state = SessionState.STOPPED
            self._detail = None

    def _preflight_host(self) -> PreflightCheck:
        try:
            result = self.host.preflight(self.config.host_policy)
        except Exception as exc:
            return PreflightCheck(
                name="hearsay_host",
                ok=False,
                detail=f"Hearsay host preflight failed ({type(exc).__name__})",
            )
        policy_matches = (
            result.output_mode == self.config.host_policy.output_mode
            and result.transcription_profile == self.config.host_policy.transcription_profile
        )
        ok = result.ok and policy_matches and not self.config.host_policy.persist_transcript
        return PreflightCheck(
            name="hearsay_host",
            ok=ok,
            detail=result.detail or ("Hearsay host ready" if ok else "Hearsay live policy unavailable"),
        )

    def _preflight_store(self) -> PreflightCheck:
        try:
            health = self.store.health()
            stats = self.store.stats(self.cue_config.collections)
        except Exception as exc:
            return PreflightCheck(
                name="knowledge_store",
                ok=False,
                detail=f"knowledge provider unavailable ({type(exc).__name__})",
            )
        ok = bool(health.healthy and stats.chunks > 0)
        detail = (
            f"{health.provider} ready with {stats.chunks} indexed chunks"
            if ok
            else health.detail or "knowledge provider has no indexed chunks"
        )
        return PreflightCheck(name="knowledge_store", ok=ok, detail=detail)

    def _preflight_embedder(self) -> PreflightCheck:
        try:
            vector = self.embedder.embed_query("interview copilot preflight")
            size = len(vector)
            dimension = int(self.embedder.dimension)
            model_id = self.embedder.model_id
        except Exception as exc:
            return PreflightCheck(
                name="embedding_model",
                ok=False,
                detail=f"embedding model unavailable ({type(exc).__name__})",
            )
        ok = bool(model_id.strip() and dimension > 0 and size == dimension)
        return PreflightCheck(
            name="embedding_model",
            ok=ok,
            detail=(
                f"{model_id} warmed with dimension {dimension}"
                if ok
                else "embedding model returned an incompatible vector"
            ),
        )

    def _preflight_overlay(self) -> PreflightCheck:
        required = (
            "begin_session",
            "set_listening",
            "set_retrieving",
            "publish_cue",
            "clear",
        )
        missing = tuple(
            name for name in required if not callable(getattr(self.overlay, name, None))
        )
        return PreflightCheck(
            name="overlay",
            ok=not missing,
            detail=(
                "cue overlay presentation contract ready"
                if not missing
                else f"cue overlay missing methods: {', '.join(missing)}"
            ),
        )

    def _on_remote_event(self, event: object) -> None:
        if not self._is_running():
            return
        try:
            segment = _segment_from_host_event(event)
        except (TypeError, ValueError, AttributeError) as exc:
            self._mark_degraded(f"invalid Remote transcript event ({type(exc).__name__})")
            return
        if segment.source is not TranscriptSource.REMOTE or not self._matches_session(segment.session_id):
            return
        try:
            candidates = self.assembler.ingest(segment)
        except Exception as exc:
            self._mark_degraded(f"question assembly failed ({type(exc).__name__})")
            return
        for candidate in candidates:
            self._submit_candidate(candidate)

    def _on_local_event(self, event: object) -> None:
        if not self._is_running():
            return
        try:
            segment = _segment_from_host_event(event)
        except (TypeError, ValueError, AttributeError) as exc:
            self._mark_degraded(f"invalid Local transcript event ({type(exc).__name__})")
            return
        if segment.source is not TranscriptSource.LOCAL or not self._matches_session(segment.session_id):
            return
        if self.on_local_segment is not None:
            try:
                self.on_local_segment(segment)
            except Exception as exc:
                self._mark_degraded(f"Local speech consumer failed ({type(exc).__name__})")

    def _submit_candidate(self, candidate: QueryCandidate) -> None:
        with self._lock:
            if (
                not self._accepting_results
                or candidate.session_id != self._session_id
                or candidate.generation <= self._latest_generation
            ):
                return
            self._latest_generation = candidate.generation
            worker = self._worker
        try:
            self.overlay.set_retrieving(candidate.session_id, candidate.generation, candidate.text)
        except Exception as exc:
            self._mark_degraded(f"overlay update failed ({type(exc).__name__})")
        if worker is None:
            self._mark_degraded("retrieval worker is unavailable")
            return
        try:
            worker.submit(candidate)
        except Exception as exc:
            self._mark_degraded(f"retrieval submission failed ({type(exc).__name__})")

    def _on_cue(self, cue: InterviewCue) -> None:
        with self._lock:
            if (
                not self._accepting_results
                or cue.session_id != self._session_id
                or cue.generation != self._latest_generation
            ):
                return
        try:
            self.overlay.publish_cue(cue)
        except Exception as exc:
            self._mark_degraded(f"overlay publication failed ({type(exc).__name__})")
            return
        if cue.state is CueState.UNAVAILABLE:
            self._mark_degraded(cue.detail or "retrieval unavailable")
        else:
            with self._lock:
                if self._accepting_results:
                    self._state = SessionState.LISTENING
                    self._detail = None

    def _is_running(self) -> bool:
        with self._lock:
            return self._accepting_results and self._session_id is not None

    def _matches_session(self, session_id: str) -> bool:
        with self._lock:
            return self._accepting_results and session_id == self._session_id

    def _mark_degraded(self, detail: str) -> None:
        with self._lock:
            if self._accepting_results:
                self._state = SessionState.DEGRADED
                self._detail = detail


def _segment_from_host_event(event: object) -> TranscriptSegment:
    session_id = str(event.session_id)
    text = str(event.text)
    sequence = int(event.sequence)
    source = TranscriptSource(_enum_value(event.source))
    final = bool(getattr(event, "final", True))
    return TranscriptSegment(
        session_id=session_id,
        source=source,
        text=text,
        order=sequence,
        is_final=final,
    )


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value))
