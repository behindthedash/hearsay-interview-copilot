from __future__ import annotations

import ctypes
import math
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

_GEOMETRY_RE = re.compile(
    r"^\s*(?P<width>\d+)x(?P<height>\d+)(?P<x>[+-]\d+)(?P<y>[+-]\d+)\s*$"
)


class WindowSurface(Protocol):
    """Small Tk/customtkinter-compatible surface used by the presentation controller."""

    def attributes(self, option: str, value: object) -> object: ...

    def geometry(self, value: str | None = None) -> str: ...

    def deiconify(self) -> None: ...

    def withdraw(self) -> None: ...

    def update_idletasks(self) -> None: ...

    def winfo_screenwidth(self) -> int: ...

    def winfo_screenheight(self) -> int: ...


class GeometryStore(Protocol):
    """Persistence seam for consumer-owned settings/configuration storage."""

    def load_geometry(self, key: str) -> str | None: ...

    def save_geometry(self, key: str, geometry: str) -> None: ...


@dataclass(frozen=True)
class WindowGeometry:
    width: int
    height: int
    x: int
    y: int

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("window width and height must be positive")

    @classmethod
    def parse(cls, value: str) -> WindowGeometry:
        match = _GEOMETRY_RE.fullmatch(value)
        if match is None:
            raise ValueError(f"invalid window geometry: {value!r}")
        return cls(
            width=int(match.group("width")),
            height=int(match.group("height")),
            x=int(match.group("x")),
            y=int(match.group("y")),
        )

    def to_tk(self) -> str:
        return f"{self.width}x{self.height}{self.x:+d}{self.y:+d}"


@dataclass(frozen=True)
class WorkArea:
    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("work-area width and height must be positive")

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.height / 2)


@dataclass(frozen=True)
class CompactWindowConfig:
    topmost: bool = True
    opacity: float = 0.95
    minimum_opacity: float = 0.20
    maximum_opacity: float = 1.0
    minimum_visible_pixels: int = 64

    def __post_init__(self) -> None:
        if not 0 < self.minimum_opacity <= self.maximum_opacity <= 1:
            raise ValueError("opacity bounds must satisfy 0 < minimum <= maximum <= 1")
        if self.minimum_visible_pixels <= 0:
            raise ValueError("minimum_visible_pixels must be positive")
        clamp_opacity(self.opacity, self.minimum_opacity, self.maximum_opacity)


def clamp_opacity(value: float, minimum: float = 0.20, maximum: float = 1.0) -> float:
    if not math.isfinite(value):
        raise ValueError("opacity must be finite")
    if not 0 < minimum <= maximum <= 1:
        raise ValueError("opacity bounds must satisfy 0 < minimum <= maximum <= 1")
    return min(maximum, max(minimum, value))


def is_geometry_visible(
    geometry: WindowGeometry,
    work_areas: Sequence[WorkArea],
    *,
    minimum_visible_pixels: int = 64,
) -> bool:
    if minimum_visible_pixels <= 0:
        raise ValueError("minimum_visible_pixels must be positive")

    required_width = min(minimum_visible_pixels, geometry.width)
    required_height = min(minimum_visible_pixels, geometry.height)
    geometry_right = geometry.x + geometry.width
    geometry_bottom = geometry.y + geometry.height

    for area in work_areas:
        visible_width = max(0, min(geometry_right, area.right) - max(geometry.x, area.x))
        visible_height = max(0, min(geometry_bottom, area.bottom) - max(geometry.y, area.y))
        if visible_width >= required_width and visible_height >= required_height:
            return True
    return False


def recover_geometry(
    geometry: WindowGeometry,
    work_areas: Sequence[WorkArea],
    *,
    minimum_visible_pixels: int = 64,
) -> WindowGeometry:
    """Return a visible geometry, preserving the requested placement when it is usable."""
    if not work_areas or is_geometry_visible(
        geometry,
        work_areas,
        minimum_visible_pixels=minimum_visible_pixels,
    ):
        return geometry

    geometry_center = (
        geometry.x + geometry.width / 2,
        geometry.y + geometry.height / 2,
    )
    target = min(
        work_areas,
        key=lambda area: _distance_squared(geometry_center, area.center),
    )

    width = min(geometry.width, target.width)
    height = min(geometry.height, target.height)
    x = min(max(geometry.x, target.x), target.right - width)
    y = min(max(geometry.y, target.y), target.bottom - height)
    return WindowGeometry(width=width, height=height, x=x, y=y)


