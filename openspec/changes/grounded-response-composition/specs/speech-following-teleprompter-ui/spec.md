## MODIFIED Requirements

### Requirement: Active prepared content is glanceable
When an active prepared or generated teleprompter document selects a new section, the teleprompter SHALL place and visually distinguish it in the configured reading position. Generated origin MAY be indicated subtly without displacing the speech-ready text.

#### Scenario: Generated response is activated
- **WHEN** a pending `generated-script` response becomes the active teleprompter document
- **THEN** its first active section SHALL appear in the configured reading position and speech-following SHALL begin from that document

### Requirement: Updates do not intentionally steal focus
Alignment-driven refreshes, generated-response arrival, cue updates, and pending-response indicators SHALL NOT intentionally activate the teleprompter or steal focus from the meeting application.

### Requirement: Manual control always overrides following
Pause, next, previous, jump, activate-pending-response, and dismiss-pending-response actions SHALL take effect immediately. Automatic following or safe auto-activation SHALL NOT override an explicit manual pause or dismissal.

### Requirement: Presentation preferences persist
Supported size, opacity, font, and geometry preferences SHALL persist without storing an additional copy of prepared or generated script content.

## ADDED Requirements

### Requirement: Pending generated responses are visible without replacing active speech
When a generated response is staged while another answer is active, the UI SHALL provide a compact pending indicator and an explicit activation path while preserving the current script and alignment position.
