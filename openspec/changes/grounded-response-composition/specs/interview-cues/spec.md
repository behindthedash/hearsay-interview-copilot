## MODIFIED Requirements

### Requirement: Default cues are concise and structured
The cue projection SHALL remain concise and glanceable: interviewer intent/question, at most one primary story, a bounded supporting-point list, provenance/status indicators, and optional clearly labeled role-bridge material. A cue SHALL NOT itself expand into a long scripted answer. When grounded response composition selects `generated-script`, the full speech-ready response SHALL live in teleprompter content while the cue projection remains a bounded supporting aid.

#### Scenario: Generated script has supporting evidence
- **WHEN** grounded response composition produces a generated script with supporting cues
- **THEN** the cue view SHALL show only the bounded supporting points and SHALL NOT duplicate the full script

### Requirement: Retrieval failure is visible and non-fatal
Knowledge/embedding/provider failure or no-match SHALL produce evidence state that can resolve to `clarification` or `unavailable` response behavior and SHALL NOT terminate the Hearsay host session.

#### Scenario: No trustworthy evidence is available
- **WHEN** retrieval returns no eligible evidence for the current question
- **THEN** the cue/response pipeline SHALL expose a no-match state and SHALL NOT generate an unsupported scripted answer
