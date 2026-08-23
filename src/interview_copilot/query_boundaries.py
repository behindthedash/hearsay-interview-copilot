from __future__ import annotations

import re
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import StrEnum


class TranscriptSource(StrEnum):
    """Consumer-domain transcript source independent of the Hearsay host package."""

    REMOTE = "Remote"
    LOCAL = "Local"


class BoundaryReason(StrEnum):
    PUNCTUATION_DEBOUNCE = "punctuation_debounce"
    PAUSE = "pause"
    MAX_AGE = "max_age"
    MAX_SIZE = "max_size"
    MANUAL = "manual"


@dataclass(frozen=True)
class TranscriptSegment:
    """Minimal finalized transcript view consumed by the boundary assembler."""

    session_id: str
    source: TranscriptSource
    text: str
    order: int
    is_final: bool = True

    def __post_init__(self) -> None:
        if not self.session_id.strip():
            raise ValueError("session_id must be non-empty")
        if self.order < 0:
            raise ValueError("order must be non-negative")


@dataclass(frozen=True)
class QueryCandidate:
    session_id: str
    generation: int
    text: str
    boundary_reason: BoundaryReason
    first_order: int
    last_order: int
    started_at: float
    completed_at: float


@dataclass(frozen=True)
class BoundaryConfig:
    punctuation_debounce_seconds: float = 0.75
    pause_seconds: float = 1.5
    max_age_seconds: float = 20.0
    max_chars: int = 1200
    duplicate_window_seconds: float = 15.0
    duplicate_similarity: float = 0.92
    duplicate_history_size: int = 8

    def __post_init__(self) -> None:
        if self.punctuation_debounce_seconds < 0:
            raise ValueError("punctuation_debounce_seconds must be non-negative")
        if self.pause_seconds <= 0:
            raise ValueError("pause_seconds must be positive")
        if self.max_age_seconds <= 0:
            raise ValueError("max_age_seconds must be positive")
        if self.max_chars <= 0:
            raise ValueError("max_chars must be positive")
        if self.duplicate_window_seconds < 0:
            raise ValueError("duplicate_window_seconds must be non-negative")
        if not 0.0 <= self.duplicate_similarity <= 1.0:
            raise ValueError("duplicate_similarity must be between 0 and 1")
        if self.duplicate_history_size <= 0:
            raise ValueError("duplicate_history_size must be positive")


