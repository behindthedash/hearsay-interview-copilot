from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class ExperienceStatus(StrEnum):
    IMPLEMENTED = "implemented"
    PROTOTYPE = "prototype"
    DESIGN = "design"
    HYPOTHETICAL = "hypothetical"


@dataclass(frozen=True)
class ManifestDocument:
    source_uri: str
    path: Path
    title: str
    experience_status: ExperienceStatus
    project: str | None = None
    topics: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str
    source_uri: str
    ordinal: int
    content: str
    content_hash: str
    title: str
    experience_status: ExperienceStatus
    project: str | None
    topics: tuple[str, ...]
    skills: tuple[str, ...]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class SearchResult:
    score: float
    chunk: KnowledgeChunk


@dataclass(frozen=True)
class RefreshReport:
    indexed: int = 0
    reused: int = 0
    removed: int = 0
    chunks_written: int = 0
    embedding_config_reset: bool = False
