# knowledge-store-provider Specification

## Purpose

Defines the storage/retrieval contract used by Interview Copilot independently of whether knowledge is stored locally or in an explicitly configured PostgreSQL/pgvector provider.

## Requirements

### Requirement: Knowledge persistence is provider-neutral
Retrieval/indexing orchestration SHALL depend on a `KnowledgeStore` interface rather than SQLite, NumPy, SQL, or pgvector details. The application SHALL use this common knowledge-store contract so supported providers expose equivalent document, chunk, provenance, experience-status, retrieval-scope, and query-result semantics.

#### Scenario: Local provider is selected
- **WHEN** indexing and query operations run with the local provider
- **THEN** callers use the same document/chunk/query result models required of any other provider

#### Scenario: Same corpus uses either provider
- **WHEN** the same synthetic corpus is indexed through local and pgvector providers
- **THEN** both expose equivalent chunk content, provenance, experience status, scope, and result metadata

### Requirement: Retrieval is explicitly scoped
Every query SHALL specify one or more allowed collections/scopes rather than searching every available collection implicitly.

#### Scenario: Career scope only
- **WHEN** retrieval requests only the career collection
- **THEN** chunks from target-role hypothetical collections are excluded

#### Scenario: Career evidence is requested
- **WHEN** the application queries the `career` scope
- **THEN** target-specific hypothetical preparation is excluded unless explicitly included

### Requirement: Embedding configuration is consistent per collection
A collection SHALL record embedding-model identity and vector dimension and SHALL reject incompatible writes/searches rather than mixing vector configurations.

#### Scenario: Incompatible embedding configuration
- **WHEN** a write or search uses an embedding model or vector dimension incompatible with the collection's recorded configuration
- **THEN** the collection rejects the operation

### Requirement: Document re-indexing is atomic
Replacing chunks for one document SHALL be atomic from the perspective of readers.

#### Scenario: Readers query during document replacement
- **WHEN** chunks for one document are being replaced
- **THEN** readers see either the previous chunks or the complete replacement, never a partial replacement

### Requirement: Provider failure degrades the consumer, not Hearsay
A provider failure SHALL surface knowledge-dependent features as unavailable/degraded and SHALL NOT terminate or corrupt the external Hearsay host session.

#### Scenario: Knowledge provider fails
- **WHEN** a knowledge provider operation fails
- **THEN** knowledge-dependent features are unavailable or degraded
- **AND** the external Hearsay host session continues without corruption

### Requirement: The contract is application-scoped
The contract SHALL remain limited to Interview Copilot retrieval needs and SHALL NOT attempt to define a generalized personal-KB platform for unrelated applications.

#### Scenario: Contract scope is evaluated
- **WHEN** the knowledge-store contract's responsibilities are evaluated
- **THEN** they are limited to Interview Copilot retrieval needs and exclude generalized personal-KB responsibilities for unrelated applications
