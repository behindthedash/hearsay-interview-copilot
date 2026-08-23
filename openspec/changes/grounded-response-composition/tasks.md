# Implementation Tasks — Grounded Response Composition

These tasks implement the merged grounded-response/teleprompter design in dependency order. Each section maps to a canonical or delta capability so implementation PRs can be taken one coherent slice at a time.

## 0. Delivery rules and dependency order

- [x] 0.1 Keep all runtime changes in `hearsay-interview-copilot`; do not add interview semantics, scripts, retrieval, response generation, or teleprompter state to Hearsay.
- [x] 0.2 Preserve the supported Hearsay transcript/session API as the integration boundary; do not consume Hearsay private queues, recorder state, UI widgets, or Whisper internals.
- [x] 0.3 Keep generated-response data session-scoped by default and ensure tests use synthetic knowledge/interview material only.
- [x] 0.4 Implement in this order unless a task explicitly states otherwise: response domain -> response policy/composition -> cue integration -> teleprompter content -> Local speech provider/alignment -> teleprompter UI -> presentation coordination -> end-to-end orchestration.
- [x] 0.5 For every implementation PR, require Ruff lint, Ruff format-check, and pytest to pass on Python 3.11 and 3.14 through the existing CI workflow.

## 1. `grounded-response-composition` — response domain

- [x] 1.1 Add a `ResponseMode` model/enumeration containing exactly `generated-script`, `cue-only`, `clarification`, and `unavailable`.
- [x] 1.2 Add an immutable response-package model carrying response mode, interviewer query generation, evidence/provenance references, truth/experience status, confidence/eligibility metadata, optional script content, and optional bounded cues.
- [x] 1.3 Define explicit response-package validation so impossible states are rejected, including generated-script without script text, cue-only without usable cue content, and generated content without a query generation.
- [x] 1.4 Add lifecycle state for `pending`, `active`, `dismissed`, and `superseded` response packages without conflating that lifecycle with teleprompter alignment state.
- [x] 1.5 Add unit tests covering valid and invalid package combinations, serialization/equality behavior where applicable, and preservation of provenance/truth-status metadata.

## 2. `grounded-response-composition` — response-mode policy

- [x] 2.1 Introduce a response coordinator that accepts one eligible interviewer query generation plus its bounded retrieval result and produces exactly one response mode.
- [x] 2.2 Define deterministic eligibility inputs for scripted generation, including retrieval relevance/quality, conflict/ambiguity state, knowledge truth status, and whether generated-script mode is enabled.
- [x] 2.3 Select `generated-script` only when evidence is sufficiently strong and internally consistent for a speech-ready answer.
- [x] 2.4 Select `cue-only` when evidence supports useful talking points but is not sufficient for a trustworthy complete script.
- [x] 2.5 Select `clarification` when the interviewer question or retrieved evidence is ambiguous enough that asking/reflecting a clarification is safer than answering directly.
- [x] 2.6 Select `unavailable` when no trustworthy supporting evidence is available or retrieval fails in a way that prevents useful guidance.
- [x] 2.7 Bind every coordinator result to the originating query generation and reject activation of results superseded by a newer generation.
- [x] 2.8 Add table-driven tests for all four response modes, including weak evidence, conflicting evidence, hypothetical-only evidence, no-match, provider failure, and scripted-generation-disabled cases.

## 3. `grounded-response-composition` — grounded script composer

- [x] 3.1 Define a composer interface that receives only the selected interviewer question/intent plus eligible retrieved evidence and returns speech-ready text with claim-to-evidence traceability.
- [x] 3.2 Ensure the composer cannot access unrelated knowledge outside the selected evidence package unless a later spec explicitly widens the retrieval contract.
- [x] 3.3 Preserve `implemented`, `prototype`, `design`, and `hypothetical` status in generated wording so planned or hypothetical work is never phrased as completed production experience.
- [x] 3.4 Prevent unsupported projects, responsibilities, technologies, metrics, outcomes, employers/customers, or implementation claims from appearing in generated scripts.
- [x] 3.5 Produce concise conversational spoken text rather than essay-style prose; push secondary facts into supporting cues instead of bloating the script.
- [x] 3.6 Retain the evidence/provenance references needed to explain where every material response claim originated.
- [x] 3.7 Add adversarial grounding tests where the requested answer would be stronger or more impressive if invented, and verify the composer either preserves the weaker truth or falls back from generated-script.
- [x] 3.8 Add tests for mixed-status evidence so a response can distinguish actual experience from architecture the user would propose for a new situation.

## 4. `interview-cues` — response-package integration

