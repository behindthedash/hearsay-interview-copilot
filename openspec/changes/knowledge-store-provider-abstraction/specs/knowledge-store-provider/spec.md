## MODIFIED Requirements

### Requirement: Knowledge persistence is provider neutral
Retrieval/indexing orchestration SHALL depend on a `KnowledgeStore` interface rather than SQLite, NumPy, SQL, or pgvector details.

#### Scenario: Local provider is selected
- **WHEN** indexing and query operations run with the local provider
- **THEN** callers use the same document/chunk/query result models required of any other provider

### Requirement: Retrieval is explicitly scoped
Every query SHALL specify one or more allowed collections/scopes.

#### Scenario: Career scope only
- **WHEN** retrieval requests only the career collection
- **THEN** chunks from target-role hypothetical collections are excluded
