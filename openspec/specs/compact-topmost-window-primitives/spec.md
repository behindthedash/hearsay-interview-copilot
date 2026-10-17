# compact-topmost-window-primitives Specification

## Purpose

Provides reusable presentation mechanics for compact topmost Interview Copilot windows without embedding cue or teleprompter domain behavior.

## Requirements

### Requirement: Topmost presentation is reusable
The shared primitive SHALL own topmost, opacity, geometry persistence, and visible-screen recovery while leaving domain rendering/state to consumers.

#### Scenario: Cue and teleprompter create windows
- **WHEN** both use the primitive
- **THEN** they receive consistent presentation mechanics without sharing domain state

### Requirement: Content updates do not force focus
Background updates SHALL NOT intentionally activate the projection or steal focus from the foreground meeting application.

#### Scenario: Content updates while the meeting application has focus
- **WHEN** a background update changes projection content while the meeting application is in the foreground
- **THEN** the update does not intentionally activate the projection or steal focus from the meeting application

### Requirement: Invalid persisted geometry fails safely
When saved placement is no longer visible on current displays, the window SHALL recover to a visible work area.

#### Scenario: Saved placement is outside current displays
- **WHEN** the window restores saved placement that is no longer visible on current displays
- **THEN** the window recovers to a visible work area
