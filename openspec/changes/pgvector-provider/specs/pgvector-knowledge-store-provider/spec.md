## MODIFIED Requirements

### Requirement: pgvector capability is validated before provider use
Initialization SHALL validate connection, TLS policy, vector capability, schema version, and collection embedding compatibility before accepting writes/queries.

#### Scenario: Remote database is healthy
- **WHEN** provider health runs against a correctly configured database
- **THEN** it reports usable schema/vector capability without exposing credentials

### Requirement: PostgreSQL remains optional
#### Scenario: Local provider is configured
- **WHEN** Interview Copilot starts in local mode
- **THEN** psycopg/pgvector are not required or imported and no PostgreSQL connection is attempted
