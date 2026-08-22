## Decisions

### D1. Latest-query-wins worker
Bound the input queue and key work by `(session_id, generation)`; newer generation invalidates older output.

### D2. Hybrid deterministic ranking
Use vector similarity for candidate selection plus lexical/metadata boosts for exact project/technology/domain terms. No LLM reranker in MVP.

### D3. Structured cue model
`InterviewCue` includes query/intent, one recommended story, bounded bullets, role bridge, provenance/status, confidence, latency, session/generation.

### D4. Confidence means retrieval quality
Do not present confidence as truth probability.
