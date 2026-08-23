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
class KnowledgeDocument:
    source_uri: str
    title: str
    source_hash: str
    manifest_hash: str
    experience_status: ExperienceStatus
    project: str | None = None
    topics: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CollectionSpec:
    name: str
    embedding_model: str
    embedding_dimension: int

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("collection name must be non-empty")
        if not self.embedding_model.strip():
            raise ValueError("embedding model must be non-empty")
        if self.embedding_dimension <= 0:
            raise ValueError("embedding dimension must be positive")


@dataclass(frozen=True)
class DocumentState:
    source_hash: str
    manifest_hash: str
    embedding_model: str
    embedding_dimension: int


@dataclass(frozen=True)
class ChunkWrite:
    chunk: KnowledgeChunk
    embedding: tuple[float, ...]


@dataclass(frozen=True)
class QueryRequest:
    collections: tuple[str, ...]
    embedding_model: str
    embedding: tuple[float, ...]
    top_k: int = 5

    def __post_init__(self) -> None:
        if not self.collections:
            raise ValueError("query must specify at least one collection")
        if any(not collection.strip() for collection in self.collections):
            raise ValueError("query collections must be non-empty")
        if not self.embedding_model.strip():
            raise ValueError("query embedding model must be non-empty")


@dataclass(frozen=True)
class SearchResult:
    score: float
    collection: str
    chunk: KnowledgeChunk


@dataclass(frozen=True)
class EnsureCollectionResult:
    created: bool = False
    rebuilt: bool = False


@dataclass(frozen=True)
class StoreHealth:
    healthy: bool
    provider: str
    detail: str | None = None


@dataclass(frozen=True)
class StoreStats:
    collections: int
    documents: int
    chunks: int


@dataclass(frozen=True)
class RefreshReport:
    indexed: int = 0
    reused: int = 0
    removed: int = 0
    chunks_written: int = 0
    embedding_config_reset: bool = False
