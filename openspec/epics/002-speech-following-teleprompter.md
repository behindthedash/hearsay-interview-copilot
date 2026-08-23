# Epic 002 — Speech-Following Teleprompter

## Business Objective

Provide a near-camera spoken-response surface that can follow either prepared interview material or dynamically composed grounded responses while the user speaks naturally.

This is a consumer feature owned by Interview Copilot. Hearsay remains unaware of scripts, generated responses, talking points, alignment state, knowledge retrieval, and interview presentation behavior.

## Architectural Principles

1. **The teleprompter presents active response content.** Prepared and generated content share one speech-following document model with explicit origin metadata.
2. **Generated responses remain grounded and transient.** Response composition happens upstream; the teleprompter presents what the grounded response coordinator produced and does not invent content.
3. **Alignment follows natural speech rather than exact words.** It tolerates paraphrase, skips, pauses, restarts, and rejoining.
4. **Only Local user speech advances content.** `Remote` interviewer speech never moves the teleprompter.
5. **Local alignment uses a provider boundary.** Hearsay `Local` events are supported, but a consumer-owned lower-latency Local recognizer may drive alignment when required without coupling to Hearsay internals.
6. **Manual control always wins.** Pause, navigation, pending-response activation, and dismissal override automatic behavior.
7. **New responses do not interrupt speech in progress.** A newly generated answer is staged until it can safely become active or the user explicitly selects it.
8. **Cues and script alignment remain separate projections.** A generated response may carry supporting cues, but cue updates do not move alignment and alignment does not recompute cues.
9. **TalkPrompter is the behavioral reference.** Pause-on-pause, off-script waiting, rejoin/recovery, backward correction, and near-camera presentation are target behaviors; reuse or port MIT-licensed implementation where it is technically sensible.
10. **Shared compact-window infrastructure is owned by this application.**

## Capabilities

- Teleprompter content model with prepared/generated origins
- Local speech alignment provider boundary
- Compact topmost presentation primitives
- Speech-following teleprompter UI
- Pending generated-response activation
- Cue/teleprompter coexistence
- Grounded-response presentation integration

## Acceptance Journey

1. The user loads prepared material or Interview Copilot stages a grounded generated response for an interviewer question.
2. The selected response becomes the active teleprompter document with stable sections and explicit origin metadata.
3. Local user speech advances the active document with confidence-based movement.
4. Pauses/restarts do not cause runaway advancement, and going off script causes the follower to wait rather than chase.
5. Skipping ahead or rejoining earlier/later content can recover.
6. Manual navigation immediately overrides automatic following.
7. A new generated response arriving while the user is still answering remains pending and does not replace the active document.
8. Supporting cues can update or render beside the script without corrupting alignment state.
9. `Remote` interviewer speech never advances teleprompter content.
10. Generated content is not persisted unless the user explicitly saves it.
