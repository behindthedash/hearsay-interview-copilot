## Purpose

Presents current interview guidance in a glanceable near-camera window without pulling focus away from the meeting application.

## Requirements

### Requirement: Cues appear in a compact always-on-top view
When enabled, the overlay SHALL render the current structured cue without reproducing full source documents or a long scripted answer.

### Requirement: Background cue updates do not steal focus
Refreshing cue content SHALL NOT intentionally activate the overlay or move keyboard focus from the foreground meeting application.

### Requirement: Placement and readability are user-controlled
The user SHALL be able to move/resize the overlay and adjust supported font/opacity presentation settings; usable settings SHALL persist across restarts and recover from disconnected displays.

### Requirement: Claim status remains visible
Implemented/prototype/design evidence and hypothetical/application ideas SHALL remain visually distinguishable.

### Requirement: Overlay state communicates availability
The overlay SHALL concisely represent idle/listening, retrieving, ready, no-match, and unavailable states.

### Requirement: Overlay visibility is directly controllable
The user SHALL be able to show, hide, and clear the cue overlay without stopping the Hearsay host session.
