## MODIFIED Requirements

### Requirement: Adjacent Remote segments form coherent turns
The system SHALL maintain a bounded in-memory buffer that can combine adjacent finalized `Remote` segments belonging to the same interviewer turn. The assembler SHALL maintain bounded per-session Remote state and SHALL emit coherent candidates rather than searching individual transcript fragments.

#### Scenario: Question spans multiple events
- **WHEN** adjacent Remote events arrive within the active utterance window
- **THEN** they are combined until a deterministic completion condition closes the turn

### Requirement: Query candidates carry supersession identity
Every candidate SHALL carry session identity and a monotonically advancing generation/order value so downstream work can reject stale results. Each emitted candidate SHALL carry session identity and a monotonically increasing generation.

#### Scenario: New question follows old question
- **WHEN** a second candidate is emitted in the same session
- **THEN** its generation is newer and can invalidate stale downstream work
