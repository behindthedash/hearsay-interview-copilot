# compact-topmost-window-primitives Specification

## Purpose

Provides reusable presentation mechanics for compact topmost Interview Copilot windows without embedding cue or teleprompter domain behavior.

## Requirements

### Requirement: Topmost presentation is reusable
The shared primitive SHALL own topmost, opacity, geometry persistence, and visible-screen recovery while leaving domain rendering and state to consumers. Cue and teleprompter views SHALL share the primitive's presentation and safe-update mechanics.

#### Scenario: Cue and teleprompter create windows
- **WHEN** both use the primitive
- **THEN** they receive consistent presentation mechanics without sharing domain state

### Requirement: Content updates do not force focus
Background updates SHALL NOT intentionally activate the projection or steal focus from the foreground meeting application.

#### Scenario: Content changes during a meeting
- **WHEN** a background content update arrives while the meeting application has focus
- **THEN** applying the update leaves focus with the meeting application

### Requirement: Invalid persisted geometry fails safely
When saved placement is no longer visible on current displays, the window SHALL recover to a visible work area.

#### Scenario: Saved placement is off-screen
- **WHEN** the window restores a saved placement that is no longer visible on any current display
- **THEN** the window moves to a visible work area
