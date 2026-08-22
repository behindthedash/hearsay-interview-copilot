## MODIFIED Requirements

### Requirement: Interview cues are shown in a compact always-on-top view
The overlay SHALL render structured cue fields rather than markdown/chat prose and SHALL preserve visible experience-status distinctions.

#### Scenario: Current cue is ready
- **WHEN** a non-stale cue arrives
- **THEN** the overlay presents its primary story, bounded supporting points, and concise provenance/status at a glance

### Requirement: Background cue updates do not steal meeting focus
#### Scenario: Meeting application is foreground
- **WHEN** cue state changes
- **THEN** the overlay updates without intentionally activating itself
