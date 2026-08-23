from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from interview_copilot.ui import (
    CompactWindowConfig,
    CompactWindowController,
    WindowGeometry,
    WorkArea,
    clamp_opacity,
    is_geometry_visible,
    recover_geometry,
)


def test_geometry_round_trips_negative_monitor_offsets() -> None:
    geometry = WindowGeometry.parse("720x180-1440+36")

    assert geometry == WindowGeometry(width=720, height=180, x=-1440, y=36)
    assert geometry.to_tk() == "720x180-1440+36"


@pytest.mark.parametrize("value", ["", "720x180", "0x180+0+0", "720x0+0+0", "bogus"])
def test_invalid_geometry_is_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        WindowGeometry.parse(value)


def test_opacity_is_bounded_and_non_finite_values_are_rejected() -> None:
    assert clamp_opacity(0.05) == pytest.approx(0.20)
    assert clamp_opacity(0.75) == pytest.approx(0.75)
    assert clamp_opacity(2.0) == pytest.approx(1.0)

    with pytest.raises(ValueError):
        clamp_opacity(float("nan"))


def test_geometry_with_meaningful_visible_area_is_preserved() -> None:
    area = WorkArea(x=0, y=0, width=1920, height=1040)
    geometry = WindowGeometry(width=500, height=240, x=1850, y=100)

    assert is_geometry_visible(geometry, [area])
    assert recover_geometry(geometry, [area]) is geometry


def test_geometry_with_only_a_sliver_visible_is_recovered() -> None:
    area = WorkArea(x=0, y=0, width=1920, height=1040)
    geometry = WindowGeometry(width=500, height=240, x=1900, y=100)

    recovered = recover_geometry(geometry, [area])

    assert recovered == WindowGeometry(width=500, height=240, x=1420, y=100)
    assert is_geometry_visible(recovered, [area])


def test_offscreen_geometry_recovers_to_nearest_monitor_and_fits_work_area() -> None:
    left = WorkArea(x=-1920, y=0, width=1920, height=1040)
    primary = WorkArea(x=0, y=0, width=1920, height=1040)
    geometry = WindowGeometry(width=2500, height=1200, x=4000, y=2000)

    recovered = recover_geometry(geometry, [left, primary])

    assert recovered == WindowGeometry(width=1920, height=1040, x=0, y=0)
    assert is_geometry_visible(recovered, [left, primary])


@dataclass
class MemoryGeometryStore:
    values: dict[str, str] = field(default_factory=dict)

    def load_geometry(self, key: str) -> str | None:
        return self.values.get(key)

    def save_geometry(self, key: str, geometry: str) -> None:
        self.values[key] = geometry


class FakeWindow:
    def __init__(self) -> None:
        self.current_geometry = "640x200+40+40"
        self.attribute_calls: list[tuple[str, object]] = []
        self.geometry_calls: list[str] = []
        self.deiconify_calls = 0
        self.withdraw_calls = 0
        self.idle_calls = 0
        self.focus_force_calls = 0
        self.lift_calls = 0

    def attributes(self, option: str, value: object) -> object:
        self.attribute_calls.append((option, value))
        return None

    def geometry(self, value: str | None = None) -> str:
        if value is not None:
            self.current_geometry = value
            self.geometry_calls.append(value)
        return self.current_geometry

    def deiconify(self) -> None:
        self.deiconify_calls += 1

    def withdraw(self) -> None:
        self.withdraw_calls += 1

    def update_idletasks(self) -> None:
        self.idle_calls += 1

    def winfo_screenwidth(self) -> int:
        return 1920

    def winfo_screenheight(self) -> int:
        return 1080

    def focus_force(self) -> None:
        self.focus_force_calls += 1

    def lift(self) -> None:
        self.lift_calls += 1


def test_restore_invalid_saved_geometry_uses_visible_fallback() -> None:
    window = FakeWindow()
    store = MemoryGeometryStore({"cue": "not-valid"})
    controller = CompactWindowController(
        window,
        geometry_store=store,
        geometry_key="cue",
        work_area_provider=lambda: [WorkArea(0, 0, 1280, 720)],
    )

    restored = controller.restore_geometry(WindowGeometry(500, 200, 100, 100))

    assert restored == WindowGeometry(500, 200, 100, 100)
    assert window.current_geometry == "500x200+100+100"


def test_restore_offscreen_saved_geometry_recovers_before_showing() -> None:
    window = FakeWindow()
    store = MemoryGeometryStore({"teleprompter": "600x200+5000+5000"})
    controller = CompactWindowController(
        window,
        geometry_store=store,
        geometry_key="teleprompter",
        work_area_provider=lambda: [WorkArea(0, 0, 1920, 1040)],
    )

    restored = controller.restore_geometry(WindowGeometry(600, 200, 20, 20))

    assert restored == WindowGeometry(600, 200, 1320, 840)
    assert window.current_geometry == "600x200+1320+840"


def test_persist_geometry_reads_realized_window_geometry() -> None:
    window = FakeWindow()
    store = MemoryGeometryStore()
    controller = CompactWindowController(
        window,
        geometry_store=store,
        geometry_key="cue",
    )
    window.current_geometry = "700x220-700+80"

    captured = controller.persist_geometry()

    assert captured == WindowGeometry(700, 220, -700, 80)
    assert store.values["cue"] == "700x220-700+80"
    assert window.idle_calls == 1


def test_show_and_background_updates_never_force_focus_or_lift() -> None:
    window = FakeWindow()
    controller = CompactWindowController(window)
    updates: list[str] = []

    controller.show()
    controller.safe_update(lambda: updates.append("updated"))

    assert ("-topmost", True) in window.attribute_calls
    assert ("-alpha", pytest.approx(0.95)) in window.attribute_calls
    assert window.deiconify_calls == 1
    assert window.idle_calls == 1
    assert updates == ["updated"]
    assert window.focus_force_calls == 0
    assert window.lift_calls == 0


def test_controller_applies_bounded_opacity_and_hide() -> None:
    window = FakeWindow()
    controller = CompactWindowController(
        window,
        config=CompactWindowConfig(minimum_opacity=0.30, opacity=0.85),
    )

    assert controller.set_opacity(0.05) == pytest.approx(0.30)
    controller.set_topmost(False)
    controller.hide()

    assert window.attribute_calls[-2:] == [("-alpha", 0.30), ("-topmost", False)]
    assert window.withdraw_calls == 1


def test_geometry_store_and_key_must_be_configured_together() -> None:
    window = FakeWindow()

    with pytest.raises(ValueError):
        CompactWindowController(window, geometry_key="cue")
    with pytest.raises(ValueError):
        CompactWindowController(window, geometry_store=MemoryGeometryStore())
