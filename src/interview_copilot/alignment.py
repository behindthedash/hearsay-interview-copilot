from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import StrEnum

from .local_speech import LocalSpeechSignal
from .teleprompter_content import TeleprompterDocument, normalize_match_text


class AlignmentTransition(StrEnum):
    HELD = "held"
    ALIGNED = "aligned"
    RECOVERED = "recovered"
    MANUAL = "manual"


@dataclass(frozen=True)
class AlignmentState:
    document_id: str
    section_index: int
    section_id: str
    confidence: float
    transition: AlignmentTransition
    automatic_paused: bool
    weak_updates: int
    detail: str | None = None


@dataclass(frozen=True)
class AlignmentConfig:
    rolling_words: int = 36
    score_tail_words: int = 14
    min_evidence_words: int = 3
    nearby_back: int = 1
    nearby_forward: int = 2
    accept_threshold: float = 0.56
    movement_margin: float = 0.08
    recovery_threshold: float = 0.74
    recovery_after_weak_updates: int = 2
    recovery_confirmations: int = 2
    backward_recovery_min_words: int = 4

    def __post_init__(self) -> None:
        if self.rolling_words < 1:
            raise ValueError("rolling_words must be positive")
        if self.score_tail_words < 1:
            raise ValueError("score_tail_words must be positive")
        if self.min_evidence_words < 1:
            raise ValueError("min_evidence_words must be positive")
        if self.nearby_back < 0 or self.nearby_forward < 0:
            raise ValueError("nearby search bounds must be non-negative")
        if not 0.0 <= self.accept_threshold <= 1.0:
            raise ValueError("accept_threshold must be between zero and one")
        if not 0.0 <= self.movement_margin <= 1.0:
            raise ValueError("movement_margin must be between zero and one")
        if not 0.0 <= self.recovery_threshold <= 1.0:
            raise ValueError("recovery_threshold must be between zero and one")
        if self.recovery_threshold < self.accept_threshold:
            raise ValueError("recovery_threshold must not be lower than accept_threshold")
        if self.recovery_after_weak_updates < 1:
            raise ValueError("recovery_after_weak_updates must be positive")
        if self.recovery_confirmations < 1:
            raise ValueError("recovery_confirmations must be positive")
        if self.backward_recovery_min_words < 1:
            raise ValueError("backward_recovery_min_words must be positive")


