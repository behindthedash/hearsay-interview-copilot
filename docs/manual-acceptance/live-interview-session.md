# Live Interview Session — Windows Acceptance

Run this after installing/running Hearsay and Interview Copilot in the same Python process/environment where the supported `hearsay.events` and `hearsay.host` imports are available.

## Preconditions

- Hearsay is configured for a live interview session using `SessionOutputMode.LIVE_ONLY`.
- Hearsay uses `LIVE_TRANSCRIPTION_PROFILE`.
- Remote/system audio and Local microphone transcription are both working.
- Interview Copilot has a healthy configured knowledge provider with indexed chunks.
- The embedding model is available locally/cached as required.
- The cue overlay opens successfully.

## Acceptance journey

1. Start/attach `InterviewCopilotSession` with a fresh session ID.
   - Preflight reports Hearsay host, knowledge provider, embedding model, and overlay ready.
   - Two public transcript subscriptions are registered: Remote and Local.
   - Copilot enters `listening` without starting or stopping Hearsay itself.

2. Ask an interviewer question through Zoom or Teams system audio.
   - Finalized `Remote` speech is assembled into one coherent query.
   - Overlay transitions to retrieving and then ready/no-match/unavailable.
   - A newer interviewer question supersedes an older in-flight retrieval result.

3. Speak locally while answering.
   - Finalized `Local` speech does not launch interviewer-query retrieval.
   - Local events remain available to the configured downstream Local-speech callback for future teleprompter alignment.

4. Exercise manual retrieval before the normal boundary fires.
   - With Remote text buffered, invoke `retrieve_current_remote_buffer()`.
   - The current buffer becomes a retrieval query exactly once.

5. Simulate a consumer-stage failure while Hearsay remains healthy.
   - Make the knowledge provider or overlay unavailable.
   - Copilot reports a degraded/unavailable state.
   - Hearsay continues capturing/transcribing and is not stopped by the consumer.

6. Stop Interview Copilot.
   - Retrieval work is invalidated/stopped first.
   - Local and Remote subscriptions are closed.
   - Buffered Remote state and current cue state are cleared.
   - Consumer-owned provider resources are released when configured.
   - Hearsay host lifecycle remains under Hearsay/session-owner control.

## Privacy check

Confirm Hearsay does not create its normal persisted transcript for the interview session while `LIVE_ONLY` is selected. Transcript persistence must require an explicit host/session choice rather than being enabled by Interview Copilot.
