## 1. Optional dependencies
- [ ] 1.1 Add optional psycopg/pgvector dependency group and lazy imports.

## 2. Schema/provider
- [ ] 2.1 Add idempotent bootstrap/migration and vector-extension validation.
- [ ] 2.2 Implement collection/document/chunk persistence and cosine query.
- [ ] 2.3 Add TLS/secret redaction and health reporting.

## 3. Tests
- [ ] 3.1 Run provider conformance suite against pgvector when `INTERVIEW_COPILOT_TEST_PG_URL` is configured.
- [ ] 3.2 Clearly skip remote integration tests otherwise.
