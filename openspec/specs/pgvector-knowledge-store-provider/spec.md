## Purpose

Implements the Interview Copilot knowledge-store contract using an explicitly configured PostgreSQL database with pgvector.

## Requirements

### Requirement: pgvector capability is validated before use
The provider SHALL validate that the configured database supports the `vector` extension and the application-owned schema before accepting indexing or retrieval work.

#### Scenario: Database lacks vector support
- **WHEN** the provider initializes against a database without the extension
- **THEN** it installs it only when explicitly authorized or reports the exact prerequisite without partially creating the schema

### Requirement: Vector search preserves the provider contract
The provider SHALL perform top-k vector retrieval with collection-compatible embeddings and return content, score, provenance, experience status, and metadata using the common store contract.

### Requirement: Remote credentials are secret material
Database credentials and complete connection strings SHALL NOT be committed, rendered in cues, or written to normal logs.

### Requirement: Remote connections honor explicit TLS policy
The provider SHALL support explicit PostgreSQL SSL/TLS configuration and SHALL NOT silently downgrade it.

### Requirement: Schema bootstrap is reproducible and application-scoped
The provider SHALL provide an idempotent bootstrap/migration path for application-owned tables, indexes, vector capability, and schema version. Object names SHALL clearly belong to Interview Copilot rather than implying a universal personal-KB schema.

### Requirement: PostgreSQL remains optional
When the pgvector provider is not selected, the application SHALL not attempt a PostgreSQL connection and local knowledge retrieval SHALL remain available.
