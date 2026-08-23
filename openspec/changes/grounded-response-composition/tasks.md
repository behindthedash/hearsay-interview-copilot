## 1. Response domain

- [ ] 1.1 Add response-package and response-mode models with query generation, evidence/provenance, truth status, optional script content, optional cues, and confidence.
- [ ] 1.2 Add response-coordinator policy for generated-script, cue-only, clarification, and unavailable outcomes.
- [ ] 1.3 Bind response composition to query generations so stale work cannot activate.

## 2. Grounded composition

- [ ] 2.1 Compose concise speech-ready answers only from eligible retrieved evidence.
- [ ] 2.2 Preserve implemented/prototype/design/hypothetical status through composition.
- [ ] 2.3 Add evidence-quality fallback behavior and tests that reject unsupported factual claims.

## 3. Teleprompter content and activation

- [ ] 3.1 Extend teleprompter content with prepared/generated origin metadata and transient provenance references.
- [ ] 3.2 Stage generated responses and prevent replacement of an answer already in progress.
- [ ] 3.3 Keep generated content ephemeral unless the user explicitly saves it.

## 4. Speech alignment

- [ ] 4.1 Generalize alignment from prepared-only content to the active teleprompter document.
- [ ] 4.2 Introduce a Local speech signal provider boundary; keep Remote speech ineligible for alignment.
- [ ] 4.3 Evaluate TalkPrompter matching/recovery behavior for a Python port or equivalent implementation and preserve required notices for reused code.

## 5. Presentation coordination

- [ ] 5.1 Render generated scripts in the speech-following teleprompter.
- [ ] 5.2 Render optional supporting cues alongside the active response without coupling cue state to alignment state.
- [ ] 5.3 Expose pending-response state and explicit activation controls without stealing focus.

## 6. Verification

- [ ] 6.1 Test prepared, generated-script, cue-only, clarification, and unavailable flows.
- [ ] 6.2 Test stale-generation cancellation and in-progress-answer protection.
- [ ] 6.3 Test that generated scripts remain evidence-grounded and preserve provenance/truth status.
- [ ] 6.4 Test Local-only alignment with both Hearsay-event and alternate low-latency provider implementations.
