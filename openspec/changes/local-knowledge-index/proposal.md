## Why

Interview retrieval needs a local-first index over user-owned career/interview material before cue generation can be implemented.

## What Changes

- Add curated corpus manifest parsing and validation.
- Chunk Markdown/text deterministically with provenance and experience status.
- Add local embeddings and incremental refresh.
- Persist local index metadata and support top-k semantic retrieval offline after model setup.

## Capabilities

### Modified Capabilities
- `local-knowledge-index`
