## Why

The independent host subscription, question assembly, retrieval, storage, and overlay components need one consumer-owned session lifecycle with preflight and teardown.

## What Changes

- Add `InterviewCopilotSession` orchestration.
- Preflight Hearsay public host capabilities, configured knowledge provider, embedding model, and overlay.
- Register/unregister transcript handlers explicitly.
- Route Remote events to query/retrieval and expose degraded consumer states without terminating host transcription.

## Capabilities

### Modified Capabilities
- `live-interview-copilot-session`
