## Purpose

Provides reusable presentation mechanics for compact topmost Interview Copilot windows without embedding cue or teleprompter domain behavior.

## Requirements

### Requirement: Topmost presentation mechanics are reusable
Cue and teleprompter views SHALL share the same topmost, opacity, geometry, and safe-update mechanics rather than duplicating them.

### Requirement: Content updates do not force focus
Background updates SHALL NOT intentionally activate the projection or steal focus from the foreground meeting application.

### Requirement: Invalid persisted geometry fails safely
When saved placement is no longer visible on current displays, the window SHALL recover to a visible work area.
