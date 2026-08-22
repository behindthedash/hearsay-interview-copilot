## Purpose

Defines prepared speech material as ordered stable sections suitable for speech-following presentation.

## Requirements

### Requirement: Prepared content is normalized into ordered sections
The system SHALL load supported text/Markdown into ordered sections with stable identity, display text, normalized match text, and source provenance.

### Requirement: Unchanged sections keep stable identity
Reloading an unchanged document SHALL preserve section identifiers.

### Requirement: Invalid or empty content fails clearly
A selected file with no usable text SHALL produce a clear error and SHALL NOT start speech-following mode.
