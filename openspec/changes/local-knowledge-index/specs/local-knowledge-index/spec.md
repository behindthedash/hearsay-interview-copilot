## MODIFIED Requirements

### Requirement: The user can index a local curated knowledge corpus
The implementation SHALL use a manifest-driven corpus outside the repository and SHALL fail safe when required experience-status metadata is absent.

#### Scenario: Curated corpus is refreshed
- **WHEN** the user refreshes a valid manifest-backed corpus
- **THEN** supported documents are chunked/indexed with stable provenance and missing required metadata is reported rather than guessed

### Requirement: Index refresh is incremental and deterministic
Source hashes and indexing configuration SHALL determine whether content is reused, re-embedded, replaced, or removed.

#### Scenario: One document changes
- **WHEN** only one source hash changes
- **THEN** only that document's active chunk generation is replaced while unchanged documents remain stable