- [ ] 4.1 Refactor cue composition so retrieval/evidence state can feed the response coordinator without losing existing cue provenance/status metadata.
- [ ] 4.2 Keep cue projection bounded and glanceable even when the same response package contains a full generated script.
- [ ] 4.3 Ensure generated-script mode shows only supporting points in the cue projection and does not duplicate the teleprompter script.
- [ ] 4.4 Ensure cue-only mode remains fully usable without creating or activating generated teleprompter content.
- [ ] 4.5 Map no-match/provider-failure evidence states into clarification/unavailable behavior without terminating the Hearsay host session.
- [ ] 4.6 Preserve existing stale-generation protection so an older cue/retrieval result cannot replace newer response guidance.
- [ ] 4.7 Add tests for generated-script + supporting-cues, cue-only, clarification, unavailable, retrieval failure, and stale-result scenarios.

## 5. `teleprompter-content` — prepared and generated documents

- [ ] 5.1 Extend the teleprompter document model with explicit `prepared` and `generated` origin metadata.
- [ ] 5.2 For generated documents, retain the originating interviewer query generation and transient provenance/evidence references.
- [ ] 5.3 Add a conversion path from a generated response package into the same ordered-section model used by prepared content.
- [ ] 5.4 Ensure normalization produces stable section identity for the lifetime of the generated document so presentation refreshes do not reset alignment.
- [ ] 5.5 Keep prepared-content loaders and persistence behavior backward-compatible.
- [ ] 5.6 Keep generated documents out of prepared-content stores/source files unless the user explicitly invokes a save action.
- [ ] 5.7 Clear generated teleprompter documents and transient provenance on session teardown unless explicitly saved.
- [ ] 5.8 Add tests for prepared/generated origin, response-to-document conversion, stable identities across refreshes, default ephemerality, explicit save behavior, and teardown cleanup.

## 6. `local-speech-alignment` — Local speech provider boundary

- [ ] 6.1 Define a consumer-owned Local speech signal provider interface containing only the information alignment needs, independent of Hearsay private implementation details.
- [ ] 6.2 Implement a Hearsay-backed provider adapter that converts supported finalized `Local` transcript events into the alignment signal contract.
- [ ] 6.3 Keep `Remote` interviewer events structurally ineligible for teleprompter alignment.
- [ ] 6.4 Define provider lifecycle/teardown semantics so stale Local events cannot leak across interview sessions.
- [ ] 6.5 Define provider health/latency diagnostics sufficient to compare finalized Hearsay events with an alternate lower-latency recognizer later.
- [ ] 6.6 Add a test/fake provider so alignment behavior can be validated without real microphone hardware or Hearsay internals.
- [ ] 6.7 Add contract tests proving both the Hearsay adapter and fake/alternate provider satisfy identical alignment inputs and Local-only guarantees.

## 7. `local-speech-alignment` — TalkPrompter-style following behavior

- [ ] 7.1 Evaluate TalkPrompter's MIT-licensed matching/recovery implementation and document which behavioral ideas or code, if any, are reused versus independently implemented.
- [ ] 7.2 Preserve all required copyright/license notices for any reused TalkPrompter source while keeping the Interview Copilot implementation native to this repository's Python architecture.
- [ ] 7.3 Generalize the alignment engine from prepared-only material to the currently active teleprompter document regardless of origin.
- [ ] 7.4 Implement confidence-based nearby matching that advances only when Local speech sufficiently supports movement.
- [ ] 7.5 Hold position during pauses or weak/noisy Local recognition rather than advancing on time or assumed reading speed.
- [ ] 7.6 Tolerate paraphrase and minor wording differences without requiring verbatim delivery.
- [ ] 7.7 Prevent repetition/restarts from causing runaway forward advancement.
- [ ] 7.8 Support recovery when the user intentionally skips ahead and sustained evidence clearly matches a later section.
- [ ] 7.9 Support rejoining after the user goes off script, including backward/restart behavior where confidence warrants it.
- [ ] 7.10 Ensure manual pause/navigation overrides automatic matching immediately.
- [ ] 7.11 Add deterministic synthetic tests for pause, paraphrase, restart, repetition, skip-ahead recovery, off-script waiting/rejoin, backward movement, weak confidence, and Remote speech contamination.
- [ ] 7.12 Run the same alignment test suite against prepared and generated documents.

## 8. `grounded-response-composition` — active/pending response lifecycle