class RemoteUtteranceAssembler:
    """Deterministically turns finalized Remote segments into bounded query candidates."""

    def __init__(
        self,
        config: BoundaryConfig | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config or BoundaryConfig()
        self._clock = clock
        self._recent: deque[tuple[str, float]] = deque(maxlen=self.config.duplicate_history_size)
        self._session_id: str | None = None
        self._generation = 0
        self._last_seen_order: int | None = None
        self._buffer = ""
        self._first_order: int | None = None
        self._last_order: int | None = None
        self._started_at: float | None = None
        self._last_activity_at: float | None = None
        self._punctuation_at: float | None = None

    @property
    def session_id(self) -> str | None:
        return self._session_id

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def buffered_text(self) -> str:
        return self._buffer

    def begin_session(self, session_id: str) -> None:
        if not session_id.strip():
            raise ValueError("session_id must be non-empty")
        if self._session_id == session_id:
            return
        self._session_id = session_id
        self._generation = 0
        self._last_seen_order = None
        self._recent.clear()
        self._clear_buffer()

    def teardown(self) -> None:
        self._session_id = None
        self._generation = 0
        self._last_seen_order = None
        self._recent.clear()
        self._clear_buffer()

    def ingest(self, segment: TranscriptSegment) -> list[QueryCandidate]:
        """Consume one finalized transcript segment and return any completed candidates."""
        if not segment.is_final or segment.source is not TranscriptSource.REMOTE:
            return []

        text = " ".join(segment.text.split())
        if not text:
            return []

        if self._session_id != segment.session_id:
            self.begin_session(segment.session_id)

        if self._last_seen_order is not None and segment.order <= self._last_seen_order:
            return []

        now = self._clock()
        emitted = self._poll(now)
        self._last_seen_order = segment.order

        if not self._buffer:
            self._start_buffer(text, segment.order, now)
        else:
            merged = _merge_overlap(self._buffer, text)
            if merged == self._buffer:
                return emitted
            if len(merged) > self.config.max_chars:
                candidate = self._emit(BoundaryReason.MAX_SIZE, now)
                if candidate is not None:
                    emitted.append(candidate)
                self._start_buffer(text, segment.order, now)
            else:
                self._buffer = merged
                self._last_order = segment.order
                self._last_activity_at = now
                self._punctuation_at = now if _looks_complete(self._buffer) else None

        if len(self._buffer) > self.config.max_chars:
            candidate = self._emit(BoundaryReason.MAX_SIZE, now)
            if candidate is not None:
                emitted.append(candidate)
        elif self._started_at is not None and now - self._started_at >= self.config.max_age_seconds:
            candidate = self._emit(BoundaryReason.MAX_AGE, now)
            if candidate is not None:
                emitted.append(candidate)

        return emitted

    def poll(self) -> list[QueryCandidate]:
        """Evaluate time-based boundaries without requiring a new transcript event."""
        return self._poll(self._clock())

    def manual_flush(self) -> list[QueryCandidate]:
        candidate = self._emit(BoundaryReason.MANUAL, self._clock())
        return [] if candidate is None else [candidate]

    def _poll(self, now: float) -> list[QueryCandidate]:
        if not self._buffer or self._started_at is None or self._last_activity_at is None:
            return []

        reason: BoundaryReason | None = None
        if now - self._started_at >= self.config.max_age_seconds:
            reason = BoundaryReason.MAX_AGE
        elif (
            self._punctuation_at is not None
            and now - self._punctuation_at >= self.config.punctuation_debounce_seconds
        ):
            reason = BoundaryReason.PUNCTUATION_DEBOUNCE
        elif now - self._last_activity_at >= self.config.pause_seconds:
            reason = BoundaryReason.PAUSE

        if reason is None:
            return []
        candidate = self._emit(reason, now)
        return [] if candidate is None else [candidate]

    def _start_buffer(self, text: str, order: int, now: float) -> None:
        self._buffer = text
        self._first_order = order
        self._last_order = order
        self._started_at = now
        self._last_activity_at = now
        self._punctuation_at = now if _looks_complete(text) else None

    def _emit(self, reason: BoundaryReason, now: float) -> QueryCandidate | None:
        if (
            not self._buffer
            or self._session_id is None
            or self._first_order is None
            or self._last_order is None
            or self._started_at is None
        ):
            return None

        text = self._buffer.strip()
        first_order = self._first_order
        last_order = self._last_order
        started_at = self._started_at
        self._clear_buffer()

        normalized = _normalize(text)
        if not normalized or self._is_recent_duplicate(normalized, now):
            return None

        self._generation += 1
        self._recent.append((normalized, now))
        return QueryCandidate(
            session_id=self._session_id,
            generation=self._generation,
            text=text,
            boundary_reason=reason,
            first_order=first_order,
            last_order=last_order,
            started_at=started_at,
            completed_at=now,
        )

    def _is_recent_duplicate(self, normalized: str, now: float) -> bool:
        while self._recent and now - self._recent[0][1] > self.config.duplicate_window_seconds:
            self._recent.popleft()

        return any(
            previous == normalized
            or SequenceMatcher(None, previous, normalized).ratio()
            >= self.config.duplicate_similarity
            for previous, _ in self._recent
        )

    def _clear_buffer(self) -> None:
        self._buffer = ""
        self._first_order = None
        self._last_order = None
        self._started_at = None
        self._last_activity_at = None
        self._punctuation_at = None


def _looks_complete(text: str) -> bool:
    return text.rstrip().endswith(("?", "!", "."))


def _normalize(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", text.casefold()).split())


def _merge_overlap(existing: str, incoming: str) -> str:
    existing_tokens = existing.split()
    incoming_tokens = incoming.split()
    existing_norm = [_normalize(token) for token in existing_tokens]
    incoming_norm = [_normalize(token) for token in incoming_tokens]

    max_overlap = min(len(existing_tokens), len(incoming_tokens))
    overlap = 0
    for size in range(max_overlap, 0, -1):
        if existing_norm[-size:] == incoming_norm[:size]:
            overlap = size
            break

    if overlap == len(incoming_tokens):
        return existing
    remainder = " ".join(incoming_tokens[overlap:])
    return f"{existing} {remainder}".strip()
