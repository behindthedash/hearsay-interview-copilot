## Purpose

Retrieves truthful evidence for a coherent interviewer query and composes a small provenance-preserving cue that can be absorbed at a glance.

## Requirements

### Requirement: Queries retrieve a bounded relevant evidence set
For each eligible query candidate, the system SHALL search the selected knowledge scope and return a bounded ranked evidence set.

### Requirement: Exact terms can reinforce semantic relevance
Ranking SHALL allow exact high-signal technology, project, skill, and domain terms to reinforce semantic similarity without excluding semantic alternatives.

### Requirement: Cues preserve truth status and provenance
Every supporting point SHALL be traceable to source material and retain experience status. Implemented evidence may be primary experience; prototype/design material SHALL remain labeled; hypothetical material SHALL never be promoted into the implemented-story pool.

#### Scenario: Implemented and hypothetical evidence both match
- **WHEN** both are retrieved
- **THEN** implemented evidence may form the primary story and hypothetical evidence may only appear as a clearly labeled role/application bridge

### Requirement: Default cues are concise and structured
The default cue SHALL contain the interviewer intent/question, at most one primary story, a bounded supporting-point list, provenance/status indicators, and optional clearly labeled role-bridge material. It SHALL NOT default to a long scripted answer.

### Requirement: Stale retrieval results do not replace newer cues
Retrieval work SHALL be bound to session/query generation. A result superseded by a newer query SHALL NOT become the active cue.

#### Scenario: Generation N finishes after N+1 is current
- **WHEN** an older retrieval completes late
- **THEN** it is discarded from active presentation and cannot replace the newer cue

### Requirement: Retrieval failure is visible and non-fatal
Knowledge/embedding/provider failure or no-match SHALL produce a concise unavailable/no-match cue state and SHALL NOT terminate the Hearsay host session.
