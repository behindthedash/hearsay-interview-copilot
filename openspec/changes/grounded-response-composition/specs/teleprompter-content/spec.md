## ADDED Requirements

### Requirement: Teleprompter content origin is explicit
Every teleprompter document SHALL identify whether its origin is `prepared` or `generated`. Generated documents SHALL also retain the interviewer query generation and provenance references that produced them.

#### Scenario: Grounded response becomes teleprompter content
- **WHEN** a `generated-script` response is activated
- **THEN** its speech-ready text SHALL be normalized into the same ordered-section model used by prepared content and SHALL retain generated-origin metadata

### Requirement: Generated content is ephemeral by default
Generated teleprompter documents SHALL NOT be written to the prepared-content store or source files unless the user explicitly saves them.

### Requirement: Alignment identity survives presentation refreshes
Rendering or cue updates SHALL NOT recreate an unchanged active teleprompter document or reset its section identities and alignment position.
