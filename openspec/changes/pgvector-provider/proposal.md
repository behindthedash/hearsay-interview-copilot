## Why

An optional private PostgreSQL + pgvector backend provides durable remote knowledge storage without changing Interview Copilot's retrieval contract.

## What Changes

- Implement `KnowledgeStore` with psycopg/pgvector.
- Add application-scoped idempotent schema bootstrap/migrations.
- Validate vector extension/model dimension compatibility.
- Add secret-safe TLS configuration and degraded health behavior.

## Capabilities

### Modified Capabilities
- `pgvector-knowledge-store-provider`
- `knowledge-store-provider`
