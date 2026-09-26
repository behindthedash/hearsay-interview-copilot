## Purpose

Provides a local semantic index over a user-owned resume/project corpus so interview questions can retrieve truthful, provenance-preserving evidence without requiring a cloud service.

## Requirements

### Requirement: The user can index a local curated knowledge corpus
The system SHALL accept a user-selected, manifest-driven local corpus and SHALL build a semantic index without requiring those sources to live inside the repository. Indexing SHALL fail safe when required experience-status metadata is absent.

#### Scenario: Corpus outside the repository is indexed
- **WHEN** the user selects a valid local corpus
- **THEN** eligible content is indexed and source provenance is recorded for every resulting chunk

#### Scenario: Curated corpus is refreshed
- **WHEN** the user refreshes a valid manifest-backed corpus
- **THEN** supported documents are chunked/indexed with stable provenance and missing required metadata is reported rather than guessed

### Requirement: Knowledge chunks preserve claim status and provenance
Every indexed chunk SHALL identify its source and carry an experience status distinguishing implemented work, prototype/experiment work, design/architecture knowledge, and hypothetical/planned material. Missing required status SHALL be surfaced rather than defaulted to implemented.

#### Scenario: Hypothetical material is indexed
- **WHEN** a source is marked hypothetical or planned
- **THEN** retrieved chunks retain that status and downstream cueing cannot treat them as implemented experience

### Requirement: Index refresh is incremental and deterministic
Source hashes and indexing configuration SHALL determine whether content is reused, re-embedded, replaced, or removed. Refreshing unchanged content under the same embedding configuration SHALL not create duplicate chunks or unnecessary re-embedding.

#### Scenario: One document changes
- **WHEN** only one source hash changes
- **THEN** only that document's chunks are replaced while unchanged documents remain stable

### Requirement: Semantic retrieval returns ranked evidence with metadata
The system SHALL accept a coherent text query and return a bounded ranked set of relevant chunks including provenance and experience status.

### Requirement: Local mode works without query-time network access
After required models are cached, local indexing and retrieval SHALL operate without sending corpus text, embeddings, or queries to a remote service.
