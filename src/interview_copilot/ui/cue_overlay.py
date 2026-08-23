from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from ..cue_retrieval import CueEvidence, CueState, InterviewCue
from ..knowledge.models import ExperienceStatus
from .windowing import CompactWindowConfig, CompactWindowController, WindowGeometry


class OverlayState(StrEnum):
    IDLE = "idle"
    LISTENING = "listening"
    RETRIEVING = "retrieving"
    READY = "ready"
    NO_MATCH = "no_match"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class OverlayEvidence:
    text: str
    title: str
    status: ExperienceStatus
    source_uri: str
    project: str | None = None

    @property
    def status_label(self) -> str:
        return self.status.value.upper()


@dataclass(frozen=True)
class CueOverlayProjection:
    state: OverlayState
    session_id: str | None = None
    generation: int | None = None
    headline: str = "Idle"
    question: str = ""
    primary_story: OverlayEvidence | None = None
    supporting_points: tuple[OverlayEvidence, ...] = ()
    role_bridge: OverlayEvidence | None = None
    detail: str | None = None


@dataclass(frozen=True)
class OverlayPresentationSettings:
    font_size: int = 16
    opacity: float = 0.95
    topmost: bool = True

    def __post_init__(self) -> None:
        if not 10 <= self.font_size <= 36:
            raise ValueError("font_size must be between 10 and 36")
        if not 0.20 <= self.opacity <= 1.0:
            raise ValueError("opacity must be between 0.20 and 1.0")


class OverlaySettingsStore(Protocol):
    def load_overlay_settings(self, key: str) -> OverlayPresentationSettings | None: ...

    def save_overlay_settings(self, key: str, settings: OverlayPresentationSettings) -> None: ...


class CueOverlayView(Protocol):
    def render(self, projection: CueOverlayProjection) -> None: ...

    def set_font_size(self, font_size: int) -> None: ...


