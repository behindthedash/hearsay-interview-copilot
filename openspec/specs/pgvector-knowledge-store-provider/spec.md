# pgvector-knowledge-store-provider Specification

## Purpose

Implements the Interview Copilot knowledge-store contract using an explicitly configured PostgreSQL database with pgvector.

## Requirements

### Requirement: pgvector capability is validated before provider use
Initialization SHALL validate connection, TLS policy, vector capability, schema version, and collection embedding compatibility before accepting writes/queries.

#### Scenario: Database lacks vector support
- **WHEN** the provider initializes against a database without the extension
- **THEN** it installs it only when explicitly authorized or reports the exact prerequisite without partially creating the schema

#### Scenario: Remote database is healthy
- **WHEN** provider health runs against a correctly configured database
- **THEN** it reports usable schema/vector capability without exposing credentials

### Requirement: Vector search preserves the provider contract
The provider SHALL perform top-k vector retrieval with collection-compatible embeddings and return content, score, provenance, experience status, and metadata using the common store contract.

#### Scenario: Retrieve matching knowledge
- **WHEN** a top-k vector query uses embeddings compatible with the collection
- **THEN** the provider returns matching content, score, provenance, experience status, and metadata using the common store contract

### Requirement: Remote credentials are secret material
Database credentials and complete connection strings SHALL NOT be committed, rendered in cues, or written to normal logs.

#### Scenario: Provider uses database credentials
- **WHEN** database credentials or a complete connection string are used by the provider
- **THEN** they are not committed, rendered in cues, or written to normal logs

### Requirement: Remote connections honor explicit TLS policy
The provider SHALL support explicit PostgreSQL SSL/TLS configuration and SHALL NOT silently downgrade it.

#### Scenario: Explicit TLS policy is configured
- **WHEN** the provider connects with an explicit PostgreSQL SSL/TLS policy
- **THEN** it honors that policy without silently downgrading it

### Requirement: Schema bootstrap is reproducible and application-scoped
The provider SHALL provide an idempotent bootstrap/migration path for application-owned tables, indexes, vector capability, and schema version. Object names SHALL clearly belong to Interview Copilot rather than implying a universal personal-KB schema.

#### Scenario: Bootstrap is repeated
- **WHEN** the bootstrap/migration path runs again against an initialized database
- **THEN** application-owned tables, indexes, vector capability, and schema version remain consistently initialized
- **AND** object names clearly belong to Interview Copilot

### Requirement: PostgreSQL remains optional
When the pgvector provider is not selected, the application SHALL not attempt a PostgreSQL connection and local knowledge retrieval SHALL remain available.

#### Scenario: Local provider is configured
- **WHEN** Interview Copilot starts in local mode
- **THEN** psycopg/pgvector are not required or imported and no PostgreSQL connection is attempted
