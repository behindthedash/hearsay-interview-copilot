"""Knowledge indexing, provider contracts, and retrieval."""

from .embeddings import DeterministicHashEmbedding, EmbeddingModel, FastEmbedEmbedding
from .index import LocalKnowledgeIndex
from .manifest import ManifestValidationError, load_manifest
from .models import (
    ChunkWrite,
    CollectionSpec,
    DocumentState,
    EnsureCollectionResult,
    ExperienceStatus,
    KnowledgeChunk,
    KnowledgeDocument,
    QueryRequest,
    RefreshReport,
    SearchResult,
    StoreHealth,
    StoreStats,
)
from .pgvector_store import PostgresKnowledgeStore, PostgresStoreError
from .provider import EmbeddingCompatibilityError, KnowledgeStore
from .store import SQLiteKnowledgeStore, SQLiteLocalStore

__all__ = [
    "ChunkWrite",
    "CollectionSpec",
    "DeterministicHashEmbedding",
    "DocumentState",
    "EmbeddingCompatibilityError",
    "EmbeddingModel",
    "EnsureCollectionResult",
    "ExperienceStatus",
    "FastEmbedEmbedding",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "KnowledgeStore",
    "LocalKnowledgeIndex",
    "ManifestValidationError",
    "PostgresKnowledgeStore",
    "PostgresStoreError",
    "QueryRequest",
    "RefreshReport",
    "SQLiteKnowledgeStore",
    "SQLiteLocalStore",
    "SearchResult",
    "StoreHealth",
    "StoreStats",
    "load_manifest",
]
