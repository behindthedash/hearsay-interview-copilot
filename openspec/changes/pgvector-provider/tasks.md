## 1. Optional dependencies
- [x] 1.1 Add optional psycopg/pgvector dependency group and lazy imports.

## 2. Schema/provider
- [x] 2.1 Add idempotent bootstrap/migration and vector-extension validation.
- [x] 2.2 Implement collection/document/chunk persistence and cosine query.
- [x] 2.3 Add TLS/secret redaction and health reporting.

## 3. Tests
- [x] 3.1 Run provider conformance suite against pgvector when `INTERVIEW_COPILOT_TEST_PG_URL` is configured.
- [x] 3.2 Clearly skip remote integration tests otherwise.
