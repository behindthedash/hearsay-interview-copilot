# remote-query-boundaries Specification

## Purpose

Turns finalized Hearsay `Remote` speech into bounded, coherent interviewer query candidates without searching on every transcript fragment.

## Requirements

### Requirement: Automatic query assembly uses Remote speech only
The system SHALL use `Remote` transcript events for automatic interviewer-query assembly and SHALL NOT treat `Local` microphone speech as interviewer intent.

#### Scenario: Local speech is excluded from automatic assembly
- **WHEN** a `Local` microphone transcript event arrives
- **THEN** it is not used for automatic interviewer-query assembly

### Requirement: Adjacent remote segments are assembled into coherent utterances
The assembler SHALL maintain bounded per-session Remote state and SHALL emit coherent candidates rather than searching individual transcript fragments.

#### Scenario: Question spans multiple events
- **WHEN** adjacent Remote events arrive within the active utterance window
- **THEN** they are combined until a deterministic completion condition closes the turn

### Requirement: Query emission is selective and bounded
The system SHALL emit a query candidate only when a configured completion condition or manual trigger is met and SHALL impose maximum age/size bounds.

#### Scenario: Query emission requires a completion condition or manual trigger
- **WHEN** buffered Remote speech has not met a configured completion condition and no manual trigger occurs
- **THEN** the system does not emit a query candidate
- **AND** the buffered speech remains subject to maximum age/size bounds

### Requirement: Duplicate boundaries do not flood retrieval
The system SHALL suppress materially duplicate candidates caused by overlap/repetition or multiple completion signals for the same turn.

#### Scenario: Repeated completion signals do not repeat a candidate
- **WHEN** multiple completion signals for the same turn produce materially duplicate candidates
- **THEN** the system suppresses the duplicate candidates

### Requirement: Query candidates carry supersession identity
Each emitted candidate SHALL carry session identity and a monotonically increasing generation.

#### Scenario: New question follows old question
- **WHEN** a second candidate is emitted in the same session
- **THEN** its generation is newer and can invalidate stale downstream work

### Requirement: Session teardown clears utterance state
Detaching from or replacing a Hearsay session SHALL clear buffered Remote speech and query-generation state.

#### Scenario: Session detachment clears assembly state
- **WHEN** the Hearsay session is detached or replaced
- **THEN** buffered Remote speech and query-generation state are cleared
