# remote-query-boundaries Specification

## Purpose

Turns finalized Hearsay `Remote` speech into bounded, coherent interviewer query candidates without searching on every transcript fragment.

## Requirements

### Requirement: Automatic query assembly uses Remote speech only
The system SHALL use `Remote` transcript events for automatic interviewer-query assembly and SHALL NOT treat `Local` microphone speech as interviewer intent.

#### Scenario: Local speech arrives
- **WHEN** a `Local` transcript event arrives
- **THEN** it is excluded from automatic interviewer-query assembly

### Requirement: Adjacent remote segments are assembled into coherent utterances
The assembler SHALL maintain a bounded in-memory buffer per session and SHALL emit coherent candidates assembled from adjacent finalized `Remote` segments of the same interviewer turn rather than searching individual transcript fragments.

#### Scenario: Question spans multiple events
- **WHEN** adjacent Remote events arrive within the active utterance window
- **THEN** they are combined until a deterministic completion condition closes the turn

### Requirement: Query emission is selective and bounded
The system SHALL emit a query candidate only when a configured completion condition or manual trigger is met and SHALL impose maximum age/size bounds.

#### Scenario: A turn reaches its configured age or size limit
- **WHEN** buffered speech reaches the configured maximum age or size
- **THEN** the system closes the turn and emits a query candidate

### Requirement: Duplicate boundaries do not flood retrieval
The system SHALL suppress materially duplicate candidates caused by overlap/repetition or multiple completion signals for the same turn.

#### Scenario: Multiple signals close the same turn
- **WHEN** multiple completion signals would emit materially duplicate candidates for the same turn
- **THEN** the system suppresses the duplicates

### Requirement: Query candidates carry supersession identity
Each emitted candidate SHALL carry session identity and a monotonically increasing generation so downstream work can reject stale results.

#### Scenario: New question follows old question
- **WHEN** a second candidate is emitted in the same session
- **THEN** its generation is newer and can invalidate stale downstream work

### Requirement: Session teardown clears utterance state
Detaching from or replacing a Hearsay session SHALL clear buffered Remote speech and query-generation state.

#### Scenario: A Hearsay session ends or is replaced
- **WHEN** the system detaches from or replaces a Hearsay session
- **THEN** it clears that session's buffered Remote speech and query-generation state
