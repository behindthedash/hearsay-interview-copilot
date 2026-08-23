# Epic 001 — Live Interview Copilot

## Business Objective

Build a separate interview-assistance application that subscribes to live Hearsay transcript events, understands coherent interviewer turns, retrieves truthful evidence, and surfaces the safest useful form of assistance: a grounded speech-ready response, concise cues, a clarification, or an explicit unavailable state.

## Host Dependencies

This project consumes, but does not own:

- finalized source-tagged transcript events from Hearsay;
- generic live-only session behavior;
- a low-latency transcription profile;
- a side-effect-free supported Python import/session surface.

The initial integration is explicit in-process registration. No webhook or network transport is required.

## Architectural Principles

1. **Transcript events are the Hearsay boundary.** Never reach into Hearsay private queues, UI, recorder, or Whisper internals.
2. **Retrieval gates generation.** Speech-ready generation is allowed only from sufficiently strong retrieved evidence; weak or ambiguous evidence degrades to cues, clarification, or unavailable behavior.
3. **Truth status is first-class.** Implemented, prototype, design, and hypothetical material remain distinguishable end-to-end and through any generated wording.
4. **Personal data stays out of Git.** Real resume/project material and interview transcripts are external runtime data.
5. **Knowledge storage is consumer-owned.** Local storage and PostgreSQL/pgvector live here, not in Hearsay.
6. **Response composition is consumer-owned.** Question interpretation, response-mode selection, grounding, and speech-ready composition belong to Interview Copilot.
7. **Stale work cannot win.** New interviewer turns supersede older retrieval and response generations.
8. **Failure degrades locally.** Retrieval/UI/database/generation failure must not terminate Hearsay transcription or fabricate an answer.
9. **Presentation does not own truth.** Cue and teleprompter surfaces project response packages; they do not create unsupported claims or mutate retrieval evidence.

## Capabilities

- Local knowledge index
- Knowledge-store provider contract
- PostgreSQL/pgvector knowledge provider
- Remote interviewer-turn boundaries
- Interview cue retrieval and composition
- Grounded response composition and response-mode selection
- Compact topmost presentation primitives
- Interview cue overlay
- Live Interview Copilot session orchestration
- Integration with the speech-following teleprompter for generated-script responses

## Acceptance Journey

1. The application attaches to a supported Hearsay live session and registers transcript handlers.
2. Finalized `Remote` speech arrives at low latency.
3. The consumer assembles a coherent interviewer turn.
4. The turn is searched against explicitly selected knowledge scopes.
5. Relevant evidence is returned with provenance and experience status.
6. The response coordinator selects generated-script, cue-only, clarification, or unavailable behavior based on evidence quality and policy.
7. A generated script, when eligible, is concise, evidence-grounded, and staged for the teleprompter with optional supporting cues.
8. Weak/ambiguous/no-match evidence never becomes an invented scripted answer.
9. A newer interviewer turn supersedes stale retrieval/composition work.
10. Consumer failure does not stop the Hearsay host.
11. Teardown unregisters handlers and clears transient query, response, and cue state.
