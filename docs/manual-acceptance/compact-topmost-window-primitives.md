# Compact Topmost Window Primitives — Windows Acceptance

Run this checklist on Windows before treating focus/topmost behavior as release-ready. Automated tests cover geometry, opacity, persistence, recovery, and the absence of explicit focus/lift calls; the Windows window manager still requires manual verification with real meeting applications.

## Setup

- [ ] Launch a small test window that uses `CompactWindowController`.
- [ ] Open Zoom or Microsoft Teams and place keyboard focus in a text field or chat input.
- [ ] If possible, connect a second monitor and position the compact window there.

## Topmost and focus safety

- [ ] Show the compact window and confirm it remains above normal application windows.
- [ ] Return focus to Zoom/Teams.
- [ ] Trigger repeated `safe_update(...)` content refreshes and confirm Zoom/Teams retains keyboard focus.
- [ ] Change opacity while Zoom/Teams is focused and confirm focus is not stolen.
- [ ] Toggle topmost off/on and confirm no explicit focus transfer occurs.
- [ ] Hide and explicitly show the window; confirm showing does not call or behave like a forced `focus_force()`/`lift()` path.

## Geometry persistence and monitor recovery

- [ ] Move/resize the compact window, persist geometry, restart the test UI, and confirm placement is restored.
- [ ] Save geometry on a secondary monitor, close the test UI, disconnect that monitor, and relaunch.
- [ ] Confirm the restored window is moved fully into a visible current monitor work area rather than remaining offscreen.
- [ ] Reconnect the secondary monitor and verify negative desktop coordinates restore correctly when that monitor is left of the primary display.

## Opacity bounds

- [ ] Request an opacity below the configured minimum and confirm the window remains visible at the minimum bound.
- [ ] Request an opacity above 1.0 and confirm the effective value is capped at 1.0.

## Result

Record the Windows version, meeting application/version, monitor arrangement, and any focus/topmost anomalies in the implementing PR before merge.
