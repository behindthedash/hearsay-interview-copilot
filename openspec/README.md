# OpenSpec

This is a greenfield OpenSpec project. Canonical product behavior is described under `openspec/specs/`; implementation work and proposed changes are tracked under `openspec/changes/`.

## Product boundary

Hearsay Interview Copilot is a separate consumer of `behindthedash/hearsay`.

- Hearsay owns audio capture, Whisper transcription, source-tagged transcript events, live-only sessions, low-latency transcription profiles, and its supported public host API.
- This repository owns interviewer-turn detection, knowledge indexing/retrieval, local and PostgreSQL/pgvector storage, grounded response composition, cue composition, interview UI, and speech-following teleprompter behavior.
- The teleprompter is a spoken-response presentation surface for both prepared and grounded generated content; Hearsay remains unaware of scripts, response generation, cues, and alignment state.
- Teleprompter alignment may use Hearsay `Local` events or a consumer-owned low-latency Local speech provider, but it must not depend on Hearsay private queues, UI widgets, recorder internals, or Whisper internals.
- Dependency direction is one-way: `hearsay-interview-copilot -> hearsay`.

## Roadmap

1. [`001-live-interview-copilot.md`](epics/001-live-interview-copilot.md)
2. [`002-speech-following-teleprompter.md`](epics/002-speech-following-teleprompter.md)

The two epics intentionally meet at grounded response presentation: Epic 001 owns question understanding, retrieval, grounding, and response-mode selection; Epic 002 owns speech-following presentation and user control.
