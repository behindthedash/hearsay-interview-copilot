## Purpose

Provides a local semantic index over a user-owned resume/project corpus so interview questions can retrieve truthful, provenance-preserving evidence without requiring a cloud service.

## Requirements

### Requirement: The user can index a local curated knowledge corpus
The system SHALL accept a user-selected local corpus containing supported text documents and SHALL build a semantic index without requiring those sources to live inside the repository.

#### Scenario: Corpus outside the repository is indexed
- **WHEN** the user selects a valid local corpus
- **THEN** eligible content is indexed and source provenance is recorded for every resulting chunk

### Requirement: Knowledge chunks preserve claim status and provenance
Every indexed chunk SHALL identify its source and carry an experience status distinguishing implemented work, prototype/experiment work, design/architecture knowledge, and hypothetical/planned material. Missing required status SHALL be surfaced rather than defaulted to implemented.

#### Scenario: Hypothetical material is indexed
- **WHEN** a source is marked hypothetical or planned
- **THEN** retrieved chunks retain that status and downstream cueing cannot treat them as implemented experience

### Requirement: Index refresh is incremental and deterministic
The system SHALL detect unchanged, changed, new, and removed sources. Refreshing unchanged content under the same embedding configuration SHALL not create duplicate chunks or unnecessary re-embedding.

#### Scenario: One source changes
- **WHEN** one indexed source changes
- **THEN** only its derived chunks are replaced or updated while unchanged sources remain intact

### Requirement: Semantic retrieval returns ranked evidence with metadata
The system SHALL accept a coherent text query and return a bounded ranked set of relevant chunks including provenance and experience status.

### Requirement: Local mode works without query-time network access
After required models are cached, local indexing and retrieval SHALL operate without sending corpus text, embeddings, or queries to a remote service.
