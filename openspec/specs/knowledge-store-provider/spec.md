# knowledge-store-provider Specification

## Purpose

Defines the storage/retrieval contract used by Interview Copilot independently of whether knowledge is stored locally or in an explicitly configured PostgreSQL/pgvector provider.

## Requirements

### Requirement: Knowledge persistence is provider neutral
Retrieval and indexing orchestration SHALL depend on a `KnowledgeStore` interface rather than SQLite, NumPy, SQL, or pgvector details.

The application SHALL use a common knowledge-store contract so supported providers expose equivalent document, chunk, provenance, experience-status, retrieval-scope, and query-result semantics.

#### Scenario: Same corpus uses either provider
- **WHEN** the same synthetic corpus is indexed through local and pgvector providers
- **THEN** both expose equivalent chunk content, provenance, experience status, scope, and result metadata

#### Scenario: Local provider is selected
- **WHEN** indexing and query operations run with the local provider
- **THEN** callers use the same document/chunk/query result models required of any other provider

### Requirement: Retrieval is explicitly scoped
Every query SHALL specify one or more allowed collections or scopes.

The store SHALL require an explicit collection or retrieval scope rather than searching every available collection implicitly.

#### Scenario: Career evidence is requested
- **WHEN** the application queries the `career` scope
- **THEN** target-specific hypothetical preparation is excluded unless explicitly included

#### Scenario: Career scope only
- **WHEN** retrieval requests only the career collection
- **THEN** chunks from target-role hypothetical collections are excluded

### Requirement: Embedding configuration is consistent per collection
A collection SHALL record embedding-model identity and vector dimension and SHALL reject incompatible writes/searches rather than mixing vector configurations.

#### Scenario: Embedding configuration differs from the collection
- **WHEN** a write or search uses an embedding model or vector dimension that differs from the collection's recorded configuration
- **THEN** the store rejects the operation

### Requirement: Document re-indexing is atomic
Replacing chunks for one document SHALL be atomic from the perspective of readers.

#### Scenario: A reader queries during re-indexing
- **WHEN** a reader accesses a document while its chunks are being replaced
- **THEN** the reader sees either the old chunk set or the new chunk set in full

### Requirement: Provider failure degrades the consumer, not Hearsay
A provider failure SHALL surface knowledge-dependent features as unavailable/degraded and SHALL NOT terminate or corrupt the external Hearsay host session.

#### Scenario: The knowledge store fails during a host session
- **WHEN** a provider fails during an external Hearsay host session
- **THEN** the application reports affected knowledge-dependent features as unavailable or degraded
- **AND** the host session continues with its state intact

### Requirement: The contract is application-scoped
The contract SHALL remain limited to Interview Copilot retrieval needs and SHALL NOT attempt to define a generalized personal-KB platform for unrelated applications.

#### Scenario: An unrelated application needs a storage operation
- **WHEN** a proposed storage operation serves a use case outside Interview Copilot retrieval
- **THEN** the operation stays outside the knowledge-store contract
