# TalkPrompter alignment reference evaluation

## Scope

The Interview Copilot speech-following behavior was informed by the public MIT-licensed TalkPrompter project (`Sven-Bo/talkprompter`), particularly its matching concepts in `src/Teleprompter.Core/Matching`.

Reference reviewed:

- `ScriptMatcher.cs`
- `MatcherOptions.cs`
- `Levenshtein.cs`
- `TrackingState.cs`
- `MatchUpdate.cs`
- upstream MIT license, copyright 2026 Sven Bosau (Bosau Digital LLC)

## Behavioral ideas retained

The Python implementation intentionally preserves several interaction ideas that are useful for a speech-following teleprompter:

1. Use a bounded recent-speech window rather than elapsed time or assumed reading speed.
2. Prefer the current and nearby script position before considering broader re-acquisition.
3. Hold position when recognition is weak or the speaker goes off script.
4. Require stronger, sustained evidence before a larger skip-ahead recovery.
5. Permit confident backward recovery when the speaker restarts earlier material.
6. Treat manual navigation as a new alignment anchor.
7. Keep matching deterministic and independent of microphone/audio implementation so behavior is testable from synthetic speech signals.

## Implementation decision: independent Python implementation

No TalkPrompter source code is copied, translated, or mechanically ported into this repository. The Interview Copilot implementation is native Python and operates at the repository's `TeleprompterDocument` section boundary rather than TalkPrompter's token-anchor model.

The implementation also differs materially in these areas:

- consumes only the consumer-owned `LocalSpeechSignal` contract;
- has no generic source field, making Remote interviewer speech structurally ineligible;
- aligns stable teleprompter sections rather than display-token positions;
- applies the same engine to prepared and generated documents;
- combines deterministic sequence similarity with token overlap rather than porting TalkPrompter's Levenshtein implementation;
- uses explicit repeated recovery confirmation for larger forward/backward moves;
- clears rolling evidence after manual anchors so automatic matching cannot immediately snap back to the old position.

Because no upstream source or substantial portion is reused, there is no copied third-party source file requiring an embedded TalkPrompter copyright header. If future work directly copies or ports TalkPrompter source, the upstream MIT copyright and permission notice must be preserved with that reused source in accordance with the MIT license.

## Upstream license

TalkPrompter is licensed under the MIT License. The reviewed upstream license states copyright 2026 Sven Bosau (Bosau Digital LLC). This document records the dependency evaluation so later contributors can distinguish behavioral inspiration from source-code reuse.
