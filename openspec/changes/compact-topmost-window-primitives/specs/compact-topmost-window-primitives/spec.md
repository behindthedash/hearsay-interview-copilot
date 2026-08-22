## MODIFIED Requirements

### Requirement: Topmost presentation is reusable
The shared primitive SHALL own topmost, opacity, geometry persistence, and visible-screen recovery while leaving domain rendering/state to consumers.

#### Scenario: Cue and teleprompter create windows
- **WHEN** both use the primitive
- **THEN** they receive consistent presentation mechanics without sharing domain state
