from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import SimpleNamespace

import pytest

from interview_copilot.local_speech import (
    FakeLocalSpeechProvider,
    FakeLocalSpeechProviderConfig,
    HearsayLocalSpeechProvider,
    LocalSpeechProviderHealth,
    LocalSpeechSignal,
    LocalSpeechSignalKind,
)


class FakeTranscriptSource(StrEnum):
    REMOTE = "Remote"
    LOCAL = "Local"


@dataclass(frozen=True)
class FakeTranscriptEvent:
    session_id: str
    sequence: int
    source: FakeTranscriptSource
    text: str
    start_time: float | None = None
    end_time: float | None = None
    final: bool = True


class FakeHearsaySubscription:
    def __init__(self) -> None:
        self.closed = False
        self.dropped = 0
        self.failures = 0

    def close(self) -> None:
        self.closed = True

    def diagnostics(self):
        return SimpleNamespace(dropped=self.dropped, failures=self.failures)


class FakeHearsayEvents:
    TranscriptSource = FakeTranscriptSource

    def __init__(self) -> None:
        self.handler = None
        self.sources = None
        self.queue_size = None
        self.name = None
        self.subscriptions: list[FakeHearsaySubscription] = []

    def register_transcript_handler(self, name, handler, *, sources, queue_size):
        self.name = name
        self.handler = handler
        self.sources = tuple(sources)
        self.queue_size = queue_size
        subscription = FakeHearsaySubscription()
        self.subscriptions.append(subscription)
        return subscription

    def emit(self, event: FakeTranscriptEvent) -> None:
        assert self.handler is not None
        self.handler(event)


class FakeHearsayHost:
    LIVE_TRANSCRIPTION_PROFILE = SimpleNamespace(name="live", chunk_duration_s=4.0)


class Clock:
    def __init__(self, start: float = 100.0) -> None:
        self.value = start

    def __call__(self) -> float:
        current = self.value
        self.value += 0.1
        return current


def _assert_common_signal(signal: LocalSpeechSignal, *, provider_name: str) -> None:
    assert signal.provider_name == provider_name
    assert signal.session_id == "session-a"
    assert signal.sequence == 7
    assert signal.text == "hello from local speech"
    assert signal.received_at >= 0
    assert not hasattr(signal, "source")


def test_local_speech_signal_is_structurally_local_only() -> None:
    signal = LocalSpeechSignal(
        provider_name="fixture",
        session_id="session-a",
        sequence=1,
        text="local speech",
        received_at=1.0,
    )

    assert signal.final is True
    assert not hasattr(signal, "source")

    with pytest.raises(ValueError, match="text must be non-empty"):
        LocalSpeechSignal(
            provider_name="fixture",
            session_id="session-a",
            sequence=1,
            text="   ",
            received_at=1.0,
        )


def test_fake_provider_satisfies_common_signal_and_lifecycle_contract() -> None:
    provider = FakeLocalSpeechProvider(clock=Clock())
    observed: list[LocalSpeechSignal] = []

    provider.start("session-a", observed.append)
    assert provider.emit(" hello   from local speech ", sequence=7)

    assert len(observed) == 1
    _assert_common_signal(observed[0], provider_name=provider.provider_name)
    running = provider.diagnostics()
    assert running.health is LocalSpeechProviderHealth.HEALTHY
    assert running.running is True
    assert running.active_session_id == "session-a"
    assert running.signal_kind is LocalSpeechSignalKind.STREAMING
    assert running.nominal_window_ms == 250.0

    provider.stop()
    assert provider.diagnostics().health is LocalSpeechProviderHealth.STOPPED
    assert not provider.emit("late speech", sequence=8, session_id="session-a")
    assert provider.diagnostics().ignored_stale == 1


def test_hearsay_provider_satisfies_common_signal_and_public_subscription_contract() -> None:
    events = FakeHearsayEvents()
    provider = HearsayLocalSpeechProvider(
        events_module=events,
        host_module=FakeHearsayHost(),
        clock=Clock(),
    )
    observed: list[LocalSpeechSignal] = []

    provider.start("session-a", observed.append)
    assert events.sources == (FakeTranscriptSource.LOCAL,)
    assert events.queue_size == 100
    events.emit(
        FakeTranscriptEvent(
            session_id="session-a",
            sequence=7,
            source=FakeTranscriptSource.LOCAL,
            text=" hello   from local speech ",
            start_time=1.0,
            end_time=2.0,
        )
    )

    assert len(observed) == 1
    _assert_common_signal(observed[0], provider_name=provider.provider_name)
    assert observed[0].start_time == 1.0
    assert observed[0].end_time == 2.0
    diagnostics = provider.diagnostics()
    assert diagnostics.health is LocalSpeechProviderHealth.HEALTHY
    assert diagnostics.signal_kind is LocalSpeechSignalKind.FINALIZED
    assert diagnostics.nominal_window_ms == 4000.0
    assert diagnostics.latency_samples == 0
    assert diagnostics.average_latency_ms is None

    subscription = events.subscriptions[-1]
    provider.stop()
    assert subscription.closed is True
    assert provider.diagnostics().health is LocalSpeechProviderHealth.STOPPED


