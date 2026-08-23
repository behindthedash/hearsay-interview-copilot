## 1. Session orchestration
- [x] 1.1 Implement preflight result model and `InterviewCopilotSession` lifecycle.
- [x] 1.2 Register Remote/Local Hearsay handlers through public API.
- [x] 1.3 Wire Remote assembler -> retrieval worker -> cue state -> overlay.

## 2. Degradation/teardown
- [x] 2.1 Keep host transcription independent from consumer-stage failures.
- [x] 2.2 Add reverse-order teardown and stale generation invalidation.
- [x] 2.3 Add manual current-Remote-buffer retrieval action.

## 3. Acceptance
- [x] 3.1 Run end-to-end synthetic host-event journey.
- [ ] 3.2 Run Windows live session acceptance with Hearsay dependency.
