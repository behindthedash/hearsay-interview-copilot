from __future__ import annotations

import importlib
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from types import ModuleType
from typing import Protocol


class LocalSpeechProviderHealth(StrEnum):
    STOPPED = "stopped"
    HEALTHY = "healthy"
    DEGRADED = "degraded"


class LocalSpeechSignalKind(StrEnum):
    FINALIZED = "finalized"
    STREAMING = "streaming"


@dataclass(frozen=True)
class LocalSpeechSignal:
    """Consumer-owned speech input that is structurally Local-only.

    There is intentionally no Remote/source discriminator on this type. Providers may
    create it only after establishing that speech belongs to the local user.
    """

    provider_name: str
    session_id: str
    sequence: int
    text: str
    received_at: float
    final: bool = True
    start_time: float | None = None
    end_time: float | None = None
    recognition_latency_ms: float | None = None

    def __post_init__(self) -> None:
        if not self.provider_name.strip():
            raise ValueError("provider_name must be non-empty")
        if not self.session_id.strip():
            raise ValueError("session_id must be non-empty")
        if self.sequence < 0:
            raise ValueError("sequence must be non-negative")
        if not self.text.strip():
            raise ValueError("text must be non-empty")
        if self.received_at < 0:
            raise ValueError("received_at must be non-negative")
        if self.recognition_latency_ms is not None and self.recognition_latency_ms < 0:
            raise ValueError("recognition_latency_ms must be non-negative")


@dataclass(frozen=True)
class LocalSpeechProviderDiagnostics:
    provider_name: str
    health: LocalSpeechProviderHealth
    signal_kind: LocalSpeechSignalKind
    running: bool
    active_session_id: str | None
    nominal_window_ms: float | None
    emitted: int
    ignored_stale: int
    ignored_non_local: int
    ignored_non_final: int
    ignored_empty: int
    handler_failures: int
    transport_dropped: int
    transport_failures: int
    last_signal_at: float | None
    latency_samples: int
    last_latency_ms: float | None
    average_latency_ms: float | None


class LocalSpeechSignalHandler(Protocol):
    def __call__(self, signal: LocalSpeechSignal) -> None: ...


class LocalSpeechSignalProvider(Protocol):
    """Alignment-facing Local speech provider contract."""

    @property
    def provider_name(self) -> str: ...

    def start(self, session_id: str, handler: LocalSpeechSignalHandler) -> None: ...

    def stop(self) -> None: ...

    def diagnostics(self) -> LocalSpeechProviderDiagnostics: ...


class _SubscriptionPort(Protocol):
    def close(self) -> None: ...

    def diagnostics(self) -> object: ...


@dataclass(frozen=True)
class HearsayLocalSpeechProviderConfig:
    subscription_name: str = "interview-copilot-local-speech"
    queue_size: int = 100

    def __post_init__(self) -> None:
        if not self.subscription_name.strip():
            raise ValueError("subscription_name must be non-empty")
        if self.queue_size <= 0:
            raise ValueError("queue_size must be positive")


