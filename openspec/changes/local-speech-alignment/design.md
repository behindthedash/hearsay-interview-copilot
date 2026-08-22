## Decisions

### D1. Rolling Local transcript window
Only finalized Local events enter the alignment context; Remote events are ignored for advancement.

### D2. Nearby-first search
Score current, previous, and next few sections before considering global recovery.

### D3. Lexical fuzzy baseline
Lexical fuzzy matching is mandatory and deterministic; optional semantic scoring can augment it later.

### D4. Explicit states
Emit alignment state including active section, confidence, and transition reason such as aligned/held/recovered/manual.
