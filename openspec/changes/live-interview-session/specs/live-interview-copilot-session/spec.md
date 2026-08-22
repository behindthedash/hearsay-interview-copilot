## MODIFIED Requirements

### Requirement: The user can start an explicit Interview Copilot session
The consumer SHALL start/attach through Hearsay's supported public host/session API and SHALL NOT require direct access to Hearsay private queues, recorder, UI widgets, or Whisper internals.

#### Scenario: Preflight succeeds
- **WHEN** required Hearsay host capabilities and the configured knowledge provider are healthy
- **THEN** the consumer registers its handlers, enters listening state, and can receive Remote/Local events through the public contract

### Requirement: Optional-stage failure does not terminate core transcription
#### Scenario: Knowledge provider fails mid-session
- **WHEN** Hearsay transcription remains healthy but retrieval storage becomes unavailable
- **THEN** Interview Copilot enters degraded cue state while leaving host transcription running
