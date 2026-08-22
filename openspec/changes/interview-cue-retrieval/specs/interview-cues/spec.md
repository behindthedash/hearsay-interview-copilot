## MODIFIED Requirements

### Requirement: Cues preserve truth status and provenance
Implemented evidence may be primary experience; prototype/design material SHALL remain labeled; hypothetical material SHALL never be promoted into the implemented-story pool.

#### Scenario: Implemented and hypothetical evidence both match
- **WHEN** both are retrieved
- **THEN** implemented evidence may form the primary story and hypothetical evidence may only appear as a clearly labeled role/application bridge

### Requirement: Stale retrieval results do not replace newer cues
#### Scenario: Generation N finishes after N+1 is current
- **WHEN** an older retrieval completes late
- **THEN** it is discarded from active presentation and cannot replace the newer cue
