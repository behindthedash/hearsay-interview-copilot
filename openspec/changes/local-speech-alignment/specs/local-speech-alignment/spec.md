## MODIFIED Requirements

### Requirement: Alignment is confidence based
The aligner SHALL prefer current/nearby sections, hold on weak evidence, and use broader recovery only after repeated low-confidence evidence or explicit manual repositioning.

#### Scenario: Natural paraphrase matches next section
- **WHEN** rolling Local speech strongly supports the next section without verbatim wording
- **THEN** alignment may advance with an aligned confidence state

### Requirement: Manual control always anchors subsequent alignment
#### Scenario: User jumps manually
- **WHEN** the user selects a section
- **THEN** that section becomes the new local alignment anchor and automatic following does not immediately snap back to the prior position
