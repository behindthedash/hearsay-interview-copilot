## Decisions

### D1. Separate overlay window
Use a dedicated consumer window, not Hearsay's live transcript UI.

### D2. Structured rendering
Use explicit labels/frames for intent, story, bullets, role bridge, status, and retrieval state.

### D3. Presentation-only persistence
Persist geometry/font/opacity/topmost preferences; never persist current cue text as UI settings.

### D4. Thread-safe projection
Background workers publish cue state to the UI thread through the consumer's safe scheduling boundary.
