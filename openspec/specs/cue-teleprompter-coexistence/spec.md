## Purpose

Coordinates dynamic interview cues and prepared teleprompter guidance without merging their state or responsibilities.

## Requirements

### Requirement: Cue and teleprompter state remain independent
A new interview cue SHALL NOT change the teleprompter's active prepared section, and local alignment movement SHALL NOT replace or recompute the current interview cue.

### Requirement: Combined presentation avoids focus theft and overlap
When both views are visible, their configured layout SHALL avoid unintended overlap and neither update path SHALL intentionally steal foreground focus.

### Requirement: Either aid can run alone
Cue-only and teleprompter-only operation SHALL remain supported without requiring state from the disabled aid.