def system_work_areas(window: WindowSurface) -> tuple[WorkArea, ...]:
    """Return current monitor work areas, falling back to the toolkit primary screen."""
    if sys.platform == "win32":
        native = _win32_work_areas()
        if native:
            return native

    width = int(window.winfo_screenwidth())
    height = int(window.winfo_screenheight())
    if width <= 0 or height <= 0:
        return ()
    return (WorkArea(x=0, y=0, width=width, height=height),)


class CompactWindowController:
    """Reusable focus-safe presentation mechanics for compact consumer windows."""

    def __init__(
        self,
        window: WindowSurface,
        *,
        config: CompactWindowConfig | None = None,
        geometry_store: GeometryStore | None = None,
        geometry_key: str | None = None,
        work_area_provider: Callable[[], Sequence[WorkArea]] | None = None,
    ) -> None:
        if (geometry_store is None) != (geometry_key is None):
            raise ValueError("geometry_store and geometry_key must be provided together")
        if geometry_key is not None and not geometry_key.strip():
            raise ValueError("geometry_key must be non-empty")

        self._window = window
        self._config = config or CompactWindowConfig()
        self._geometry_store = geometry_store
        self._geometry_key = geometry_key
        self._work_area_provider = work_area_provider or (lambda: system_work_areas(window))
        self._topmost = self._config.topmost
        self._opacity = clamp_opacity(
            self._config.opacity,
            self._config.minimum_opacity,
            self._config.maximum_opacity,
        )

    @property
    def topmost(self) -> bool:
        return self._topmost

    @property
    def opacity(self) -> float:
        return self._opacity

    def set_topmost(self, enabled: bool) -> None:
        self._topmost = bool(enabled)
        self._window.attributes("-topmost", self._topmost)

    def set_opacity(self, value: float) -> float:
        self._opacity = clamp_opacity(
            value,
            self._config.minimum_opacity,
            self._config.maximum_opacity,
        )
        self._window.attributes("-alpha", self._opacity)
        return self._opacity

    def apply_presentation(self) -> None:
        self._window.attributes("-topmost", self._topmost)
        self._window.attributes("-alpha", self._opacity)

    def restore_geometry(self, fallback: WindowGeometry) -> WindowGeometry:
        geometry = fallback
        if self._geometry_store is not None and self._geometry_key is not None:
            saved = self._geometry_store.load_geometry(self._geometry_key)
            if saved:
                try:
                    geometry = WindowGeometry.parse(saved)
                except ValueError:
                    geometry = fallback

        recovered = recover_geometry(
            geometry,
            tuple(self._work_area_provider()),
            minimum_visible_pixels=self._config.minimum_visible_pixels,
        )
        self._window.geometry(recovered.to_tk())
        return recovered

    def persist_geometry(self) -> WindowGeometry:
        self._window.update_idletasks()
        geometry = WindowGeometry.parse(self._window.geometry())
        if self._geometry_store is not None and self._geometry_key is not None:
            self._geometry_store.save_geometry(self._geometry_key, geometry.to_tk())
        return geometry

    def show(self) -> None:
        """Show the window without focus/lift/activation calls."""
        self.apply_presentation()
        self._window.deiconify()

    def hide(self) -> None:
        self._window.withdraw()

    def safe_update(self, update: Callable[[], None]) -> None:
        """Apply background content changes without showing or focusing the window."""
        update()
        self._window.update_idletasks()


def _distance_squared(first: tuple[float, float], second: tuple[float, float]) -> float:
    return (first[0] - second[0]) ** 2 + (first[1] - second[1]) ** 2


def _win32_work_areas() -> tuple[WorkArea, ...]:
    """Enumerate Win32 monitor work areas without importing a GUI toolkit."""
    from ctypes import wintypes

    class MonitorInfo(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    monitor_enum_proc = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HANDLE,
        wintypes.HDC,
        ctypes.POINTER(wintypes.RECT),
        wintypes.LPARAM,
    )
    user32 = ctypes.windll.user32
    work_areas: list[WorkArea] = []

    @monitor_enum_proc
    def collect(hmonitor: object, _hdc: object, _rect: object, _data: int) -> bool:
        info = MonitorInfo()
        info.cbSize = ctypes.sizeof(MonitorInfo)
        if not user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
            return True
        work = info.rcWork
        width = work.right - work.left
        height = work.bottom - work.top
        if width > 0 and height > 0:
            work_areas.append(WorkArea(work.left, work.top, width, height))
        return True

    if not user32.EnumDisplayMonitors(None, None, collect, 0):
        return ()
    return tuple(work_areas)
