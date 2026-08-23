from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import ExperienceStatus, ManifestDocument

_SUPPORTED_SUFFIXES = {".md", ".markdown", ".txt", ".json"}


class ManifestValidationError(ValueError):
    """Raised when a corpus manifest cannot be safely interpreted."""


def _string_tuple(value: Any, *, field_name: str, source_uri: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ManifestValidationError(
            f"{source_uri}: '{field_name}' must be a list of non-empty strings"
        )
    return tuple(item.strip() for item in value)


def load_manifest(corpus_root: str | Path, manifest_name: str = "corpus.json") -> list[ManifestDocument]:
    root = Path(corpus_root).expanduser().resolve()
    manifest_path = root / manifest_name
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManifestValidationError(f"Corpus manifest not found: {manifest_path}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestValidationError(f"Invalid JSON in corpus manifest: {exc}") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("documents"), list):
        raise ManifestValidationError("corpus.json must contain a top-level 'documents' array")

    documents: list[ManifestDocument] = []
    seen: set[str] = set()

    for index, item in enumerate(payload["documents"]):
        if not isinstance(item, dict):
            raise ManifestValidationError(f"documents[{index}] must be an object")

        raw_path = item.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ManifestValidationError(f"documents[{index}] is missing a non-empty 'path'")

        candidate = (root / raw_path).resolve()
        try:
            relative = candidate.relative_to(root)
        except ValueError as exc:
            raise ManifestValidationError(
                f"documents[{index}] path escapes the selected corpus directory: {raw_path}"
            ) from exc

        source_uri = relative.as_posix()
        if source_uri in seen:
            raise ManifestValidationError(f"Duplicate corpus document path: {source_uri}")
        seen.add(source_uri)

        if candidate.suffix.lower() not in _SUPPORTED_SUFFIXES:
            raise ManifestValidationError(
                f"{source_uri}: unsupported file type '{candidate.suffix}'"
            )
        if not candidate.is_file():
            raise ManifestValidationError(f"{source_uri}: source file does not exist")

        raw_status = item.get("experience_status")
        if raw_status is None:
            raise ManifestValidationError(
                f"{source_uri}: required 'experience_status' is missing"
            )
        try:
            status = ExperienceStatus(str(raw_status))
        except ValueError as exc:
            allowed = ", ".join(item.value for item in ExperienceStatus)
            raise ManifestValidationError(
                f"{source_uri}: invalid experience_status '{raw_status}'; expected one of {allowed}"
            ) from exc

        title = item.get("title") or candidate.stem
        if not isinstance(title, str) or not title.strip():
            raise ManifestValidationError(f"{source_uri}: 'title' must be a non-empty string")

        project = item.get("project")
        if project is not None and (not isinstance(project, str) or not project.strip()):
            raise ManifestValidationError(f"{source_uri}: 'project' must be a non-empty string")

        metadata = item.get("metadata") or {}
        if not isinstance(metadata, dict):
            raise ManifestValidationError(f"{source_uri}: 'metadata' must be an object")

        documents.append(
            ManifestDocument(
                source_uri=source_uri,
                path=candidate,
                title=title.strip(),
                experience_status=status,
                project=project.strip() if isinstance(project, str) else None,
                topics=_string_tuple(item.get("topics"), field_name="topics", source_uri=source_uri),
                skills=_string_tuple(item.get("skills"), field_name="skills", source_uri=source_uri),
                metadata=metadata,
            )
        )

    return documents


def read_document_text(document: ManifestDocument) -> str:
    if document.path.suffix.lower() == ".json":
        try:
            payload = json.loads(document.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ManifestValidationError(
                f"{document.source_uri}: source JSON is invalid: {exc}"
            ) from exc
        return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)

    return document.path.read_text(encoding="utf-8")
