## Decisions

### D1. Consumer owns orchestration
`InterviewCopilotSession` coordinates host subscription handles, utterance assembler, retrieval worker, cue state, teleprompter subscriptions, and UI lifecycle.

### D2. Hearsay is an external dependency
Use only documented host import/subscriber/session APIs. Never reach into its application queues or widgets.

### D3. Prewarm before ready
Verify provider/index, embedding cache/model, host Remote source/live profile availability, and overlay initialization before reporting ready.

### D4. Reverse-order teardown
Invalidate query generations, stop workers, unregister handlers, clear transient state, then release UI/session resources.
