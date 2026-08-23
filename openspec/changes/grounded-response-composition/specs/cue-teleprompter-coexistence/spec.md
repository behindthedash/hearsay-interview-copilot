## MODIFIED Requirements

### Requirement: Cue and teleprompter state remain independent
Cue state and teleprompter alignment state SHALL retain separate identities and lifecycles. Cue arrival by itself SHALL NOT move teleprompter alignment, and local alignment movement SHALL NOT recompute cue content. A grounded response coordinator MAY intentionally stage a generated teleprompter document and supporting cues from the same response package, but each projection SHALL retain its own state identity.

#### Scenario: Generated response carries supporting cues
- **WHEN** one response package contains a generated script and bounded supporting cues
- **THEN** the presentation coordinator MAY render both while teleprompter advancement affects only alignment state and cue refresh affects only cue state

### Requirement: Combined presentation avoids focus theft and overlap
When script and cue projections are visible together, their configured layout SHALL avoid unintended overlap and neither response arrival nor either update path SHALL intentionally steal foreground focus.

### Requirement: Either aid can run alone
Cue-only and teleprompter-only operation SHALL remain supported without requiring state from the disabled aid. A generated script SHALL remain usable without rendering supporting cues, and cue-only fallback SHALL remain usable without activating teleprompter content.

#### Scenario: Response policy selects cue-only
- **WHEN** evidence supports useful guidance but not a trustworthy generated script
- **THEN** the cue projection SHALL remain usable without creating or activating generated teleprompter content
