# knowledge-store-provider Specification

## Purpose

Defines the storage/retrieval contract used by Interview Copilot independently of whether knowledge is stored locally or in an explicitly configured PostgreSQL/pgvector provider.

## Requirements

### Requirement: Knowledge persistence is provider neutral
Retrieval/indexing orchestration SHALL depend on a `KnowledgeStore` interface rather than SQLite, NumPy, SQL, or pgvector details.

#### Scenario: Local provider is selected
- **WHEN** indexing and query operations run with the local provider
- **THEN** callers use the same document/chunk/query result models required of any other provider

#### Scenario: Same corpus uses either provider
- **WHEN** the same synthetic corpus is indexed through local and pgvector providers
- **THEN** both expose equivalent chunk content, provenance, experience status, scope, and result metadata

### Requirement: Retrieval is explicitly scoped
Every query SHALL specify one or more allowed collections/scopes.

#### Scenario: Career scope only
- **WHEN** retrieval requests only the career collection
- **THEN** chunks from target-role hypothetical collections are excluded

#### Scenario: Career evidence is requested
- **WHEN** the application queries the `career` scope
- **THEN** target-specific hypothetical preparation is excluded unless explicitly included

### Requirement: Embedding configuration is consistent per collection
A collection SHALL record embedding-model identity and vector dimension and SHALL reject incompatible writes/searches rather than mixing vector configurations.

#### Scenario: Incompatible embedding configuration is used
- **WHEN** a write or search uses a model identity or vector dimension incompatible with the collection's recorded configuration
- **THEN** the store rejects the operation rather than mixing vector configurations

### Requirement: Document re-indexing is atomic
Replacing chunks for one document SHALL be atomic from the perspective of readers.

#### Scenario: Document chunks are replaced
- **WHEN** readers query while a document's chunks are being replaced
- **THEN** they observe either the previous chunks or the replacement chunks, never a partial replacement

### Requirement: Provider failure degrades the consumer, not Hearsay
A provider failure SHALL surface knowledge-dependent features as unavailable/degraded and SHALL NOT terminate or corrupt the external Hearsay host session.

#### Scenario: Knowledge provider fails
- **WHEN** a knowledge provider fails during a host session
- **THEN** knowledge-dependent features become unavailable or degraded
- **AND** the external Hearsay host session continues without termination or corruption

### Requirement: The contract is application-scoped
The contract SHALL remain limited to Interview Copilot retrieval needs and SHALL NOT attempt to define a generalized personal-KB platform for unrelated applications.

#### Scenario: Contract scope is evaluated
- **WHEN** determining which capabilities belong in the knowledge-store contract
- **THEN** the contract covers Interview Copilot retrieval needs and excludes generalized personal-KB capabilities for unrelated applications