class LocalSpeechAligner:
    """Deterministically follow Local speech through the active teleprompter document.

    The aligner is deliberately document-origin neutral. It consumes only the
    consumer-owned ``LocalSpeechSignal`` type and therefore cannot receive Remote
    interviewer transcript events through its public speech-processing method.
    """

    def __init__(self, config: AlignmentConfig | None = None) -> None:
        self.config = config or AlignmentConfig()
        self._document: TeleprompterDocument | None = None
        self._section_index = 0
        self._rolling_tokens: list[str] = []
        self._automatic_paused = False
        self._weak_updates = 0
        self._pending_recovery_index: int | None = None
        self._pending_recovery_count = 0
        self._state: AlignmentState | None = None

    @property
    def document(self) -> TeleprompterDocument | None:
        return self._document

    @property
    def state(self) -> AlignmentState | None:
        return self._state

    @property
    def automatic_paused(self) -> bool:
        return self._automatic_paused

    def activate(self, document: TeleprompterDocument, *, section_index: int = 0) -> AlignmentState:
        if not 0 <= section_index < len(document.sections):
            raise IndexError("section_index is outside the teleprompter document")
        self._document = document
        self._section_index = section_index
        self._automatic_paused = False
        self._reset_evidence()
        return self._snapshot(
            confidence=0.0,
            transition=AlignmentTransition.HELD,
            detail="document-activated",
        )

    def clear(self) -> None:
        self._document = None
        self._section_index = 0
        self._automatic_paused = False
        self._rolling_tokens.clear()
        self._weak_updates = 0
        self._pending_recovery_index = None
        self._pending_recovery_count = 0
        self._state = None

    def pause(self) -> AlignmentState:
        self._require_document()
        self._automatic_paused = True
        self._reset_evidence()
        return self._snapshot(
            confidence=0.0,
            transition=AlignmentTransition.MANUAL,
            detail="automatic-following-paused",
        )

    def resume(self) -> AlignmentState:
        self._require_document()
        self._automatic_paused = False
        self._reset_evidence()
        return self._snapshot(
            confidence=0.0,
            transition=AlignmentTransition.MANUAL,
            detail="automatic-following-resumed",
        )

    def next(self) -> AlignmentState:
        document = self._require_document()
        return self.jump(min(self._section_index + 1, len(document.sections) - 1), detail="next")

    def previous(self) -> AlignmentState:
        self._require_document()
        return self.jump(max(self._section_index - 1, 0), detail="previous")

    def jump(self, section_index: int, *, detail: str = "jump") -> AlignmentState:
        document = self._require_document()
        if not 0 <= section_index < len(document.sections):
            raise IndexError("section_index is outside the teleprompter document")
        self._section_index = section_index
        self._reset_evidence()
        return self._snapshot(
            confidence=1.0,
            transition=AlignmentTransition.MANUAL,
            detail=detail,
        )

    def process(self, signal: LocalSpeechSignal) -> AlignmentState:
        if not isinstance(signal, LocalSpeechSignal):
            raise TypeError("alignment accepts only LocalSpeechSignal values")
        document = self._require_document()

        if self._automatic_paused:
            return self._snapshot(
                confidence=0.0,
                transition=AlignmentTransition.HELD,
                detail="manual-pause",
            )

        incoming = normalize_match_text(signal.text).split()
        if not incoming:
            return self._hold(0.0, "empty-local-speech")

        self._merge_rolling(incoming)
        evidence_words = min(len(self._rolling_tokens), self.config.score_tail_words)
        if evidence_words < self.config.min_evidence_words:
            return self._hold(0.0, "insufficient-evidence", weak=False)

        local_indices = self._nearby_indices(len(document.sections))
        local_scores = {index: self._score_section(index) for index in local_indices}
        current_score = local_scores.get(
            self._section_index, self._score_section(self._section_index)
        )
        best_local_index, best_local_score = max(
            local_scores.items(),
            key=lambda item: (item[1], -abs(item[0] - self._section_index), -item[0]),
        )

        if current_score >= self.config.accept_threshold:
            if (
                best_local_index != self._section_index
                and best_local_score >= self.config.accept_threshold
                and best_local_score >= current_score + self.config.movement_margin
            ):
                return self._accept(
                    best_local_index,
                    best_local_score,
                    AlignmentTransition.ALIGNED,
                    "nearby-match",
                )
            self._weak_updates = 0
            self._clear_pending_recovery()
            return self._snapshot(
                confidence=current_score,
                transition=AlignmentTransition.HELD,
                detail="current-section-supported",
            )

        if (
            best_local_index != self._section_index
            and best_local_score >= self.config.accept_threshold
            and best_local_score >= current_score + self.config.movement_margin
        ):
            return self._accept(
                best_local_index,
                best_local_score,
                AlignmentTransition.ALIGNED,
                "nearby-match",
            )

        return self._consider_recovery(incoming, local_indices, best_local_score)

    def _consider_recovery(
        self,
        incoming: list[str],
        local_indices: tuple[int, ...],
        best_local_score: float,
    ) -> AlignmentState:
        document = self._require_document()
        self._weak_updates += 1
        if self._weak_updates < self.config.recovery_after_weak_updates:
            self._clear_pending_recovery()
            return self._snapshot(
                confidence=max(0.0, best_local_score),
                transition=AlignmentTransition.HELD,
                detail="weak-evidence",
            )

        global_scores = {
            index: self._score_section(index)
            for index in range(len(document.sections))
            if index not in local_indices or index == self._section_index
        }
        recovery_index, recovery_score = max(
            global_scores.items(),
            key=lambda item: (item[1], -abs(item[0] - self._section_index), -item[0]),
        )

        if recovery_index == self._section_index or recovery_score < self.config.recovery_threshold:
            self._clear_pending_recovery()
            return self._snapshot(
                confidence=max(0.0, recovery_score, best_local_score),
                transition=AlignmentTransition.HELD,
                detail="off-script-waiting",
            )

        if (
            recovery_index < self._section_index
            and len(incoming) < self.config.backward_recovery_min_words
        ):
            self._clear_pending_recovery()
            return self._snapshot(
                confidence=recovery_score,
                transition=AlignmentTransition.HELD,
                detail="backward-recovery-needs-more-evidence",
            )

        if self._pending_recovery_index == recovery_index:
            self._pending_recovery_count += 1
        else:
            self._pending_recovery_index = recovery_index
            self._pending_recovery_count = 1

        if self._pending_recovery_count < self.config.recovery_confirmations:
            return self._snapshot(
                confidence=recovery_score,
                transition=AlignmentTransition.HELD,
                detail="recovery-pending",
            )

        direction = (
            "backward-recovery" if recovery_index < self._section_index else "skip-ahead-recovery"
        )
        return self._accept(
            recovery_index,
            recovery_score,
            AlignmentTransition.RECOVERED,
            direction,
        )

    def _score_section(self, section_index: int) -> float:
        document = self._require_document()
        reference = document.sections[section_index].match_text.split()
        if not reference or not self._rolling_tokens:
            return 0.0

        spoken = self._rolling_tokens[-self.config.score_tail_words :]
        max_sample = min(len(spoken), self.config.score_tail_words)
        min_sample = min(self.config.min_evidence_words, max_sample)
        best = 0.0

        for sample_size in range(min_sample, max_sample + 1):
            sample = spoken[-sample_size:]
            reference_lengths = {
                max(self.config.min_evidence_words, sample_size - 2),
                sample_size,
                sample_size + 2,
                len(reference),
            }
            for reference_length in sorted(reference_lengths):
                window_length = min(reference_length, len(reference))
                if window_length < self.config.min_evidence_words:
                    continue
                for start in range(0, len(reference) - window_length + 1):
                    window = reference[start : start + window_length]
                    best = max(best, _lexical_similarity(sample, window))
        return best

    def _nearby_indices(self, section_count: int) -> tuple[int, ...]:
        start = max(0, self._section_index - self.config.nearby_back)
        end = min(section_count, self._section_index + self.config.nearby_forward + 1)
        return tuple(range(start, end))

    def _merge_rolling(self, incoming: list[str]) -> None:
        overlap_limit = min(len(self._rolling_tokens), len(incoming), 10)
        overlap = 0
        for size in range(overlap_limit, 0, -1):
            if self._rolling_tokens[-size:] == incoming[:size]:
                overlap = size
                break
        self._rolling_tokens.extend(incoming[overlap:])
        if len(self._rolling_tokens) > self.config.rolling_words:
            self._rolling_tokens = self._rolling_tokens[-self.config.rolling_words :]

    def _accept(
        self,
        section_index: int,
        confidence: float,
        transition: AlignmentTransition,
        detail: str,
    ) -> AlignmentState:
        self._section_index = section_index
        self._weak_updates = 0
        self._clear_pending_recovery()
        return self._snapshot(
            confidence=confidence,
            transition=transition,
            detail=detail,
        )

    def _hold(self, confidence: float, detail: str, *, weak: bool = True) -> AlignmentState:
        if weak:
            self._weak_updates += 1
        return self._snapshot(
            confidence=confidence,
            transition=AlignmentTransition.HELD,
            detail=detail,
        )

    def _snapshot(
        self,
        *,
        confidence: float,
        transition: AlignmentTransition,
        detail: str | None,
    ) -> AlignmentState:
        document = self._require_document()
        section = document.sections[self._section_index]
        self._state = AlignmentState(
            document_id=document.document_id,
            section_index=self._section_index,
            section_id=section.section_id,
            confidence=max(0.0, min(1.0, confidence)),
            transition=transition,
            automatic_paused=self._automatic_paused,
            weak_updates=self._weak_updates,
            detail=detail,
        )
        return self._state

    def _reset_evidence(self) -> None:
        self._rolling_tokens.clear()
        self._weak_updates = 0
        self._clear_pending_recovery()

    def _clear_pending_recovery(self) -> None:
        self._pending_recovery_index = None
        self._pending_recovery_count = 0

    def _require_document(self) -> TeleprompterDocument:
        if self._document is None:
            raise RuntimeError("no active teleprompter document")
        return self._document


def _lexical_similarity(left: list[str], right: list[str]) -> float:
    if not left or not right:
        return 0.0

    sequence = SequenceMatcher(a=left, b=right, autojunk=False).ratio()
    left_counts = Counter(left)
    right_counts = Counter(right)
    overlap = sum((left_counts & right_counts).values())
    if overlap == 0:
        return sequence * 0.35

    precision = overlap / len(left)
    recall = overlap / len(right)
    f1 = 2.0 * precision * recall / (precision + recall)
    containment = overlap / min(len(left), len(right))
    return 0.45 * sequence + 0.25 * f1 + 0.30 * containment
