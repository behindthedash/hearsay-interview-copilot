## Decisions

### D1. Deterministic assembler
Implement `RemoteUtteranceAssembler`; no LLM classifier in the MVP boundary detector.

### D2. Remote only for automatic triggers
Local speech may be observed elsewhere but never launches interviewer retrieval automatically.

### D3. Completion rules
Use punctuation+debounce, silence/pause timing where observable, max age/size, and explicit manual flush.

### D4. Duplicate suppression
Use normalized lexical similarity/recent emitted history to suppress overlap artifacts.

### D5. Fake-clock tests
Boundary timing must be deterministic in tests.
