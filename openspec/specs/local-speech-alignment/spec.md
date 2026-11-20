## Purpose

Tracks the user's position in prepared material from finalized Hearsay `Local` speech without requiring verbatim delivery.

## Requirements

### Requirement: Only Local speech drives alignment
`Remote` transcript events SHALL NOT advance or reposition teleprompter alignment state.

#### Scenario: Remote transcript arrives
- **WHEN** a `Remote` transcript event arrives
- **THEN** the current alignment position stays the same

### Requirement: Alignment is confidence-based
The aligner SHALL prefer current/nearby sections, hold on weak evidence, and use broader recovery only after repeated low-confidence evidence or explicit manual repositioning. Strong nearby semantic/fuzzy evidence MAY advance to the best supported section.

#### Scenario: Natural paraphrase matches next section
- **WHEN** rolling Local speech strongly supports the next section without verbatim wording
- **THEN** alignment may advance with an aligned confidence state

### Requirement: Repetition does not cause runaway advancement
Repeating/restarting material from the current section SHALL not by itself skip ahead.

#### Scenario: User restarts the current section
- **WHEN** the user restarts material from the current section
- **THEN** the repetition alone does not advance alignment

### Requirement: Skipped content can recover
Sustained strong evidence for a later section SHALL allow recovery to that section and mark the move as recovery.

#### Scenario: Speech supports a later section during broader recovery
- **WHEN** broader recovery is allowed and Local speech sustains strong evidence for a later section
- **THEN** alignment can move to that section and marks the move as recovery

### Requirement: Manual control always anchors subsequent alignment
The aligner SHALL use the manually selected section as the anchor for subsequent automatic alignment.

#### Scenario: User jumps manually
- **WHEN** the user selects a section
- **THEN** that section becomes the new local alignment anchor and automatic following does not immediately snap back to the prior position