class JsonOverlaySettingsStore:
    """Persist presentation settings only; cue content never enters this store."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load_geometry(self, key: str) -> str | None:
        record = self._record(key)
        value = record.get("geometry")
        return value if isinstance(value, str) else None

    def save_geometry(self, key: str, geometry: str) -> None:
        data = self._read()
        record = self._ensure_record(data, key)
        record["geometry"] = geometry
        self._write(data)

    def load_overlay_settings(self, key: str) -> OverlayPresentationSettings | None:
        record = self._record(key)
        if not record:
            return None

        font_size = record.get("font_size", 16)
        opacity = record.get("opacity", 0.95)
        topmost = record.get("topmost", True)
        if isinstance(font_size, bool) or not isinstance(font_size, int):
            return None
        if isinstance(opacity, bool) or not isinstance(opacity, (int, float)):
            return None
        if not isinstance(topmost, bool):
            return None
        try:
            return OverlayPresentationSettings(
                font_size=font_size,
                opacity=float(opacity),
                topmost=topmost,
            )
        except ValueError:
            return None

    def save_overlay_settings(self, key: str, settings: OverlayPresentationSettings) -> None:
        data = self._read()
        record = self._ensure_record(data, key)
        record.update(
            {
                "font_size": settings.font_size,
                "opacity": settings.opacity,
                "topmost": settings.topmost,
            }
        )
        self._write(data)

    def _record(self, key: str) -> dict[str, object]:
        value = self._read().get(key)
        return value if isinstance(value, dict) else {}

    def _read(self) -> dict[str, object]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _ensure_record(data: dict[str, object], key: str) -> dict[str, object]:
        current = data.get(key)
        if isinstance(current, dict):
            return current
        record: dict[str, object] = {}
        data[key] = record
        return record

    def _write(self, data: dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)


class CueOverlayStateModel:
    """Generation-aware presentation state independent of any GUI toolkit."""

    def __init__(self) -> None:
        self._session_id: str | None = None
        self._generation = 0
        self._cleared_through_generation = -1
        self._projection = CueOverlayProjection(state=OverlayState.IDLE)

    @property
    def projection(self) -> CueOverlayProjection:
        return self._projection

    @property
    def session_id(self) -> str | None:
        return self._session_id

    @property
    def generation(self) -> int:
        return self._generation

    def begin_session(self, session_id: str) -> None:
        session_id = session_id.strip()
        if not session_id:
            raise ValueError("session_id must be non-empty")
        self._session_id = session_id
        self._generation = 0
        self._cleared_through_generation = -1
        self._projection = CueOverlayProjection(
            state=OverlayState.LISTENING,
            session_id=session_id,
            headline="Listening",
            detail="Waiting for an interviewer question",
        )

    def set_listening(self, session_id: str) -> bool:
        if self._session_id != session_id:
            self.begin_session(session_id)
            return True
        self._projection = CueOverlayProjection(
            state=OverlayState.LISTENING,
            session_id=session_id,
            generation=self._generation or None,
            headline="Listening",
            detail="Waiting for an interviewer question",
        )
        return True

    def set_retrieving(
        self,
        session_id: str,
        generation: int,
        question: str,
    ) -> bool:
        if not self._accept_generation(session_id, generation):
            return False
        self._generation = generation
        self._projection = CueOverlayProjection(
            state=OverlayState.RETRIEVING,
            session_id=session_id,
            generation=generation,
            headline="Retrieving",
            question=_compact_text(question, 220),
            detail="Searching selected interview knowledge",
        )
        return True

    def apply_cue(self, cue: InterviewCue) -> bool:
        if not self._accept_generation(cue.session_id, cue.generation):
            return False
        self._generation = cue.generation
        self._projection = project_cue(cue)
        return True

    def clear(self) -> CueOverlayProjection:
        self._cleared_through_generation = max(
            self._cleared_through_generation,
            self._generation,
        )
        self._projection = CueOverlayProjection(
            state=OverlayState.IDLE,
            session_id=self._session_id,
            generation=self._generation or None,
            headline="Cleared",
        )
        return self._projection

    def _accept_generation(self, session_id: str, generation: int) -> bool:
        if generation <= 0:
            return False
        if self._session_id is None:
            self.begin_session(session_id)
        if session_id != self._session_id:
            return False
        if generation < self._generation:
            return False
        return generation > self._cleared_through_generation


class CueOverlayPresenter:
    """Schedule generation-safe cue projection onto a focus-safe compact window."""

    def __init__(
        self,
        view: CueOverlayView,
        window_controller: CompactWindowController,
        schedule: Callable[[Callable[[], None]], None],
        *,
        model: CueOverlayStateModel | None = None,
        settings_store: OverlaySettingsStore | None = None,
        settings_key: str = "cue-overlay",
        settings: OverlayPresentationSettings | None = None,
    ) -> None:
        if not settings_key.strip():
            raise ValueError("settings_key must be non-empty")
        self.view = view
        self.window_controller = window_controller
        self.schedule = schedule
        self.model = model or CueOverlayStateModel()
        self.settings_store = settings_store
        self.settings_key = settings_key
        self.settings = settings or OverlayPresentationSettings()
        self.view.set_font_size(self.settings.font_size)

    def begin_session(self, session_id: str) -> None:
        self._schedule_projection(lambda: self.model.begin_session(session_id))

    def set_listening(self, session_id: str) -> None:
        self._schedule_projection(lambda: self.model.set_listening(session_id))

    def set_retrieving(self, session_id: str, generation: int, question: str) -> None:
        self._schedule_projection(
            lambda: self.model.set_retrieving(session_id, generation, question)
        )

    def publish_cue(self, cue: InterviewCue) -> None:
        self._schedule_projection(lambda: self.model.apply_cue(cue))

    def clear(self) -> None:
        def apply() -> None:
            self.model.clear()
            self.view.render(self.model.projection)

        self.schedule(lambda: self.window_controller.safe_update(apply))

    def show(self) -> None:
        self.window_controller.show()

    def hide(self) -> None:
        self.window_controller.hide()

    def set_font_size(self, font_size: int) -> int:
        font_size = min(36, max(10, int(font_size)))
        self.settings = OverlayPresentationSettings(
            font_size=font_size,
            opacity=self.settings.opacity,
            topmost=self.settings.topmost,
        )
        self.view.set_font_size(font_size)
        self._persist_settings()
        return font_size

    def adjust_font_size(self, delta: int) -> int:
        return self.set_font_size(self.settings.font_size + delta)

    def set_opacity(self, opacity: float) -> float:
        applied = self.window_controller.set_opacity(opacity)
        self.settings = OverlayPresentationSettings(
            font_size=self.settings.font_size,
            opacity=applied,
            topmost=self.settings.topmost,
        )
        self._persist_settings()
        return applied

    def set_topmost(self, enabled: bool) -> None:
        self.window_controller.set_topmost(enabled)
        self.settings = OverlayPresentationSettings(
            font_size=self.settings.font_size,
            opacity=self.settings.opacity,
            topmost=bool(enabled),
        )
        self._persist_settings()

    def persist_geometry(self) -> WindowGeometry:
        return self.window_controller.persist_geometry()

    def _schedule_projection(self, mutate: Callable[[], object]) -> None:
        def apply() -> None:
            before = self.model.projection
            result = mutate()
            if result is False or self.model.projection is before:
                return
            self.view.render(self.model.projection)

        self.schedule(lambda: self.window_controller.safe_update(apply))

    def _persist_settings(self) -> None:
        if self.settings_store is not None:
            self.settings_store.save_overlay_settings(self.settings_key, self.settings)


def project_cue(cue: InterviewCue) -> CueOverlayProjection:
    state = {
        CueState.READY: OverlayState.READY,
        CueState.NO_MATCH: OverlayState.NO_MATCH,
        CueState.UNAVAILABLE: OverlayState.UNAVAILABLE,
    }[cue.state]
    headline = {
        OverlayState.READY: "Ready",
        OverlayState.NO_MATCH: "No match",
        OverlayState.UNAVAILABLE: "Unavailable",
    }[state]
    return CueOverlayProjection(
        state=state,
        session_id=cue.session_id,
        generation=cue.generation,
        headline=headline,
        question=_compact_text(cue.question, 220),
        primary_story=_project_evidence(cue.primary_story),
        supporting_points=tuple(_project_evidence(item) for item in cue.supporting_points),
        role_bridge=_project_evidence(cue.role_bridge),
        detail=_compact_text(cue.detail, 180) if cue.detail else None,
    )


def _project_evidence(evidence: CueEvidence | None) -> OverlayEvidence | None:
    if evidence is None:
        return None
    return OverlayEvidence(
        text=_compact_text(evidence.text, 260),
        title=_compact_text(evidence.title, 80),
        status=evidence.experience_status,
        source_uri=evidence.source_uri,
        project=evidence.project,
    )


def _compact_text(text: str, limit: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(1, limit - 1)].rstrip() + "…"


class TkCueOverlayWindow:
    """Small standard-library Tk shell for the cue overlay.

    Tk imports remain lazy so non-UI/headless use can import the package without a display.
    """

    def __init__(
        self,
        master: object,
        *,
        settings_store: JsonOverlaySettingsStore | None = None,
        settings_key: str = "cue-overlay",
        fallback_geometry: WindowGeometry | None = None,
    ) -> None:
        import tkinter as tk

        self._tk = tk
        self.settings_store = settings_store
        self.settings_key = settings_key
        settings = (
            settings_store.load_overlay_settings(settings_key)
            if settings_store is not None
            else None
        ) or OverlayPresentationSettings()

        self.window = tk.Toplevel(master)
        self.window.title("Interview Copilot")
        self.window.resizable(True, True)
        self._view = _TkCueOverlayView(self.window, font_size=settings.font_size)
        self._window_controller = CompactWindowController(
            self.window,
            config=CompactWindowConfig(topmost=settings.topmost, opacity=settings.opacity),
            geometry_store=settings_store,
            geometry_key=settings_key if settings_store is not None else None,
        )
        self.presenter = CueOverlayPresenter(
            self._view,
            self._window_controller,
            lambda callback: self.window.after(0, callback),
            settings_store=settings_store,
            settings_key=settings_key,
            settings=settings,
        )
        self._view.bind_controls(self)
        self._persist_after_id: str | None = None
        fallback = fallback_geometry or WindowGeometry(width=540, height=360, x=24, y=24)
        self._window_controller.restore_geometry(fallback)
        self._view.render(self.presenter.model.projection)
        self.window.protocol("WM_DELETE_WINDOW", self.hide)
        self.window.bind("<Configure>", self._on_configure)

    def begin_session(self, session_id: str) -> None:
        self.presenter.begin_session(session_id)

    def set_listening(self, session_id: str) -> None:
        self.presenter.set_listening(session_id)

    def set_retrieving(self, session_id: str, generation: int, question: str) -> None:
        self.presenter.set_retrieving(session_id, generation, question)

    def publish_cue(self, cue: InterviewCue) -> None:
        self.presenter.publish_cue(cue)

    def show(self) -> None:
        self.presenter.show()

    def hide(self) -> None:
        self._persist_now()
        self.presenter.hide()

    def clear(self) -> None:
        self.presenter.clear()

    def destroy(self) -> None:
        self._persist_now()
        self.window.destroy()

    def _on_configure(self, _event: object) -> None:
        if self.settings_store is None:
            return
        if self._persist_after_id is not None:
            self.window.after_cancel(self._persist_after_id)
        self._persist_after_id = self.window.after(350, self._persist_now)

    def _persist_now(self) -> None:
        self._persist_after_id = None
        if self.settings_store is not None:
            with suppress(ValueError, self._tk.TclError):
                self.presenter.persist_geometry()


class _TkCueOverlayView:
    def __init__(self, window: object, *, font_size: int) -> None:
        import tkinter as tk

        self._tk = tk
        self.window = window
        self.font_size = font_size
        self._support_labels: list[object] = []

        self.container = tk.Frame(window, padx=10, pady=8)
        self.container.pack(fill="both", expand=True)
        self.status_label = tk.Label(self.container, anchor="w")
        self.status_label.pack(fill="x")
        self.question_label = tk.Label(
            self.container,
            anchor="w",
            justify="left",
            wraplength=500,
        )
        self.question_label.pack(fill="x", pady=(4, 8))
        self.primary_label = tk.Label(
            self.container,
            anchor="w",
            justify="left",
            wraplength=500,
        )
        self.primary_label.pack(fill="x", pady=(0, 6))
        self.support_frame = tk.Frame(self.container)
        self.support_frame.pack(fill="both", expand=True)
        self.bridge_label = tk.Label(
            self.container,
            anchor="w",
            justify="left",
            wraplength=500,
        )
        self.bridge_label.pack(fill="x", pady=(6, 0))
        self.detail_label = tk.Label(
            self.container,
            anchor="w",
            justify="left",
            wraplength=500,
        )
        self.detail_label.pack(fill="x", pady=(4, 0))

        self.controls = tk.Frame(self.container)
        self.controls.pack(fill="x", pady=(8, 0))
        self._control_buttons: list[object] = []
        self.set_font_size(font_size)

    def bind_controls(self, owner: TkCueOverlayWindow) -> None:
        tk = self._tk
        specs = (
            ("Clear", owner.clear),
            ("Hide", owner.hide),
            ("A-", lambda: owner.presenter.adjust_font_size(-1)),
            ("A+", lambda: owner.presenter.adjust_font_size(1)),
            ("Fade-", lambda: owner.presenter.set_opacity(owner.presenter.settings.opacity - 0.05)),
            ("Fade+", lambda: owner.presenter.set_opacity(owner.presenter.settings.opacity + 0.05)),
        )
        for text, command in specs:
            button = tk.Button(self.controls, text=text, command=command, takefocus=False)
            button.pack(side="left", padx=(0, 4))
            self._control_buttons.append(button)

    def render(self, projection: CueOverlayProjection) -> None:
        self.status_label.configure(text=projection.headline)
        self.question_label.configure(
            text=(f"Question: {projection.question}" if projection.question else "")
        )
        self.primary_label.configure(text=self._evidence_text("Story", projection.primary_story))
        for label in self._support_labels:
            label.destroy()
        self._support_labels.clear()
        for evidence in projection.supporting_points:
            label = self._tk.Label(
                self.support_frame,
                text=self._evidence_text("•", evidence),
                anchor="w",
                justify="left",
                wraplength=500,
            )
            label.pack(fill="x", pady=(0, 3))
            self._apply_body_font(label)
            self._support_labels.append(label)
        self.bridge_label.configure(text=self._evidence_text("Bridge", projection.role_bridge))
        self.detail_label.configure(text=projection.detail or "")
        self.set_font_size(self.font_size)

    def set_font_size(self, font_size: int) -> None:
        self.font_size = font_size
        self.status_label.configure(font=("Segoe UI", max(10, font_size - 2), "bold"))
        self.question_label.configure(font=("Segoe UI", font_size, "bold"))
        self.primary_label.configure(font=("Segoe UI", font_size))
        self.bridge_label.configure(font=("Segoe UI", max(10, font_size - 1)))
        self.detail_label.configure(font=("Segoe UI", max(10, font_size - 2)))
        for label in self._support_labels:
            self._apply_body_font(label)

    def _apply_body_font(self, label: object) -> None:
        label.configure(font=("Segoe UI", max(10, self.font_size - 1)))

    @staticmethod
    def _evidence_text(prefix: str, evidence: OverlayEvidence | None) -> str:
        if evidence is None:
            return ""
        project = f" · {evidence.project}" if evidence.project else ""
        return f"{prefix} [{evidence.status_label}] {evidence.title}{project}: {evidence.text}"
