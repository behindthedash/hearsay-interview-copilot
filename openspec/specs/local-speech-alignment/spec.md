## Purpose

Tracks the user's position in prepared material from finalized Hearsay `Local` speech without requiring verbatim delivery.

## Requirements

### Requirement: Only Local speech drives alignment
`Remote` transcript events SHALL NOT advance or reposition teleprompter alignment state.

### Requirement: Alignment is confidence-based
Strong nearby semantic/fuzzy evidence MAY advance to the best supported section; weak evidence SHALL hold the current position. The aligner SHALL prefer current/nearby sections and use broader recovery only after repeated low-confidence evidence or explicit manual repositioning.

#### Scenario: Natural paraphrase matches next section
- **WHEN** rolling Local speech strongly supports the next section without verbatim wording
- **THEN** alignment may advance with an aligned confidence state

### Requirement: Repetition does not cause runaway advancement
Repeating/restarting material from the current section SHALL not by itself skip ahead.

### Requirement: Skipped content can recover
Sustained strong evidence for a later section SHALL allow recovery to that section and mark the move as recovery.

### Requirement: Manual control always anchors subsequent alignment
Manual section selection SHALL become the new local alignment anchor, and automatic following SHALL NOT immediately snap back to the prior position.

#### Scenario: User jumps manually
- **WHEN** the user selects a section
- **THEN** that section becomes the new local alignment anchor and automatic following does not immediately snap back to the prior position
