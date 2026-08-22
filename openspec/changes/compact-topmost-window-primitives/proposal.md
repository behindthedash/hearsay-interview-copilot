## Why

Cue and teleprompter windows need the same focus-safe topmost/geometry/opacity behavior without duplicating Windows-specific presentation logic.

## What Changes

- Add a thin reusable topmost-window helper for consumer UIs.
- Centralize geometry persistence/offscreen recovery and opacity bounds.
- Guarantee background content updates do not intentionally force focus.

## Capabilities

### Modified Capabilities
- `compact-topmost-window-primitives`
