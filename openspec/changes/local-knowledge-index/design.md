## Decisions

### D1. Corpus stays outside Git
Use a user-selected directory plus `corpus.json` manifest. Metadata includes source path/title/topics/skills/project and required `experience_status`.

### D2. Deterministic chunking
Use headings/paragraph boundaries with stable chunk identifiers derived from source identity, ordinal, and normalized content digest.

### D3. Local embedding adapter
Start with FastEmbed/ONNX behind an embedding interface. Cache/model setup may require network once; query/indexing remains local afterwards.

### D4. Local persistence
Use SQLite for document/chunk metadata and a NumPy-backed vector search baseline for the initial corpus size. Provider abstraction work is separate.

## Expected Package
- `src/interview_copilot/knowledge/`
- synthetic corpus fixtures/tests only
