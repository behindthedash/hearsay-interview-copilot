# Epic 002 — Speech-Following Teleprompter

## Business Objective

Provide prepared interview talking points that follow the user's own speech naturally while coexisting with dynamic retrieval cues.

This is a consumer feature built on Hearsay `Local` transcript events. Hearsay remains unaware of scripts, talking points, alignment state, and interview presentation behavior.

## Architectural Principles

1. Prepared content is structured user-authored guidance, not a transcript.
2. Alignment follows meaning rather than exact words and tolerates paraphrase, skips, pauses, and restarts.
3. Only `Local` speech advances prepared content; `Remote` speech never moves it.
4. Manual control always wins.
5. Dynamic cues and prepared content remain separate models and meet only in presentation coordination.
6. Shared compact-window infrastructure is owned by this application.

## Capabilities

- Teleprompter content model
- Local speech alignment
- Compact topmost presentation primitives
- Speech-following teleprompter UI
- Cue/teleprompter coexistence

## Acceptance Journey

1. User loads a prepared outline.
2. The application consumes Hearsay `Local` transcript events.
3. The active section follows natural speech with confidence-based movement.
4. Pauses/restarts do not cause runaway advancement.
5. Skipping ahead can recover.
6. Manual navigation immediately overrides automatic following.
7. Dynamic interview cues can update without corrupting alignment state.
8. `Remote` speech never advances prepared content.
