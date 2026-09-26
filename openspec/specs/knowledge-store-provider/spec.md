## Purpose

Defines the storage/retrieval contract used by Interview Copilot independently of whether knowledge is stored locally or in an explicitly configured PostgreSQL/pgvector provider.

## Requirements

### Requirement: Knowledge persistence is provider-neutral
Retrieval and indexing orchestration SHALL depend on a `KnowledgeStore` interface rather than SQLite, NumPy, SQL, or pgvector details, so supported providers expose equivalent document, chunk, provenance, experience-status, retrieval-scope, and query-result semantics.

#### Scenario: Same corpus uses either provider
- **WHEN** the same synthetic corpus is indexed through local and pgvector providers
- **THEN** both expose equivalent chunk content, provenance, experience status, scope, and result metadata

#### Scenario: Local provider is selected
- **WHEN** indexing and query operations run with the local provider
- **THEN** callers use the same document/chunk/query result models required of any other provider

### Requirement: Retrieval is explicitly scoped
Every query SHALL specify one or more allowed collections/scopes, and the store SHALL NOT search collections that were not requested.

#### Scenario: Career scope only
- **WHEN** retrieval requests only the career collection
- **THEN** chunks from target-role hypothetical collections are excluded

### Requirement: Embedding configuration is consistent per collection
A collection SHALL record embedding-model identity and vector dimension and SHALL reject incompatible writes/searches rather than mixing vector configurations.

### Requirement: Document re-indexing is atomic
Replacing chunks for one document SHALL be atomic from the perspective of readers.

### Requirement: Provider failure degrades the consumer, not Hearsay
A provider failure SHALL surface knowledge-dependent features as unavailable/degraded and SHALL NOT terminate or corrupt the external Hearsay host session.

### Requirement: The contract is application-scoped
The contract SHALL remain limited to Interview Copilot retrieval needs and SHALL NOT attempt to define a generalized personal-KB platform for unrelated applications.
