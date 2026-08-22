## Decisions

### D1. Coordinate presentation, not models
Cue and teleprompter have separate state stores/lifecycles; a thin presentation coordinator handles window coexistence only.

### D2. Independent windows first
Default to two independently movable windows. A stacked layout can be added later if user testing supports it.

### D3. Non-focus attention
New cue arrival may use an accent/badge/pulse but never focus forcing.
