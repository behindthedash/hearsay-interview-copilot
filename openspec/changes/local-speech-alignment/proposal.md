## Why

The teleprompter should follow natural speech rather than forcing fixed-speed scrolling or verbatim delivery.

## What Changes

- Consume Hearsay Local transcript events only.
- Maintain rolling Local speech context.
- Score nearby prepared sections with hold/recovery confidence states.
- Support manual navigation anchors and global recovery only after sustained mismatch.

## Capabilities

### Modified Capabilities
- `local-speech-alignment`
