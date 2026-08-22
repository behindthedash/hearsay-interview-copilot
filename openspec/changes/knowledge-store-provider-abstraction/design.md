## Decisions

### D1. Store contract
Representative operations: `ensure_collection`, `upsert_document`, `replace_document_chunks`, `delete_document`, `query`, `get_chunk`, `health`, `stats`.

### D2. Shared domain models
Document/chunk/provenance/experience-status/query-result types live above providers.

### D3. Embedding identity belongs to collection
Collection metadata records model identifier and dimension; incompatible writes/searches fail explicitly.

### D4. Atomic replace-on-reindex
Readers see either the prior complete chunk generation or the new complete generation.
