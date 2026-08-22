## Decisions

### D1. Separate `TeleprompterWindow`
Do not reuse Hearsay's live transcript UI.

### D2. Section-based positioning first
Move discrete active sections into a stable reading zone; no per-word highlighting in MVP.

### D3. Use consumer topmost primitive
Topmost/geometry/opacity/focus-safe mechanics come from the shared consumer primitive.

### D4. Persist presentation only
Store geometry, width, font, opacity, and topmost preference; never persist the prepared script as UI settings.
