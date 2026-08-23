from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from interview_copilot.cue_retrieval import CueEvidence, CueState, InterviewCue
from interview_copilot.knowledge.models import ExperienceStatus
from interview_copilot.ui.cue_overlay import (
    CueOverlayPresenter,
    CueOverlayProjection,
    CueOverlayStateModel,
    JsonOverlaySettingsStore,
    OverlayPresentationSettings,
    OverlayState,
    project_cue,
)
from interview_copilot.ui.windowing import WindowGeometry


def _evidence(
    status: ExperienceStatus,
    *,
    text: str = "Built the retrieval path and preserved source provenance.",
    title: str = "Source-code RAG",
) -> CueEvidence:
    return CueEvidence(
        text=text,
        source_uri="projects/rag.md",
        title=title,
        experience_status=status,
        collection="career",
        chunk_id=f"chunk-{status.value}",
        score=0.91,
        project="winteam-rag",
    )


def _cue(
    generation: int,
    *,
    state: CueState = CueState.READY,
    session_id: str = "session-1",
) -> InterviewCue:
    return InterviewCue(
        session_id=session_id,
        generation=generation,
        question="Tell me about a RAG system you built.",
        intent="RAG system experience",
        state=state,
        primary_story=(
            _evidence(ExperienceStatus.IMPLEMENTED) if state is CueState.READY else None
        ),
        supporting_points=(
            (_evidence(ExperienceStatus.PROTOTYPE, title="MCP integration"),)
            if state is CueState.READY
            else ()
        ),
        role_bridge=(
            _evidence(ExperienceStatus.DESIGN, title="Compliance adaptation")
            if state is CueState.READY
            else None
        ),
        confidence=0.91,
        detail="retrieval unavailable (RuntimeError)" if state is CueState.UNAVAILABLE else None,
    )


def test_project_cue_keeps_claim_status_visible_and_compact() -> None:
    long_text = "word " * 100
    cue = InterviewCue(
        session_id="session-1",
        generation=2,
        question="How would you use this experience?",
        intent="experience",
        state=CueState.READY,
        primary_story=_evidence(ExperienceStatus.IMPLEMENTED, text=long_text),
        supporting_points=(_evidence(ExperienceStatus.PROTOTYPE),),
        role_bridge=_evidence(ExperienceStatus.HYPOTHETICAL),
    )

    projection = project_cue(cue)

    assert projection.state is OverlayState.READY
    assert projection.primary_story is not None
    assert projection.primary_story.status_label == "IMPLEMENTED"
    assert len(projection.primary_story.text) <= 260
    assert projection.supporting_points[0].status_label == "PROTOTYPE"
    assert projection.role_bridge is not None
    assert projection.role_bridge.status_label == "HYPOTHETICAL"


def test_state_model_exposes_listening_retrieving_and_terminal_states() -> None:
    model = CueOverlayStateModel()

    model.begin_session("session-1")
    assert model.projection.state is OverlayState.LISTENING

    assert model.set_retrieving("session-1", 1, "What did you build?")
    assert model.projection.state is OverlayState.RETRIEVING

    assert model.apply_cue(_cue(1, state=CueState.NO_MATCH))
    assert model.projection.state is OverlayState.NO_MATCH

    assert model.apply_cue(_cue(2, state=CueState.UNAVAILABLE))
    assert model.projection.state is OverlayState.UNAVAILABLE


def test_stale_generation_never_overwrites_newer_projection() -> None:
    model = CueOverlayStateModel()
    model.begin_session("session-1")
    assert model.set_retrieving("session-1", 4, "Newest question")

    assert not model.apply_cue(_cue(3))
    assert model.projection.state is OverlayState.RETRIEVING
    assert model.projection.generation == 4
    assert model.projection.question == "Newest question"


def test_prior_session_cue_is_rejected() -> None:
    model = CueOverlayStateModel()
    model.begin_session("session-new")

    assert not model.apply_cue(_cue(8, session_id="session-old"))
    assert model.projection.state is OverlayState.LISTENING
    assert model.projection.session_id == "session-new"


def test_clear_suppresses_inflight_result_for_cleared_generation() -> None:
    model = CueOverlayStateModel()
    model.begin_session("session-1")
    assert model.set_retrieving("session-1", 5, "Question")

    model.clear()

    assert not model.apply_cue(_cue(5))
    assert model.projection.state is OverlayState.IDLE
    assert model.apply_cue(_cue(6))
    assert model.projection.state is OverlayState.READY