- [ ] 8.1 Track whether the user is actively answering using Local speech/alignment/session state without inferring interview semantics inside Hearsay.
- [ ] 8.2 When a new generated response completes while another answer is active, stage it as pending instead of replacing the active teleprompter document.
- [ ] 8.3 Preserve the current active document identity, section position, and alignment state while a pending response exists.
- [ ] 8.4 Allow explicit activation of the pending response and initialize its alignment at the correct first section.
- [ ] 8.5 Allow explicit dismissal of the pending response without altering the active document.
- [ ] 8.6 Prevent safe auto-activation from overriding an explicit user pause or dismissal.
- [ ] 8.7 Supersede stale pending responses when a newer interviewer query generation produces newer guidance, subject to in-progress-answer protection.
- [ ] 8.8 Add state-machine tests for active -> pending -> activate, active -> pending -> dismiss, stale pending supersession, and teardown.

## 9. `speech-following-teleprompter-ui` — generated response presentation

- [ ] 9.1 Render both prepared and generated teleprompter documents through the same reading surface and alignment projection.
- [ ] 9.2 Place the current active section in the configured reading position and visually distinguish it without excessive UI movement.
- [ ] 9.3 Add a subtle generated-origin indicator that does not compete with the speech-ready text.
- [ ] 9.4 Add a compact pending-response indicator that does not replace the active script or steal application focus.
- [ ] 9.5 Add explicit activate-pending and dismiss-pending controls.
- [ ] 9.6 Preserve existing manual pause, next, previous, and jump controls and make them authoritative over automatic following.
- [ ] 9.7 Ensure alignment refreshes, generated-response arrival, cue updates, and pending indicators never intentionally steal foreground focus from the meeting application.
- [ ] 9.8 Persist size, opacity, font, and geometry preferences without persisting an extra copy of generated or prepared script content.
- [ ] 9.9 Add UI/state tests for generated activation, pending indication, manual override, no-focus-steal behavior where testable, and preference persistence.

## 10. `cue-teleprompter-coexistence` — coordinated presentation

- [ ] 10.1 Keep cue projection identity/lifecycle separate from teleprompter document/alignment identity even when both originate from one response package.
- [ ] 10.2 Introduce or extend the thin presentation coordinator so a generated-script package can intentionally stage both teleprompter content and bounded supporting cues.
- [ ] 10.3 Ensure teleprompter advancement changes only alignment state and cue refresh changes only cue state.
- [ ] 10.4 Ensure configured cue and teleprompter layouts avoid unintended overlap and neither path forces foreground focus.
- [ ] 10.5 Preserve teleprompter-only operation when cue rendering is disabled.
- [ ] 10.6 Preserve cue-only operation when response policy does not permit a generated script.
- [ ] 10.7 Add integration tests for simultaneous cue/alignment updates, generated-script without cues, cue-only without teleprompter activation, and independent teardown.

## 11. Live interview session orchestration

- [ ] 11.1 Wire eligible `Remote` interviewer turns through retrieval -> evidence evaluation -> response-mode selection -> cue/script composition.
- [ ] 11.2 Route generated-script response packages into pending/active teleprompter lifecycle while routing supporting cues independently to cue presentation.
- [ ] 11.3 Route `Local` speech only into answer-state/alignment behavior and never into interviewer-question retrieval.
- [ ] 11.4 Preserve query-generation cancellation so superseded retrieval/composition work cannot become active guidance.
- [ ] 11.5 Ensure failure in retrieval, generation, Local speech provider, cue presentation, or teleprompter presentation degrades locally and does not terminate Hearsay transcription.
- [ ] 11.6 Ensure session teardown unregisters Hearsay handlers/providers and clears pending/active generated response state, transient evidence, cue state, and alignment state.
- [ ] 11.7 Add end-to-end synthetic tests for prepared-answer flow, grounded generated-answer flow, cue-only fallback, clarification, unavailable/no-match, new question while answering, stale-generation cancellation, and clean teardown.

## 12. Acceptance and release verification

- [ ] 12.1 Demonstrate a prepared script that follows Local speech, pauses when the user pauses, waits when the user goes off script, and recovers when the user rejoins.
- [ ] 12.2 Demonstrate an interviewer `Remote` question producing strong evidence, a grounded generated response, bounded supporting cues, and a generated teleprompter document.
- [ ] 12.3 Demonstrate that weak/conflicting evidence cannot produce a polished unsupported answer and instead resolves to cue-only, clarification, or unavailable.
- [ ] 12.4 Demonstrate that a second interviewer question arriving while the user is answering becomes pending and does not replace the active teleprompter position.
- [ ] 12.5 Demonstrate that Remote speech never advances the teleprompter.
- [ ] 12.6 Demonstrate that generated scripts disappear on teardown unless explicitly saved.
- [ ] 12.7 Verify provenance/truth status can be traced from generated response claims back to the selected knowledge evidence.
- [ ] 12.8 Run the full project quality gate: `ruff check`, `ruff format --check`, and `pytest` through CI on Python 3.11 and 3.14.
