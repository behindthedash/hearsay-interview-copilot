# Epic 001 — Live Interview Copilot

## Business Objective

Build a separate interview-assistance application that subscribes to live Hearsay transcript events and surfaces concise, truthful, provenance-preserving cues while an interview is happening.

## Host Dependencies

This project consumes, but does not own:

- finalized source-tagged transcript events from Hearsay;
- generic live-only session behavior;
- a low-latency transcription profile;
- a side-effect-free supported Python import/session surface.

The initial integration is explicit in-process registration. No webhook or network transport is required.

## Architectural Principles

1. **Transcript events are the boundary.** Never reach into Hearsay private queues, UI, recorder, or Whisper internals.
2. **Retrieval before generation.** The default cue is evidence and structure, not a scripted answer.
3. **Truth status is first-class.** Implemented, prototype, design, and hypothetical material remain distinguishable end-to-end.
4. **Personal data stays out of Git.** Real resume/project material and interview transcripts are external runtime data.
5. **Knowledge storage is consumer-owned.** Local storage and PostgreSQL/pgvector live here, not in Hearsay.
6. **Stale work cannot win.** New interviewer turns supersede older retrieval generations.
7. **Failure degrades locally.** Retrieval/UI/database failure must not terminate Hearsay transcription.

## Capabilities

- Local knowledge index
- Knowledge-store provider contract
- PostgreSQL/pgvector knowledge provider
- Remote interviewer-turn boundaries
- Interview cue retrieval and composition
- Compact topmost presentation primitives
- Interview cue overlay
- Live Interview Copilot session orchestration

## Acceptance Journey

1. The application attaches to a supported Hearsay live session and registers transcript handlers.
2. Finalized `Remote` speech arrives at low latency.
3. The consumer assembles a coherent interviewer turn.
4. The turn is searched against explicitly selected knowledge scopes.
5. Relevant evidence is returned with provenance and experience status.
6. A concise cue appears near the webcam.
7. A newer interviewer turn supersedes stale retrieval/cue work.
8. Consumer failure does not stop the Hearsay host.
9. Teardown unregisters handlers and clears transient query/cue state.
