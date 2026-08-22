## Decisions

### D1. Direct psycopg is sufficient
Avoid adding SQLAlchemy solely for this small provider.

### D2. Schema is application-scoped
Use clearly owned collection/document/chunk tables and schema versioning; do not define a generalized personal-KB platform.

### D3. Exact cosine first
Exact pgvector cosine retrieval is sufficient for the initial corpus. Add HNSW only after profiling justifies it and dimension is known.

### D4. Secrets are injected
Connection material comes from environment/credential injection (for example `INTERVIEW_COPILOT_KB_DATABASE_URL`) and is redacted from logs/errors. Remote deployments support explicit TLS modes.
