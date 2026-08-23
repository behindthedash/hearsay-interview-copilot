## Why

The current product model treats the teleprompter as prepared-only content and the knowledge system as a separate cue surface. That leaves a gap for the common case where an interviewer asks a question with no prepared script: the system can retrieve useful evidence but cannot turn it into speech-ready guidance in the same surface the user is already following.

## What Changes

- Add grounded response composition that turns an eligible interviewer question plus retrieved evidence into one of several response modes: generated script, cue-only guidance, clarification, or unavailable.
- Treat the teleprompter as a spoken-response presentation engine rather than a prepared-script-only feature.
- Allow teleprompter content to originate from prepared material or an ephemeral generated response while retaining source/provenance metadata.
- Allow a generated script to carry supporting cue bullets without merging cue state into speech-alignment state.
- Prevent a newly generated response from interrupting an answer already in progress; stage it until activation is safe or explicitly requested.
- Keep generation evidence-bound: weak, ambiguous, or missing retrieval SHALL degrade to cue-only, clarification, or unavailable behavior rather than inventing experience.
- Allow teleprompter alignment to consume a consumer-owned low-latency Local speech signal when needed, while preserving Hearsay as the generic audio/transcript host and never using Remote speech for alignment.

## Repository Boundary

This change belongs entirely in `hearsay-interview-copilot`. Hearsay already exposes the correct generic boundary and remains unaware of questions, knowledge retrieval, response composition, scripts, cues, or teleprompter state.

## Capabilities

### Added Capabilities
- `grounded-response-composition`

### Modified Capabilities
- `interview-cues`
- `teleprompter-content`
- `local-speech-alignment`
- `speech-following-teleprompter-ui`
- `cue-teleprompter-coexistence`
