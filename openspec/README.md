# OpenSpec

This is a greenfield OpenSpec project. Current product behavior is described as canonical capability specs under `openspec/specs/`; there are no change proposals yet.

## Product boundary

Hearsay Interview Copilot is a separate consumer of `behindthedash/hearsay`.

- Hearsay owns audio capture, Whisper transcription, source-tagged transcript events, live-only sessions, and low-latency transcription profiles.
- This repository owns interviewer-turn detection, knowledge indexing/retrieval, local and PostgreSQL/pgvector storage, cue composition, interview UI, and speech-following teleprompter behavior.
- Dependency direction is one-way: `hearsay-interview-copilot -> hearsay`.
- This repository must use Hearsay's supported public host API and must not read Hearsay private queues, UI widgets, recorder internals, or Whisper internals.

## Roadmap

1. [`001-live-interview-copilot.md`](epics/001-live-interview-copilot.md)
2. [`002-speech-following-teleprompter.md`](epics/002-speech-following-teleprompter.md)

Future implementation work should introduce `openspec/changes/<change-name>/` only when an actual change to these baseline specs is proposed.
