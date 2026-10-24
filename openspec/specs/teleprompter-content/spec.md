# teleprompter-content Specification

## Purpose

Defines prepared speech material as ordered stable sections suitable for speech-following presentation.

## Requirements

### Requirement: Prepared content is normalized into ordered sections
The system SHALL load supported text/Markdown into ordered sections with stable identity, display text, normalized match text, and source provenance.
Each section SHALL have stable identity, source provenance, display text, normalized match text, and ordinal position.

#### Scenario: Markdown content reloads unchanged
- **WHEN** the same source is reloaded without content changes
- **THEN** section identities and ordering remain stable

### Requirement: Unchanged sections keep stable identity
Reloading an unchanged document SHALL preserve section identifiers.

#### Scenario: Unchanged document is reloaded
- **WHEN** a document is reloaded without content changes
- **THEN** its section identifiers remain unchanged

### Requirement: Invalid or empty content fails clearly
A selected file with no usable text SHALL produce a clear error and SHALL NOT start speech-following mode.

#### Scenario: Selected file contains no usable text
- **WHEN** the selected file contains no usable text
- **THEN** the system produces a clear error
- **AND** speech-following mode does not start
