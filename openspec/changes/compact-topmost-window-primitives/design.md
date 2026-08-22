## Decisions

### D1. Composition over deep UI inheritance
Prefer a small helper/controller used by separate window classes.

### D2. Parent window owns content
The primitive handles geometry/topmost/opacity/show-update mechanics only.

### D3. No focus forcing
Background update paths never call `focus_force()` or equivalent.

### D4. Recover offscreen geometry
Saved geometry is validated against current monitor work areas before use.