class _FakeView:
    def __init__(self) -> None:
        self.rendered: list[CueOverlayProjection] = []
        self.font_sizes: list[int] = []

    def render(self, projection: CueOverlayProjection) -> None:
        self.rendered.append(projection)

    def set_font_size(self, font_size: int) -> None:
        self.font_sizes.append(font_size)


class _FakeWindowController:
    def __init__(self) -> None:
        self.shown = 0
        self.hidden = 0
        self.opacity = 0.95
        self.topmost = True
        self.safe_updates = 0
        self.persisted = WindowGeometry(500, 300, 10, 20)

    def safe_update(self, update: Callable[[], None]) -> None:
        self.safe_updates += 1
        update()

    def show(self) -> None:
        self.shown += 1

    def hide(self) -> None:
        self.hidden += 1

    def set_opacity(self, value: float) -> float:
        self.opacity = min(1.0, max(0.20, value))
        return self.opacity

    def set_topmost(self, enabled: bool) -> None:
        self.topmost = enabled

    def persist_geometry(self) -> WindowGeometry:
        return self.persisted


class _MemorySettingsStore:
    def __init__(self) -> None:
        self.saved: list[OverlayPresentationSettings] = []

    def load_overlay_settings(self, key: str) -> OverlayPresentationSettings | None:
        del key
        return self.saved[-1] if self.saved else None

    def save_overlay_settings(self, key: str, settings: OverlayPresentationSettings) -> None:
        assert key == "cue-overlay"
        self.saved.append(settings)


def test_presenter_schedules_worker_updates_and_rejects_stale_cue() -> None:
    view = _FakeView()
    window = _FakeWindowController()
    scheduled: list[Callable[[], None]] = []
    presenter = CueOverlayPresenter(view, window, scheduled.append)

    presenter.begin_session("session-1")
    presenter.set_retrieving("session-1", 3, "New question")
    presenter.publish_cue(_cue(2))

    assert view.rendered == []
    for callback in scheduled:
        callback()

    assert [item.state for item in view.rendered] == [
        OverlayState.LISTENING,
        OverlayState.RETRIEVING,
    ]
    assert window.safe_updates == 3


def test_presenter_controls_visibility_font_opacity_and_topmost() -> None:
    view = _FakeView()
    window = _FakeWindowController()
    store = _MemorySettingsStore()
    presenter = CueOverlayPresenter(
        view,
        window,
        lambda callback: callback(),
        settings_store=store,
    )

    presenter.show()
    presenter.hide()
    assert presenter.set_font_size(50) == 36
    assert presenter.set_opacity(0.1) == 0.20
    presenter.set_topmost(False)

    assert window.shown == 1
    assert window.hidden == 1
    assert view.font_sizes[-1] == 36
    assert window.opacity == 0.20
    assert not window.topmost
    assert store.saved[-1] == OverlayPresentationSettings(
        font_size=36,
        opacity=0.20,
        topmost=False,
    )


def test_json_settings_store_round_trips_presentation_only(tmp_path: Path) -> None:
    path = tmp_path / "ui.json"
    store = JsonOverlaySettingsStore(path)
    settings = OverlayPresentationSettings(font_size=19, opacity=0.85, topmost=False)

    store.save_geometry("cue-overlay", "500x300-120+40")
    store.save_overlay_settings("cue-overlay", settings)

    assert store.load_geometry("cue-overlay") == "500x300-120+40"
    assert store.load_overlay_settings("cue-overlay") == settings
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted == {
        "cue-overlay": {
            "font_size": 19,
            "geometry": "500x300-120+40",
            "opacity": 0.85,
            "topmost": False,
        }
    }
    assert "question" not in path.read_text(encoding="utf-8")
    assert "primary_story" not in path.read_text(encoding="utf-8")


def test_invalid_json_settings_fall_back_without_crashing(tmp_path: Path) -> None:
    path = tmp_path / "ui.json"
    path.write_text('{"cue-overlay":{"font_size":99}}', encoding="utf-8")
    store = JsonOverlaySettingsStore(path)

    assert store.load_overlay_settings("cue-overlay") is None