def test_hearsay_adapter_defensively_rejects_remote_nonfinal_empty_and_wrong_session() -> None:
    events = FakeHearsayEvents()
    provider = HearsayLocalSpeechProvider(
        events_module=events,
        host_module=FakeHearsayHost(),
        clock=Clock(),
    )
    observed: list[LocalSpeechSignal] = []
    provider.start("session-a", observed.append)

    events.emit(
        FakeTranscriptEvent(
            session_id="session-a",
            sequence=1,
            source=FakeTranscriptSource.REMOTE,
            text="interviewer speech",
        )
    )
    events.emit(
        FakeTranscriptEvent(
            session_id="session-a",
            sequence=2,
            source=FakeTranscriptSource.LOCAL,
            text="partial local speech",
            final=False,
        )
    )
    events.emit(
        FakeTranscriptEvent(
            session_id="session-a",
            sequence=3,
            source=FakeTranscriptSource.LOCAL,
            text="   ",
        )
    )
    events.emit(
        FakeTranscriptEvent(
            session_id="old-session",
            sequence=4,
            source=FakeTranscriptSource.LOCAL,
            text="stale local speech",
        )
    )

    assert observed == []
    diagnostics = provider.diagnostics()
    assert diagnostics.ignored_non_local == 1
    assert diagnostics.ignored_non_final == 1
    assert diagnostics.ignored_empty == 1
    assert diagnostics.ignored_stale == 1


def test_hearsay_provider_epoch_blocks_old_callback_after_session_restart() -> None:
    events = FakeHearsayEvents()
    provider = HearsayLocalSpeechProvider(
        events_module=events,
        host_module=FakeHearsayHost(),
        clock=Clock(),
    )
    observed: list[LocalSpeechSignal] = []

    provider.start("session-a", observed.append)
    old_handler = events.handler
    assert old_handler is not None
    provider.stop()

    provider.start("session-b", observed.append)
    old_handler(
        FakeTranscriptEvent(
            session_id="session-b",
            sequence=5,
            source=FakeTranscriptSource.LOCAL,
            text="late callback from old subscription",
        )
    )
    events.emit(
        FakeTranscriptEvent(
            session_id="session-b",
            sequence=6,
            source=FakeTranscriptSource.LOCAL,
            text="current local speech",
        )
    )

    assert [signal.text for signal in observed] == ["current local speech"]
    assert provider.diagnostics().ignored_stale == 1


def test_fake_provider_rejects_prior_session_signals_after_restart() -> None:
    provider = FakeLocalSpeechProvider(clock=Clock())
    observed: list[LocalSpeechSignal] = []

    provider.start("session-a", observed.append)
    provider.stop()
    provider.start("session-b", observed.append)

    assert not provider.emit("old local speech", sequence=1, session_id="session-a")
    assert provider.emit("new local speech", sequence=2, session_id="session-b")
    assert [signal.session_id for signal in observed] == ["session-b"]


def test_provider_diagnostics_support_latency_comparison_without_fabricating_hearsay_latency() -> None:
    fake = FakeLocalSpeechProvider(
        FakeLocalSpeechProviderConfig(nominal_window_ms=200.0),
        clock=Clock(),
    )
    fake.start("session-a", lambda signal: None)
    assert fake.emit("one", sequence=1, recognition_latency_ms=80.0)
    assert fake.emit("two", sequence=2, recognition_latency_ms=120.0)

    fake_diagnostics = fake.diagnostics()
    assert fake_diagnostics.latency_samples == 2
    assert fake_diagnostics.last_latency_ms == 120.0
    assert fake_diagnostics.average_latency_ms == 100.0
    assert fake_diagnostics.nominal_window_ms == 200.0

    events = FakeHearsayEvents()
    hearsay = HearsayLocalSpeechProvider(
        events_module=events,
        host_module=FakeHearsayHost(),
        clock=Clock(),
    )
    hearsay.start("session-a", lambda signal: None)
    events.emit(
        FakeTranscriptEvent(
            session_id="session-a",
            sequence=1,
            source=FakeTranscriptSource.LOCAL,
            text="finalized local speech",
        )
    )
    hearsay_diagnostics = hearsay.diagnostics()

    assert hearsay_diagnostics.nominal_window_ms == 4000.0
    assert hearsay_diagnostics.signal_kind is LocalSpeechSignalKind.FINALIZED
    assert hearsay_diagnostics.latency_samples == 0
    assert hearsay_diagnostics.last_latency_ms is None
    assert hearsay_diagnostics.average_latency_ms is None


def test_handler_failure_is_isolated_and_marks_provider_degraded() -> None:
    provider = FakeLocalSpeechProvider(clock=Clock())

    def fail(_signal: LocalSpeechSignal) -> None:
        raise RuntimeError("alignment consumer failed")

    provider.start("session-a", fail)
    assert not provider.emit("local speech", sequence=1)

    diagnostics = provider.diagnostics()
    assert diagnostics.running is True
    assert diagnostics.health is LocalSpeechProviderHealth.DEGRADED
    assert diagnostics.handler_failures == 1


def test_hearsay_transport_diagnostics_are_projected_without_transcript_content() -> None:
    events = FakeHearsayEvents()
    provider = HearsayLocalSpeechProvider(
        events_module=events,
        host_module=FakeHearsayHost(),
        clock=Clock(),
    )
    provider.start("session-a", lambda signal: None)
    subscription = events.subscriptions[-1]
    subscription.dropped = 2
    subscription.failures = 1

    diagnostics = provider.diagnostics()

    assert diagnostics.health is LocalSpeechProviderHealth.DEGRADED
    assert diagnostics.transport_dropped == 2
    assert diagnostics.transport_failures == 1
    assert not hasattr(diagnostics, "text")
