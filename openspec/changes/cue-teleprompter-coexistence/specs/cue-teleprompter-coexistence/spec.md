## MODIFIED Requirements

### Requirement: Cue and teleprompter state remain independent
The presentation coordinator SHALL never use cue arrival to modify speech alignment or use teleprompter advancement to recompute the active interview cue.

#### Scenario: Both streams update close together
- **WHEN** a cue arrives while Local alignment advances
- **THEN** both projections update independently and retain their own state identities

### Requirement: Either aid can run alone
#### Scenario: Cue retrieval is disabled
- **WHEN** the user runs only the teleprompter
- **THEN** prepared-content following remains fully functional without cue state
