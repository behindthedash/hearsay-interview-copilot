## MODIFIED Requirements

### Requirement: The user can index a local curated knowledge corpus
The system SHALL accept a user-selected local corpus containing supported text documents and SHALL build a semantic index without requiring those sources to live inside the repository. The implementation SHALL use a manifest-driven corpus outside the repository and SHALL fail safe when required experience-status metadata is absent.

#### Scenario: Corpus outside the repository is indexed
- **WHEN** the user selects a valid local corpus
- **THEN** eligible content is indexed and source provenance is recorded for every resulting chunk

#### Scenario: Curated corpus is refreshed
- **WHEN** the user refreshes a valid manifest-backed corpus
- **THEN** supported documents are chunked/indexed with stable provenance and missing required metadata is reported rather than guessed

### Requirement: Index refresh is incremental and deterministic
The system SHALL detect unchanged, changed, new, and removed sources. Refreshing unchanged content under the same embedding configuration SHALL not create duplicate chunks or unnecessary re-embedding. Source hashes and indexing configuration SHALL determine whether content is reused, re-embedded, replaced, or removed.

#### Scenario: One source changes
- **WHEN** one indexed source changes
- **THEN** only its derived chunks are replaced or updated while unchanged sources remain intact

#### Scenario: One document changes
- **WHEN** only one source hash changes
- **THEN** only that document's active chunk generation is replaced while unchanged documents remain stable
