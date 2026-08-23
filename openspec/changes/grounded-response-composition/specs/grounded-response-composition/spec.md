## ADDED Requirements

### Requirement: Each eligible interviewer turn produces a response mode
For each eligible interviewer query generation, the system SHALL produce exactly one active response mode from `generated-script`, `cue-only`, `clarification`, or `unavailable`.

#### Scenario: Strong evidence supports a speech-ready response
- **WHEN** retrieval returns sufficiently relevant, internally usable evidence and scripted generation is enabled
- **THEN** the response coordinator MAY produce a `generated-script` response with supporting cues

#### Scenario: Evidence is insufficient for a script
- **WHEN** evidence is partial, conflicting, weak, or ambiguous
- **THEN** the response coordinator SHALL choose `cue-only`, `clarification`, or `unavailable` rather than inventing a complete answer

### Requirement: Generated scripts are evidence-grounded
A generated script SHALL be composed only from retrieved evidence and SHALL preserve source provenance and experience/truth status. The system SHALL NOT introduce unsupported projects, responsibilities, technologies, metrics, outcomes, or claims of implementation.

#### Scenario: Retrieved material is hypothetical
- **WHEN** evidence describes a design, proposal, prototype, or hypothetical example
- **THEN** generated wording SHALL retain that status and SHALL NOT present it as production experience

### Requirement: Generated scripts are optimized for spoken delivery
A generated script SHALL be concise, conversational, and structured for immediate speech rather than essay-style reading. Supporting details MAY be emitted as separate cues instead of expanding the script.

### Requirement: Response packages remain generation-bound
Each response package SHALL carry the interviewer query generation that produced it. A response package superseded by a newer query generation SHALL NOT become active or replace newer guidance.

### Requirement: New responses do not interrupt an answer in progress
A newly composed response SHALL be staged rather than replacing the active teleprompter document while Local speech indicates the user is already answering, unless the user explicitly activates the new response.

#### Scenario: New question arrives while user is still speaking
- **WHEN** a new response package completes while the current answer remains active
- **THEN** the system SHALL expose the new package as pending and preserve the active teleprompter position

### Requirement: Generated response data is transient by default
Generated scripts, transient evidence packages, and response-state metadata SHALL remain session-scoped unless the user explicitly saves them.
