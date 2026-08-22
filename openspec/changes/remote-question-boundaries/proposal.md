## Why

Searching on every transcript fragment would create noisy, expensive, and unstable cues. The consumer needs deterministic interviewer-turn assembly over Remote events.

## What Changes

- Subscribe to Hearsay Remote transcript events only for automatic query generation.
- Buffer adjacent segments into coherent utterances.
- Emit on punctuation/debounce, pause, maximum age/size, or manual flush.
- Suppress overlap duplicates and assign monotonic query generations.

## Capabilities

### Modified Capabilities
- `remote-query-boundaries`
