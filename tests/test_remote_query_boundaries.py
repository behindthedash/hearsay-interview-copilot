from __future__ import annotations

from interview_copilot.query_boundaries import (
    BoundaryConfig,
    BoundaryReason,
    RemoteUtteranceAssembler,
    TranscriptSegment,
    TranscriptSource,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def segment(
    text: str,
    order: int,
    *,
    session_id: str = "session-a",
    source: TranscriptSource = TranscriptSource.REMOTE,
    is_final: bool = True,
) -> TranscriptSegment:
    return TranscriptSegment(
        session_id=session_id,
        source=source,
        text=text,
        order=order,
        is_final=is_final,
    )


def test_local_and_nonfinal_segments_do_not_drive_query_assembly():
    clock = FakeClock()
    assembler = RemoteUtteranceAssembler(clock=clock)

    assert (
        assembler.ingest(
            segment("Tell me about your background?", 1, source=TranscriptSource.LOCAL)
        )
        == []
    )
    assert assembler.ingest(segment("Remote draft", 2, is_final=False)) == []
    assert assembler.buffered_text == ""
    assert assembler.session_id is None


def test_adjacent_remote_segments_merge_and_emit_after_punctuation_debounce():
    clock = FakeClock()
    assembler = RemoteUtteranceAssembler(clock=clock)

    assert assembler.ingest(segment("How would you", 1)) == []
    clock.advance(0.2)
    assert assembler.ingest(segment("design a RAG system?", 2)) == []
    assert assembler.buffered_text == "How would you design a RAG system?"

    clock.advance(0.8)
    emitted = assembler.poll()

    assert len(emitted) == 1
    candidate = emitted[0]
    assert candidate.text == "How would you design a RAG system?"
    assert candidate.boundary_reason is BoundaryReason.PUNCTUATION_DEBOUNCE
    assert candidate.generation == 1
    assert candidate.first_order == 1
    assert candidate.last_order == 2
    assert candidate.session_id == "session-a"


def test_overlap_fragments_are_merged_without_repeating_words():
    clock = FakeClock()
    assembler = RemoteUtteranceAssembler(clock=clock)

    assembler.ingest(segment("How would you design", 1))
    clock.advance(0.2)
    assembler.ingest(segment("design a retrieval system?", 2))

    assert assembler.buffered_text == "How would you design a retrieval system?"


def test_pause_boundary_can_emit_without_another_transcript_event():
    clock = FakeClock()
    assembler = RemoteUtteranceAssembler(
        BoundaryConfig(punctuation_debounce_seconds=5.0, pause_seconds=1.0),
        clock=clock,
    )

    assembler.ingest(segment("Walk me through that architecture", 1))
    clock.advance(1.1)

    emitted = assembler.poll()
    assert len(emitted) == 1
    assert emitted[0].boundary_reason is BoundaryReason.PAUSE


def test_max_age_boundary_precedes_pause_when_hard_age_limit_is_reached():
    clock = FakeClock()
    assembler = RemoteUtteranceAssembler(
        BoundaryConfig(
            punctuation_debounce_seconds=10.0,
            pause_seconds=10.0,
            max_age_seconds=2.0,
        ),
        clock=clock,
    )

    assembler.ingest(segment("This interviewer turn keeps going", 1))
    clock.advance(2.1)

    emitted = assembler.poll()
    assert len(emitted) == 1
    assert emitted[0].boundary_reason is BoundaryReason.MAX_AGE


def test_max_size_flushes_existing_buffer_before_accepting_overflowing_segment():
    clock = FakeClock()
    assembler = RemoteUtteranceAssembler(
        BoundaryConfig(max_chars=24, pause_seconds=10.0, max_age_seconds=10.0),
        clock=clock,
    )

    assembler.ingest(segment("How would you design", 1))
    emitted = assembler.ingest(segment("a secure retrieval layer", 2))

    assert len(emitted) == 1
    assert emitted[0].text == "How would you design"
    assert emitted[0].boundary_reason is BoundaryReason.MAX_SIZE
    assert assembler.buffered_text == "a secure retrieval layer"


def test_manual_flush_emits_buffered_remote_speech():
    clock = FakeClock()
    assembler = RemoteUtteranceAssembler(clock=clock)

    assembler.ingest(segment("What did you personally own", 1))
    emitted = assembler.manual_flush()

    assert len(emitted) == 1
    assert emitted[0].boundary_reason is BoundaryReason.MANUAL
    assert emitted[0].generation == 1
    assert assembler.buffered_text == ""


def test_duplicate_candidates_are_suppressed_without_advancing_generation():
    clock = FakeClock()
    assembler = RemoteUtteranceAssembler(clock=clock)

    assembler.ingest(segment("How would you design RAG?", 1))
    first = assembler.manual_flush()
    assert first[0].generation == 1

    clock.advance(1.0)
    assembler.ingest(segment("How would you design RAG?", 2))
    assert assembler.manual_flush() == []
    assert assembler.generation == 1


def test_distinct_candidates_advance_generation_monotonically():
    clock = FakeClock()
    assembler = RemoteUtteranceAssembler(clock=clock)

    assembler.ingest(segment("Tell me about your architecture work", 1))
    first = assembler.manual_flush()[0]
    assembler.ingest(segment("How did you validate the result", 2))
    second = assembler.manual_flush()[0]

    assert first.generation == 1
    assert second.generation == 2


def test_repeated_or_out_of_order_segment_order_is_ignored():
    clock = FakeClock()
    assembler = RemoteUtteranceAssembler(clock=clock)

    assembler.ingest(segment("How would you", 3))
    assert assembler.ingest(segment("How would you", 3)) == []
    assert assembler.ingest(segment("old fragment", 2)) == []
    assert assembler.buffered_text == "How would you"


def test_new_session_clears_buffer_recent_history_and_generation():
    clock = FakeClock()
    assembler = RemoteUtteranceAssembler(clock=clock)

    assembler.ingest(segment("First session question", 1, session_id="session-a"))
    assert assembler.manual_flush()[0].generation == 1
    assembler.ingest(segment("unfinished old turn", 2, session_id="session-a"))

    assembler.ingest(segment("First new session question", 1, session_id="session-b"))
    candidate = assembler.manual_flush()[0]

    assert candidate.session_id == "session-b"
    assert candidate.generation == 1
    assert candidate.text == "First new session question"


def test_teardown_clears_all_transient_state_and_restarts_generation():
    clock = FakeClock()
    assembler = RemoteUtteranceAssembler(clock=clock)

    assembler.ingest(segment("Question one", 1))
    assert assembler.manual_flush()[0].generation == 1
    assembler.ingest(segment("unfinished", 2))

    assembler.teardown()

    assert assembler.session_id is None
    assert assembler.buffered_text == ""
    assert assembler.generation == 0

    assembler.ingest(segment("Question after reattach", 1, session_id="session-c"))
    assert assembler.manual_flush()[0].generation == 1
