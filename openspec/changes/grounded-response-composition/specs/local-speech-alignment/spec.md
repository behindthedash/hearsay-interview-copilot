## MODIFIED Requirements

### Requirement: Only Local speech drives alignment
Only speech identified as the user's Local speech SHALL advance or reposition teleprompter alignment state. `Remote` interviewer speech SHALL NOT advance or reposition teleprompter alignment state. The alignment implementation SHALL consume a Local speech signal through a consumer-owned provider boundary so that Hearsay `Local` events or an alternate low-latency Local recognizer can satisfy the same contract.

#### Scenario: Remote speech arrives while a script is active
- **WHEN** a `Remote` transcript event arrives
- **THEN** teleprompter alignment SHALL remain unchanged

#### Scenario: Alternate Local recognizer is configured
- **WHEN** a consumer-owned low-latency Local speech provider emits eligible Local speech
- **THEN** the alignment engine MAY use that signal without coupling to Hearsay private audio, recorder, UI, or Whisper internals

### Requirement: Alignment is confidence-based
Strong nearby semantic/fuzzy evidence MAY advance to the best supported section of the active teleprompter document; weak evidence SHALL hold the current position. The rule SHALL apply equally to prepared and generated teleprompter documents.

### Requirement: Repetition does not cause runaway advancement
Repeating/restarting material from the current section of the active teleprompter document SHALL not by itself skip ahead.

### Requirement: Skipped content can recover
Sustained strong evidence for a later section of the active teleprompter document SHALL allow recovery to that section and mark the move as recovery.