class HearsayLocalSpeechProvider:
    """Adapter over Hearsay's supported finalized Local transcript subscription API."""

    provider_name = "hearsay-finalized-local"

    def __init__(
        self,
        config: HearsayLocalSpeechProviderConfig | None = None,
        *,
        events_module: ModuleType | object | None = None,
        host_module: ModuleType | object | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config or HearsayLocalSpeechProviderConfig()
        self._events_module = events_module
        self._host_module = host_module
        self._clock = clock
        self._lock = threading.RLock()
        self._subscription: _SubscriptionPort | None = None
        self._handler: LocalSpeechSignalHandler | None = None
        self._active_session_id: str | None = None
        self._epoch = 0
        self._nominal_window_ms: float | None = None
        self._emitted = 0
        self._ignored_stale = 0
        self._ignored_non_local = 0
        self._ignored_non_final = 0
        self._ignored_empty = 0
        self._handler_failures = 0
        self._last_signal_at: float | None = None
        self._latency_samples = 0
        self._latency_total_ms = 0.0
        self._last_latency_ms: float | None = None

    def start(self, session_id: str, handler: LocalSpeechSignalHandler) -> None:
        if not session_id.strip():
            raise ValueError("session_id must be non-empty")
        if not callable(handler):
            raise TypeError("handler must be callable")

        events, host = self._public_modules()
        transcript_source = events.TranscriptSource
        local_source = transcript_source.LOCAL
        register = events.register_transcript_handler
        live_profile = host.LIVE_TRANSCRIPTION_PROFILE
        nominal_window_ms = float(live_profile.chunk_duration_s) * 1000.0

        with self._lock:
            if self._subscription is not None:
                raise RuntimeError("Local speech provider is already running")
            self._epoch += 1
            epoch = self._epoch
            self._active_session_id = session_id
            self._handler = handler
            self._nominal_window_ms = nominal_window_ms

        try:
            subscription = register(
                self.config.subscription_name,
                lambda event: self._handle_hearsay_event(event, epoch),
                sources=[local_source],
                queue_size=self.config.queue_size,
            )
        except Exception:
            with self._lock:
                if self._epoch == epoch:
                    self._active_session_id = None
                    self._handler = None
                    self._nominal_window_ms = None
            raise

        with self._lock:
            if self._epoch != epoch or self._active_session_id != session_id:
                subscription.close()
                raise RuntimeError("Local speech provider start was superseded")
            self._subscription = subscription

    def stop(self) -> None:
        with self._lock:
            self._epoch += 1
            subscription = self._subscription
            self._subscription = None
            self._handler = None
            self._active_session_id = None
        if subscription is not None:
            subscription.close()

    def diagnostics(self) -> LocalSpeechProviderDiagnostics:
        with self._lock:
            subscription = self._subscription
            emitted = self._emitted
            ignored_stale = self._ignored_stale
            ignored_non_local = self._ignored_non_local
            ignored_non_final = self._ignored_non_final
            ignored_empty = self._ignored_empty
            handler_failures = self._handler_failures
            last_signal_at = self._last_signal_at
            latency_samples = self._latency_samples
            latency_total_ms = self._latency_total_ms
            last_latency_ms = self._last_latency_ms
            active_session_id = self._active_session_id
            nominal_window_ms = self._nominal_window_ms

        transport_dropped = 0
        transport_failures = 0
        if subscription is not None:
            try:
                transport = subscription.diagnostics()
                transport_dropped = int(getattr(transport, "dropped", 0))
                transport_failures = int(getattr(transport, "failures", 0))
            except Exception:
                transport_failures += 1

        running = subscription is not None and active_session_id is not None
        degraded = handler_failures > 0 or transport_dropped > 0 or transport_failures > 0
        if not running:
            health = LocalSpeechProviderHealth.STOPPED
        elif degraded:
            health = LocalSpeechProviderHealth.DEGRADED
        else:
            health = LocalSpeechProviderHealth.HEALTHY

        average_latency_ms = latency_total_ms / latency_samples if latency_samples else None
        return LocalSpeechProviderDiagnostics(
            provider_name=self.provider_name,
            health=health,
            signal_kind=LocalSpeechSignalKind.FINALIZED,
            running=running,
            active_session_id=active_session_id,
            nominal_window_ms=nominal_window_ms,
            emitted=emitted,
            ignored_stale=ignored_stale,
            ignored_non_local=ignored_non_local,
            ignored_non_final=ignored_non_final,
            ignored_empty=ignored_empty,
            handler_failures=handler_failures,
            transport_dropped=transport_dropped,
            transport_failures=transport_failures,
            last_signal_at=last_signal_at,
            latency_samples=latency_samples,
            last_latency_ms=last_latency_ms,
            average_latency_ms=average_latency_ms,
        )

    def _public_modules(self) -> tuple[object, object]:
        events = self._events_module or importlib.import_module("hearsay.events")
        host = self._host_module or importlib.import_module("hearsay.host")
        try:
            if not callable(events.register_transcript_handler):
                raise AttributeError("register_transcript_handler")
            _ = events.TranscriptSource.LOCAL
            chunk_duration = float(host.LIVE_TRANSCRIPTION_PROFILE.chunk_duration_s)
        except (AttributeError, TypeError, ValueError) as exc:
            raise RuntimeError(
                f"Hearsay public Local speech API unavailable ({type(exc).__name__})"
            ) from exc
        if chunk_duration <= 0:
            raise RuntimeError("Hearsay live transcription chunk duration must be positive")
        return events, host

    def _handle_hearsay_event(self, event: object, epoch: int) -> None:
        source = _enum_value(getattr(event, "source", None))
        final = bool(getattr(event, "final", False))
        event_session_id = str(getattr(event, "session_id", ""))
        text = _normalize_signal_text(str(getattr(event, "text", "")))

        with self._lock:
            if epoch != self._epoch or event_session_id != self._active_session_id:
                self._ignored_stale += 1
                return
            if source != "Local":
                self._ignored_non_local += 1
                return
            if not final:
                self._ignored_non_final += 1
                return
            if not text:
                self._ignored_empty += 1
                return
            handler = self._handler
            if handler is None:
                self._ignored_stale += 1
                return
            received_at = self._clock()
            signal = LocalSpeechSignal(
                provider_name=self.provider_name,
                session_id=event_session_id,
                sequence=int(event.sequence),
                text=text,
                received_at=received_at,
                final=True,
                start_time=_optional_float(getattr(event, "start_time", None)),
                end_time=_optional_float(getattr(event, "end_time", None)),
            )

        try:
            handler(signal)
        except Exception:
            with self._lock:
                if epoch == self._epoch:
                    self._handler_failures += 1
            return

        with self._lock:
            if epoch != self._epoch or event_session_id != self._active_session_id:
                return
            self._emitted += 1
            self._last_signal_at = received_at


@dataclass(frozen=True)
class FakeLocalSpeechProviderConfig:
    provider_name: str = "fake-local-speech"
    signal_kind: LocalSpeechSignalKind = LocalSpeechSignalKind.STREAMING
    nominal_window_ms: float | None = 250.0

    def __post_init__(self) -> None:
        if not self.provider_name.strip():
            raise ValueError("provider_name must be non-empty")
        if self.nominal_window_ms is not None and self.nominal_window_ms <= 0:
            raise ValueError("nominal_window_ms must be positive")


class FakeLocalSpeechProvider:
    """Deterministic provider for alignment tests without audio hardware or Hearsay."""

    def __init__(
        self,
        config: FakeLocalSpeechProviderConfig | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config or FakeLocalSpeechProviderConfig()
        self._clock = clock
        self._lock = threading.RLock()
        self._handler: LocalSpeechSignalHandler | None = None
        self._active_session_id: str | None = None
        self._emitted = 0
        self._ignored_stale = 0
        self._handler_failures = 0
        self._last_signal_at: float | None = None
        self._latency_samples = 0
        self._latency_total_ms = 0.0
        self._last_latency_ms: float | None = None

    @property
    def provider_name(self) -> str:
        return self.config.provider_name

    def start(self, session_id: str, handler: LocalSpeechSignalHandler) -> None:
        if not session_id.strip():
            raise ValueError("session_id must be non-empty")
        if not callable(handler):
            raise TypeError("handler must be callable")
        with self._lock:
            if self._handler is not None:
                raise RuntimeError("Local speech provider is already running")
            self._active_session_id = session_id
            self._handler = handler

    def stop(self) -> None:
        with self._lock:
            self._active_session_id = None
            self._handler = None

    def emit(
        self,
        text: str,
        *,
        sequence: int,
        session_id: str | None = None,
        final: bool = True,
        start_time: float | None = None,
        end_time: float | None = None,
        recognition_latency_ms: float | None = None,
    ) -> bool:
        normalized = _normalize_signal_text(text)
        with self._lock:
            active_session_id = self._active_session_id
            handler = self._handler
            event_session_id = session_id or active_session_id
            if (
                handler is None
                or active_session_id is None
                or event_session_id != active_session_id
            ):
                self._ignored_stale += 1
                return False
            if not normalized:
                return False
            received_at = self._clock()
            signal = LocalSpeechSignal(
                provider_name=self.provider_name,
                session_id=active_session_id,
                sequence=sequence,
                text=normalized,
                received_at=received_at,
                final=final,
                start_time=start_time,
                end_time=end_time,
                recognition_latency_ms=recognition_latency_ms,
            )

        try:
            handler(signal)
        except Exception:
            with self._lock:
                self._handler_failures += 1
            return False

        with self._lock:
            if handler is not self._handler or active_session_id != self._active_session_id:
                return False
            self._emitted += 1
            self._last_signal_at = received_at
            if recognition_latency_ms is not None:
                self._latency_samples += 1
                self._latency_total_ms += recognition_latency_ms
                self._last_latency_ms = recognition_latency_ms
        return True

    def diagnostics(self) -> LocalSpeechProviderDiagnostics:
        with self._lock:
            running = self._handler is not None and self._active_session_id is not None
            degraded = self._handler_failures > 0
            if not running:
                health = LocalSpeechProviderHealth.STOPPED
            elif degraded:
                health = LocalSpeechProviderHealth.DEGRADED
            else:
                health = LocalSpeechProviderHealth.HEALTHY
            average_latency_ms = (
                self._latency_total_ms / self._latency_samples if self._latency_samples else None
            )
            return LocalSpeechProviderDiagnostics(
                provider_name=self.provider_name,
                health=health,
                signal_kind=self.config.signal_kind,
                running=running,
                active_session_id=self._active_session_id,
                nominal_window_ms=self.config.nominal_window_ms,
                emitted=self._emitted,
                ignored_stale=self._ignored_stale,
                ignored_non_local=0,
                ignored_non_final=0,
                ignored_empty=0,
                handler_failures=self._handler_failures,
                transport_dropped=0,
                transport_failures=0,
                last_signal_at=self._last_signal_at,
                latency_samples=self._latency_samples,
                last_latency_ms=self._last_latency_ms,
                average_latency_ms=average_latency_ms,
            )


def _normalize_signal_text(text: str) -> str:
    return " ".join(text.split())


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def _enum_value(value: object) -> str:
    raw = getattr(value, "value", value)
    return str(raw) if raw is not None else ""
