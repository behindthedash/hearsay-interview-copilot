## MODIFIED Requirements

### Requirement: Prepared content is normalized into ordered sections
Each section SHALL have stable identity, source provenance, display text, normalized match text, and ordinal position.

#### Scenario: Markdown content reloads unchanged
- **WHEN** the same source is reloaded without content changes
- **THEN** section identities and ordering remain stable
