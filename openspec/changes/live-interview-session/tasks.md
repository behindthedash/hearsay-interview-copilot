## 1. Session orchestration
- [ ] 1.1 Implement preflight result model and `InterviewCopilotSession` lifecycle.
- [ ] 1.2 Register Remote/Local Hearsay handlers through public API.
- [ ] 1.3 Wire Remote assembler -> retrieval worker -> cue state -> overlay.

## 2. Degradation/teardown
- [ ] 2.1 Keep host transcription independent from consumer-stage failures.
- [ ] 2.2 Add reverse-order teardown and stale generation invalidation.
- [ ] 2.3 Add manual current-Remote-buffer retrieval action.

## 3. Acceptance
- [ ] 3.1 Run end-to-end synthetic host-event journey.
- [ ] 3.2 Run Windows live session acceptance with Hearsay dependency.
