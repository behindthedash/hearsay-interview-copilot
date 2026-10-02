## MODIFIED Requirements

### Requirement: Alignment is confidence-based
Strong nearby semantic/fuzzy evidence MAY advance to the best supported section; weak evidence SHALL hold the current position. The aligner SHALL prefer current/nearby sections, hold on weak evidence, and use broader recovery only after repeated low-confidence evidence or explicit manual repositioning.

#### Scenario: Natural paraphrase matches next section
- **WHEN** rolling Local speech strongly supports the next section without verbatim wording
- **THEN** alignment may advance with an aligned confidence state

### Requirement: Manual control always anchors subsequent alignment
A manually selected section SHALL become the new local alignment anchor; automatic following SHALL NOT immediately snap back to the prior position.

#### Scenario: User jumps manually
- **WHEN** the user selects a section
- **THEN** that section becomes the new local alignment anchor and automatic following does not immediately snap back to the prior position
