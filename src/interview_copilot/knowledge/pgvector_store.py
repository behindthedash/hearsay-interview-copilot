from __future__ import annotations

import json
import os
import re
import threading
from collections.abc import Sequence
from typing import Any

import numpy as np

from .models import (
    ChunkWrite,
    CollectionSpec,
    DocumentState,
    EnsureCollectionResult,
    ExperienceStatus,
    KnowledgeChunk,
    KnowledgeDocument,
    QueryRequest,
    SearchResult,
    StoreHealth,
    StoreStats,
)
from .provider import EmbeddingCompatibilityError

_SCHEMA_VERSION = 1
_SCHEMA_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ALLOWED_SSLMODES = {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}


class PostgresStoreError(RuntimeError):
    """Raised for secret-safe PostgreSQL provider failures."""


class PostgresKnowledgeStore:
    """Optional PostgreSQL + pgvector KnowledgeStore provider."""

    def __init__(
        self,
        database_url: str | None = None,
        *,
        sslmode: str | None = None,
        schema: str = "interview_copilot_kb",
    ) -> None:
        self.database_url = database_url or os.getenv("INTERVIEW_COPILOT_KB_DATABASE_URL")
        self.sslmode = sslmode or os.getenv("INTERVIEW_COPILOT_KB_SSLMODE")
        if self.sslmode is not None and self.sslmode not in _ALLOWED_SSLMODES:
            allowed = ", ".join(sorted(_ALLOWED_SSLMODES))
            raise ValueError(f"sslmode must be one of: {allowed}")
        if not _SCHEMA_PATTERN.fullmatch(schema):
            raise ValueError("schema must be a simple PostgreSQL identifier")

        self.schema = schema
        self._ready = False
        self._ready_lock = threading.Lock()

    @property
    def provider_name(self) -> str:
        return "postgres-pgvector"

    @property
    def _schema_sql(self) -> str:
        return f'"{self.schema}"'

    def _table(self, name: str) -> str:
        if not _SCHEMA_PATTERN.fullmatch(name):
            raise ValueError("table must be a simple PostgreSQL identifier")
        return f'{self._schema_sql}."{name}"'

    def _require_database_url(self) -> str:
        if not self.database_url:
            raise PostgresStoreError("PostgreSQL database URL is not configured")
        return self.database_url

    @staticmethod
    def _load_driver():
        try:
            import psycopg
            from pgvector.psycopg import register_vector
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise PostgresStoreError(
                "PostgreSQL support is not installed; install the 'postgres' extra"
            ) from exc
        return psycopg, dict_row, register_vector

    def _raw_connect(self):
        database_url = self._require_database_url()
        psycopg, dict_row, _ = self._load_driver()
        kwargs: dict[str, Any] = {"row_factory": dict_row}
        if self.sslmode is not None:
            kwargs["sslmode"] = self.sslmode
        try:
            return psycopg.connect(database_url, **kwargs)
        except Exception as exc:
            raise PostgresStoreError(
                f"PostgreSQL connection failed ({type(exc).__name__})"
            ) from None

    def _connect(self):
        connection = self._raw_connect()
        _, _, register_vector = self._load_driver()
        try:
            register_vector(connection)
        except Exception as exc:
            connection.close()
            raise PostgresStoreError(
                f"pgvector type registration failed ({type(exc).__name__})"
            ) from None
        return connection

    def _ensure_ready(self) -> None:
        if self._ready:
            return
        with self._ready_lock:
            if self._ready:
                return
            self._bootstrap()
            self._ready = True

    def _bootstrap(self) -> None:
        with self._raw_connect() as connection:
            connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
            extension = connection.execute(
                "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
            ).fetchone()
            if extension is None:
                raise PostgresStoreError("pgvector extension is unavailable")

            connection.execute(f"CREATE SCHEMA IF NOT EXISTS {self._schema_sql}")
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self._table("schema_metadata")} (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            current = connection.execute(
                f"SELECT value FROM {self._table('schema_metadata')} WHERE key = 'schema_version'"
            ).fetchone()
            if current is None:
                connection.execute(
                    f"""
                    INSERT INTO {self._table("schema_metadata")}(key, value)
                    VALUES ('schema_version', %s)
                    """,
                    (str(_SCHEMA_VERSION),),
                )
            elif int(current["value"]) != _SCHEMA_VERSION:
                raise PostgresStoreError(
                    f"Unsupported PostgreSQL knowledge schema version {current['value']}"
                )

            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self._table("collections")} (
                    name TEXT PRIMARY KEY,
                    embedding_model TEXT NOT NULL,
                    embedding_dimension INTEGER NOT NULL CHECK (embedding_dimension > 0)
                )
                """
            )
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self._table("documents")} (
                    collection TEXT NOT NULL
                        REFERENCES {self._table("collections")}(name) ON DELETE CASCADE,
                    source_uri TEXT NOT NULL,
                    title TEXT NOT NULL,
                    source_hash TEXT NOT NULL,
                    manifest_hash TEXT NOT NULL,
                    experience_status TEXT NOT NULL,
                    project TEXT,
                    topics_json JSONB NOT NULL,
                    skills_json JSONB NOT NULL,
                    metadata_json JSONB NOT NULL,
                    PRIMARY KEY(collection, source_uri)
                )
                """
            )
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self._table("chunks")} (
                    collection TEXT NOT NULL,
                    chunk_id TEXT NOT NULL,
                    source_uri TEXT NOT NULL,
                    ordinal INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    title TEXT NOT NULL,
                    experience_status TEXT NOT NULL,
                    project TEXT,
                    topics_json JSONB NOT NULL,
                    skills_json JSONB NOT NULL,
                    metadata_json JSONB NOT NULL,
                    embedding VECTOR NOT NULL,
                    PRIMARY KEY(collection, chunk_id),
                    UNIQUE(collection, source_uri, ordinal),
                    FOREIGN KEY(collection, source_uri)
                        REFERENCES {self._table("documents")}(collection, source_uri)
                        ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                f"""
                CREATE INDEX IF NOT EXISTS chunks_collection_source_idx
                ON {self._table("chunks")}(collection, source_uri)
                """
            )

        with self._connect() as connection:
            connection.execute("SELECT 1").fetchone()

    def _require_collection(self, connection, collection: str):
        row = connection.execute(
            f"""
            SELECT name, embedding_model, embedding_dimension
            FROM {self._table("collections")}
            WHERE name = %s
            """,
            (collection,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown knowledge collection: {collection}")
        return row

    def ensure_collection(
        self,
        spec: CollectionSpec,
        *,
        rebuild_if_incompatible: bool = False,
    ) -> EnsureCollectionResult:
        self._ensure_ready()
        with self._connect() as connection:
            current = connection.execute(
                f"""
                SELECT embedding_model, embedding_dimension
                FROM {self._table("collections")}
                WHERE name = %s
                """,
                (spec.name,),
            ).fetchone()
            if current is None:
                connection.execute(
                    f"""
                    INSERT INTO {self._table("collections")}(
                        name, embedding_model, embedding_dimension
                    ) VALUES (%s, %s, %s)
                    """,
                    (spec.name, spec.embedding_model, spec.embedding_dimension),
                )
                return EnsureCollectionResult(created=True)

            compatible = (
                current["embedding_model"] == spec.embedding_model
                and int(current["embedding_dimension"]) == spec.embedding_dimension
            )
            if compatible:
                return EnsureCollectionResult()

            if not rebuild_if_incompatible:
                raise EmbeddingCompatibilityError(
                    f"Collection '{spec.name}' uses {current['embedding_model']} / "
                    f"{current['embedding_dimension']} dimensions, not "
                    f"{spec.embedding_model} / {spec.embedding_dimension}"
                )

            connection.execute(
                f"DELETE FROM {self._table('documents')} WHERE collection = %s",
                (spec.name,),
            )
            connection.execute(
                f"""
                UPDATE {self._table("collections")}
                SET embedding_model = %s, embedding_dimension = %s
                WHERE name = %s
                """,
                (spec.embedding_model, spec.embedding_dimension, spec.name),
            )
            return EnsureCollectionResult(rebuilt=True)

    def get_document_state(self, collection: str, source_uri: str) -> DocumentState | None:
        self._ensure_ready()
        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT d.source_hash, d.manifest_hash,
                       c.embedding_model, c.embedding_dimension
                FROM {self._table("documents")} d
                JOIN {self._table("collections")} c ON c.name = d.collection
                WHERE d.collection = %s AND d.source_uri = %s
                """,
                (collection, source_uri),
            ).fetchone()
        if row is None:
            return None
        return DocumentState(
            source_hash=row["source_hash"],
            manifest_hash=row["manifest_hash"],
            embedding_model=row["embedding_model"],
            embedding_dimension=int(row["embedding_dimension"]),
        )

    def list_source_uris(self, collection: str) -> set[str]:
        self._ensure_ready()
        with self._connect() as connection:
            self._require_collection(connection, collection)
            rows = connection.execute(
                f"SELECT source_uri FROM {self._table('documents')} WHERE collection = %s",
                (collection,),
            ).fetchall()
        return {row["source_uri"] for row in rows}

    def upsert_document(self, collection: str, document: KnowledgeDocument) -> None:
        self._ensure_ready()
        with self._connect() as connection:
            self._require_collection(connection, collection)
            self._upsert_document(connection, collection, document)

    def _upsert_document(self, connection, collection: str, document: KnowledgeDocument) -> None:
        connection.execute(
            f"""
            INSERT INTO {self._table("documents")}(
                collection, source_uri, title, source_hash, manifest_hash,
                experience_status, project, topics_json, skills_json, metadata_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb)
            ON CONFLICT(collection, source_uri) DO UPDATE SET
                title = excluded.title,
                source_hash = excluded.source_hash,
                manifest_hash = excluded.manifest_hash,
                experience_status = excluded.experience_status,
                project = excluded.project,
                topics_json = excluded.topics_json,
                skills_json = excluded.skills_json,
                metadata_json = excluded.metadata_json
            """,
            (
                collection,
                document.source_uri,
                document.title,
                document.source_hash,
                document.manifest_hash,
                document.experience_status.value,
                document.project,
                json.dumps(document.topics),
                json.dumps(document.skills),
                json.dumps(document.metadata, sort_keys=True),
            ),
        )

    def replace_document_chunks(
        self,
        collection: str,
        document: KnowledgeDocument,
        chunks: Sequence[ChunkWrite],
    ) -> None:
        self._ensure_ready()
        with self._connect() as connection:
            collection_row = self._require_collection(connection, collection)
            dimension = int(collection_row["embedding_dimension"])
            for write in chunks:
                if write.chunk.source_uri != document.source_uri:
                    raise ValueError("chunk source_uri does not match document source_uri")
                if len(write.embedding) != dimension:
                    raise EmbeddingCompatibilityError(
                        f"Chunk embedding dimension {len(write.embedding)} does not match "
                        f"collection '{collection}' dimension {dimension}"
                    )

            self._upsert_document(connection, collection, document)
            connection.execute(
                f"""
                DELETE FROM {self._table("chunks")}
                WHERE collection = %s AND source_uri = %s
                """,
                (collection, document.source_uri),
            )
            if chunks:
                connection.executemany(
                    f"""
                    INSERT INTO {self._table("chunks")}(
                        collection, chunk_id, source_uri, ordinal, content, content_hash,
                        title, experience_status, project, topics_json, skills_json,
                        metadata_json, embedding
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s::jsonb, %s::jsonb, %s::jsonb, %s
                    )
                    """,
                    [
                        (
                            collection,
                            write.chunk.chunk_id,
                            write.chunk.source_uri,
                            write.chunk.ordinal,
                            write.chunk.content,
                            write.chunk.content_hash,
                            write.chunk.title,
                            write.chunk.experience_status.value,
                            write.chunk.project,
                            json.dumps(write.chunk.topics),
                            json.dumps(write.chunk.skills),
                            json.dumps(write.chunk.metadata, sort_keys=True),
                            np.asarray(write.embedding, dtype=np.float32),
                        )
                        for write in chunks
                    ],
                )

    def delete_document(self, collection: str, source_uri: str) -> None:
        self._ensure_ready()
        with self._connect() as connection:
            self._require_collection(connection, collection)
            connection.execute(
                f"""
                DELETE FROM {self._table("documents")}
                WHERE collection = %s AND source_uri = %s
                """,
                (collection, source_uri),
            )

    def _validate_query_collections(self, connection, request: QueryRequest) -> tuple[str, ...]:
        collections = tuple(dict.fromkeys(request.collections))
        dimension = len(request.embedding)
        for collection in collections:
            row = self._require_collection(connection, collection)
            if row["embedding_model"] != request.embedding_model:
                raise EmbeddingCompatibilityError(
                    f"Query model '{request.embedding_model}' does not match "
                    f"collection '{collection}' model '{row['embedding_model']}'"
                )
            if int(row["embedding_dimension"]) != dimension:
                raise EmbeddingCompatibilityError(
                    f"Query embedding dimension {dimension} does not match "
                    f"collection '{collection}' dimension {row['embedding_dimension']}"
                )
        return collections

    def query(self, request: QueryRequest) -> list[SearchResult]:
        if request.top_k <= 0:
            return []
        self._ensure_ready()

        vector = np.asarray(request.embedding, dtype=np.float32).reshape(-1)
        with self._connect() as connection:
            collections = self._validate_query_collections(connection, request)
            if float(np.linalg.norm(vector)) == 0.0:
                rows = connection.execute(
                    f"""
                    SELECT collection, chunk_id, source_uri, ordinal, content, content_hash,
                           title, experience_status, project, topics_json, skills_json,
                           metadata_json, 0.0::double precision AS score
                    FROM {self._table("chunks")}
                    WHERE collection = ANY(%s)
                    ORDER BY collection, source_uri, ordinal
                    LIMIT %s
                    """,
                    (list(collections), request.top_k),
                ).fetchall()
            else:
                rows = connection.execute(
                    f"""
                    SELECT collection, chunk_id, source_uri, ordinal, content, content_hash,
                           title, experience_status, project, topics_json, skills_json,
                           metadata_json,
                           1 - (embedding <=> %s) AS score
                    FROM {self._table("chunks")}
                    WHERE collection = ANY(%s)
                    ORDER BY embedding <=> %s, collection, source_uri, ordinal
                    LIMIT %s
                    """,
                    (vector, list(collections), vector, request.top_k),
                ).fetchall()

        return [
            SearchResult(
                score=float(row["score"]),
                collection=row["collection"],
                chunk=self._row_to_chunk(row),
            )
            for row in rows
        ]

    def get_chunk(self, collection: str, chunk_id: str) -> KnowledgeChunk | None:
        self._ensure_ready()
        with self._connect() as connection:
            self._require_collection(connection, collection)
            row = connection.execute(
                f"""
                SELECT chunk_id, source_uri, ordinal, content, content_hash, title,
                       experience_status, project, topics_json, skills_json, metadata_json
                FROM {self._table("chunks")}
                WHERE collection = %s AND chunk_id = %s
                """,
                (collection, chunk_id),
            ).fetchone()
        return None if row is None else self._row_to_chunk(row)

    def health(self) -> StoreHealth:
        if not self.database_url:
            return StoreHealth(
                healthy=False,
                provider=self.provider_name,
                detail="database URL is not configured",
            )
        try:
            self._ensure_ready()
            with self._connect() as connection:
                extension = connection.execute(
                    "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
                ).fetchone()
                schema_version = connection.execute(
                    f"""
                    SELECT value FROM {self._table("schema_metadata")}
                    WHERE key = 'schema_version'
                    """
                ).fetchone()
            if extension is None or schema_version is None:
                return StoreHealth(
                    healthy=False,
                    provider=self.provider_name,
                    detail="required pgvector/schema capability is unavailable",
                )
            return StoreHealth(
                healthy=True,
                provider=self.provider_name,
                detail=(
                    f"schema_version={schema_version['value']}; "
                    f"vector={extension['extversion']}"
                ),
            )
        except Exception as exc:
            return StoreHealth(
                healthy=False,
                provider=self.provider_name,
                detail=f"provider validation failed ({type(exc).__name__})",
            )

    def stats(self, collections: Sequence[str] | None = None) -> StoreStats:
        self._ensure_ready()
        with self._connect() as connection:
            if collections is None:
                collection_count = int(
                    connection.execute(
                        f"SELECT COUNT(*) AS count FROM {self._table('collections')}"
                    ).fetchone()["count"]
                )
                document_count = int(
                    connection.execute(
                        f"SELECT COUNT(*) AS count FROM {self._table('documents')}"
                    ).fetchone()["count"]
                )
                chunk_count = int(
                    connection.execute(
                        f"SELECT COUNT(*) AS count FROM {self._table('chunks')}"
                    ).fetchone()["count"]
                )
            else:
                scoped = tuple(dict.fromkeys(collections))
                if not scoped:
                    return StoreStats(collections=0, documents=0, chunks=0)
                for collection in scoped:
                    self._require_collection(connection, collection)
                collection_count = len(scoped)
                document_count = int(
                    connection.execute(
                        f"""
                        SELECT COUNT(*) AS count FROM {self._table("documents")}
                        WHERE collection = ANY(%s)
                        """,
                        (list(scoped),),
                    ).fetchone()["count"]
                )
                chunk_count = int(
                    connection.execute(
                        f"""
                        SELECT COUNT(*) AS count FROM {self._table("chunks")}
                        WHERE collection = ANY(%s)
                        """,
                        (list(scoped),),
                    ).fetchone()["count"]
                )

        return StoreStats(
            collections=collection_count,
            documents=document_count,
            chunks=chunk_count,
        )

    @staticmethod
    def _row_to_chunk(row) -> KnowledgeChunk:
        def sequence(value) -> tuple[str, ...]:
            if isinstance(value, str):
                value = json.loads(value)
            return tuple(value)

        metadata = row["metadata_json"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        return KnowledgeChunk(
            chunk_id=row["chunk_id"],
            source_uri=row["source_uri"],
            ordinal=int(row["ordinal"]),
            content=row["content"],
            content_hash=row["content_hash"],
            title=row["title"],
            experience_status=ExperienceStatus(row["experience_status"]),
            project=row["project"],
            topics=sequence(row["topics_json"]),
            skills=sequence(row["skills_json"]),
            metadata=dict(metadata),
        )
