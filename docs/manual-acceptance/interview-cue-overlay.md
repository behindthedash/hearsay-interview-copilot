# Interview Cue Overlay — Windows Manual Acceptance

Run this checklist on Windows with the Interview Copilot overlay positioned near the webcam and a live Zoom or Teams meeting window in the foreground.

## Focus safety

- [ ] Put keyboard focus in the Zoom/Teams chat or another meeting text field.
- [ ] Publish a `retrieving` overlay state from a background worker.
- [ ] Publish a `ready` cue while continuing to type in the meeting application.
- [ ] Confirm the overlay updates without taking keyboard focus or activating itself.
- [ ] Publish `no_match` and `unavailable` states and confirm focus remains in the meeting application.

## Visibility and controls

- [ ] Confirm the overlay remains topmost while Zoom/Teams is active.
- [ ] Confirm Clear removes the current cue without stopping the host session.
- [ ] Confirm Hide withdraws the overlay and it can be shown again without losing session state.
- [ ] Confirm A-/A+ adjust text size and persist after restarting the application.
- [ ] Confirm Fade-/Fade+ adjust opacity within the supported bounds and persist after restart.
- [ ] Move and resize the overlay, restart the application, and confirm geometry is restored.

## Multi-monitor recovery

- [ ] Place the overlay on a secondary monitor and close the application.
- [ ] Disconnect that monitor before restarting.
- [ ] Confirm the overlay recovers into a visible work area on a connected display.
- [ ] Repeat with a monitor positioned to the left of the primary display so persisted geometry contains a negative X coordinate.

## Truth/status presentation

- [ ] Render evidence with `implemented`, `prototype`, `design`, and `hypothetical` status.
- [ ] Confirm each item visibly includes its status and that design/hypothetical material is not presented as implemented experience.
- [ ] Confirm the overlay shows concise cue text rather than full source documents or a long generated script.

## Stale update protection

- [ ] Start retrieval for generation N and then generation N+1 before N completes.
- [ ] Deliver generation N after N+1 is already retrieving or ready.
- [ ] Confirm generation N does not replace the newer display.
- [ ] Clear a retrieving generation and confirm a late result from that same generation does not reappear.
