# local-speech-alignment Specification

## Purpose

Tracks the user's position in prepared material from finalized Hearsay `Local` speech without requiring verbatim delivery.

## Requirements

### Requirement: Only Local speech drives alignment
`Remote` transcript events SHALL NOT advance or reposition teleprompter alignment state.

#### Scenario: Remote speech leaves alignment unchanged
- **WHEN** a Remote transcript event is received
- **THEN** the teleprompter alignment position remains unchanged

### Requirement: Alignment is confidence-based
The aligner SHALL prefer current/nearby sections, hold on weak evidence, and use broader recovery only after repeated low-confidence evidence or explicit manual repositioning.

#### Scenario: Natural paraphrase matches next section
- **WHEN** rolling Local speech strongly supports the next section without verbatim wording
- **THEN** alignment may advance with an aligned confidence state

### Requirement: Repetition does not cause runaway advancement
Repeating/restarting material from the current section SHALL not by itself skip ahead.

#### Scenario: User repeats the current section
- **WHEN** the user repeats or restarts material from the current section
- **THEN** that repetition alone does not advance alignment to a later section

### Requirement: Skipped content can recover
Sustained strong evidence for a later section SHALL allow recovery to that section and mark the move as recovery.

#### Scenario: Sustained evidence supports a later section
- **WHEN** sustained strong evidence supports a later section
- **THEN** alignment can recover to that section and marks the move as recovery

### Requirement: Manual control always anchors subsequent alignment
Manual section selection SHALL establish the new local alignment anchor for subsequent automatic following.

#### Scenario: User jumps manually
- **WHEN** the user selects a section
- **THEN** that section becomes the new local alignment anchor and automatic following does not immediately snap back to the prior position
