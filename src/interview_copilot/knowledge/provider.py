from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from .models import (
    ChunkWrite,
    CollectionSpec,
    DocumentState,
    EnsureCollectionResult,
    KnowledgeChunk,
    KnowledgeDocument,
    QueryRequest,
    SearchResult,
    StoreHealth,
    StoreStats,
)


class EmbeddingCompatibilityError(ValueError):
    """Raised when a collection and embedding configuration do not match."""


@runtime_checkable
class KnowledgeStore(Protocol):
    @property
    def provider_name(self) -> str: ...

    def ensure_collection(
        self,
        spec: CollectionSpec,
        *,
        rebuild_if_incompatible: bool = False,
    ) -> EnsureCollectionResult: ...

    def get_document_state(self, collection: str, source_uri: str) -> DocumentState | None: ...

    def list_source_uris(self, collection: str) -> set[str]: ...

    def upsert_document(self, collection: str, document: KnowledgeDocument) -> None: ...

    def replace_document_chunks(
        self,
        collection: str,
        document: KnowledgeDocument,
        chunks: Sequence[ChunkWrite],
    ) -> None: ...

    def delete_document(self, collection: str, source_uri: str) -> None: ...

    def query(self, request: QueryRequest) -> list[SearchResult]: ...

    def get_chunk(self, collection: str, chunk_id: str) -> KnowledgeChunk | None: ...

    def health(self) -> StoreHealth: ...

    def stats(self, collections: Sequence[str] | None = None) -> StoreStats: ...
