## MODIFIED Requirements

### Requirement: Active prepared content is glanceable
The UI SHALL emphasize the active section and nearby context without requiring per-word karaoke behavior or continuous fixed-speed scrolling.

#### Scenario: Alignment changes section
- **WHEN** a new active section is selected
- **THEN** it moves into the configured reading position with clear visual emphasis

### Requirement: Manual control always overrides following
#### Scenario: User pauses follow mode
- **WHEN** follow mode is paused
- **THEN** automatic alignment may continue computing but cannot move the displayed active section until resumed
