from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path

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


class SQLiteKnowledgeStore:
    """Local SQLite metadata + NumPy cosine-search KnowledgeStore provider."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).expanduser()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @property
    def provider_name(self) -> str:
        return "sqlite-numpy"

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            self._reset_legacy_schema_if_needed(connection)
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS collections (
                    name TEXT PRIMARY KEY,
                    embedding_model TEXT NOT NULL,
                    embedding_dimension INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS documents (
                    collection TEXT NOT NULL REFERENCES collections(name) ON DELETE CASCADE,
                    source_uri TEXT NOT NULL,
                    title TEXT NOT NULL,
                    source_hash TEXT NOT NULL,
                    manifest_hash TEXT NOT NULL,
                    experience_status TEXT NOT NULL,
                    project TEXT,
                    topics_json TEXT NOT NULL,
                    skills_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    PRIMARY KEY(collection, source_uri)
                );

                CREATE TABLE IF NOT EXISTS chunks (
                    collection TEXT NOT NULL,
                    chunk_id TEXT NOT NULL,
                    source_uri TEXT NOT NULL,
                    ordinal INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    title TEXT NOT NULL,
                    experience_status TEXT NOT NULL,
                    project TEXT,
                    topics_json TEXT NOT NULL,
                    skills_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    embedding_dimension INTEGER NOT NULL,
                    PRIMARY KEY(collection, chunk_id),
                    UNIQUE(collection, source_uri, ordinal),
                    FOREIGN KEY(collection, source_uri)
                        REFERENCES documents(collection, source_uri) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_chunks_collection_source
                    ON chunks(collection, source_uri);
                """
            )

    @staticmethod
    def _reset_legacy_schema_if_needed(connection: sqlite3.Connection) -> None:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        if "documents" not in tables:
            return

        document_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(documents)").fetchall()
        }
        if "collection" in document_columns:
            return

        # The pre-provider schema is only a derived cache. Its source corpus remains
        # authoritative, so rebuilding it is safer than inventing a collection scope.
        connection.executescript(
            """
            DROP TABLE IF EXISTS chunks;
            DROP TABLE IF EXISTS documents;
            DROP TABLE IF EXISTS index_metadata;
            DROP TABLE IF EXISTS collections;
            """
        )

    @staticmethod
    def _require_collection(
        connection: sqlite3.Connection,
        collection: str,
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT name, embedding_model, embedding_dimension FROM collections WHERE name = ?",
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
        with self._connect() as connection:
            current = connection.execute(
                "SELECT embedding_model, embedding_dimension FROM collections WHERE name = ?",
                (spec.name,),
            ).fetchone()
            if current is None:
                connection.execute(
                    "INSERT INTO collections(name, embedding_model, embedding_dimension) VALUES (?, ?, ?)",
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

            connection.execute("DELETE FROM documents WHERE collection = ?", (spec.name,))
            connection.execute(
                """
                UPDATE collections
                SET embedding_model = ?, embedding_dimension = ?
                WHERE name = ?
                """,
                (spec.embedding_model, spec.embedding_dimension, spec.name),
            )
            return EnsureCollectionResult(rebuilt=True)

    def get_document_state(self, collection: str, source_uri: str) -> DocumentState | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT d.source_hash, d.manifest_hash,
                       c.embedding_model, c.embedding_dimension
                FROM documents d
                JOIN collections c ON c.name = d.collection
                WHERE d.collection = ? AND d.source_uri = ?
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
        with self._connect() as connection:
            self._require_collection(connection, collection)
            return {
                row["source_uri"]
                for row in connection.execute(
                    "SELECT source_uri FROM documents WHERE collection = ?",
                    (collection,),
                ).fetchall()
            }

    def upsert_document(self, collection: str, document: KnowledgeDocument) -> None:
        with self._connect() as connection:
            self._require_collection(connection, collection)
            self._upsert_document(connection, collection, document)

    @staticmethod
    def _upsert_document(
        connection: sqlite3.Connection,
        collection: str,
        document: KnowledgeDocument,
    ) -> None:
        connection.execute(
            """
            INSERT INTO documents(
                collection, source_uri, title, source_hash, manifest_hash,
                experience_status, project, topics_json, skills_json, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                "DELETE FROM chunks WHERE collection = ? AND source_uri = ?",
                (collection, document.source_uri),
            )
            connection.executemany(
                """
                INSERT INTO chunks(
                    collection, chunk_id, source_uri, ordinal, content, content_hash,
                    title, experience_status, project, topics_json, skills_json,
                    metadata_json, embedding, embedding_dimension
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        np.asarray(write.embedding, dtype=np.float32).tobytes(),
                        dimension,
                    )
                    for write in chunks
                ],
            )

    def delete_document(self, collection: str, source_uri: str) -> None:
        with self._connect() as connection:
            self._require_collection(connection, collection)
            connection.execute(
                "DELETE FROM documents WHERE collection = ? AND source_uri = ?",
                (collection, source_uri),
            )

    def query(self, request: QueryRequest) -> list[SearchResult]:
        if request.top_k <= 0:
            return []

        collections = tuple(dict.fromkeys(request.collections))
        query = np.asarray(request.embedding, dtype=np.float32).reshape(-1)

        with self._connect() as connection:
            for collection in collections:
                row = self._require_collection(connection, collection)
                if row["embedding_model"] != request.embedding_model:
                    raise EmbeddingCompatibilityError(
                        f"Query model '{request.embedding_model}' does not match "
                        f"collection '{collection}' model '{row['embedding_model']}'"
                    )
                if int(row["embedding_dimension"]) != query.shape[0]:
                    raise EmbeddingCompatibilityError(
                        f"Query embedding dimension {query.shape[0]} does not match "
                        f"collection '{collection}' dimension {row['embedding_dimension']}"
                    )

            placeholders = ",".join("?" for _ in collections)
            rows = connection.execute(
                f"""
                SELECT collection, chunk_id, source_uri, ordinal, content, content_hash,
                       title, experience_status, project, topics_json, skills_json,
                       metadata_json, embedding, embedding_dimension
                FROM chunks
                WHERE collection IN ({placeholders})
                ORDER BY collection, source_uri, ordinal
                """,
                collections,
            ).fetchall()

        if not rows:
            return []

        matrix = np.stack(
            [
                np.frombuffer(
                    row["embedding"],
                    dtype=np.float32,
                    count=int(row["embedding_dimension"]),
                )
                for row in rows
            ]
        )
        matrix_norms = np.linalg.norm(matrix, axis=1)
        query_norm = float(np.linalg.norm(query))
        if query_norm == 0:
            scores = np.zeros(len(rows), dtype=np.float32)
        else:
            safe_norms = np.where(matrix_norms == 0, 1.0, matrix_norms)
            scores = (matrix @ query) / (safe_norms * query_norm)

        ranked = np.argsort(-scores, kind="stable")[: min(request.top_k, len(rows))]
        return [
            SearchResult(
                score=float(scores[index]),
                collection=rows[index]["collection"],
                chunk=self._row_to_chunk(rows[index]),
            )
            for index in ranked
        ]

    def get_chunk(self, collection: str, chunk_id: str) -> KnowledgeChunk | None:
        with self._connect() as connection:
            self._require_collection(connection, collection)
            row = connection.execute(
                """
                SELECT chunk_id, source_uri, ordinal, content, content_hash, title,
                       experience_status, project, topics_json, skills_json, metadata_json
                FROM chunks
                WHERE collection = ? AND chunk_id = ?
                """,
                (collection, chunk_id),
            ).fetchone()
        return None if row is None else self._row_to_chunk(row)

    def health(self) -> StoreHealth:
        try:
            with self._connect() as connection:
                connection.execute("SELECT 1").fetchone()
        except sqlite3.Error as exc:
            return StoreHealth(healthy=False, provider=self.provider_name, detail=str(exc))
        return StoreHealth(healthy=True, provider=self.provider_name)

    def stats(self, collections: Sequence[str] | None = None) -> StoreStats:
        with self._connect() as connection:
            if collections is None:
                collection_count = int(
                    connection.execute("SELECT COUNT(*) FROM collections").fetchone()[0]
                )
                document_count = int(
                    connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
                )
                chunk_count = int(connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])
            else:
                scoped = tuple(dict.fromkeys(collections))
                if not scoped:
                    return StoreStats(collections=0, documents=0, chunks=0)
                for collection in scoped:
                    self._require_collection(connection, collection)
                placeholders = ",".join("?" for _ in scoped)
                collection_count = len(scoped)
                document_count = int(
                    connection.execute(
                        f"SELECT COUNT(*) FROM documents WHERE collection IN ({placeholders})",
                        scoped,
                    ).fetchone()[0]
                )
                chunk_count = int(
                    connection.execute(
                        f"SELECT COUNT(*) FROM chunks WHERE collection IN ({placeholders})",
                        scoped,
                    ).fetchone()[0]
                )

        return StoreStats(
            collections=collection_count,
            documents=document_count,
            chunks=chunk_count,
        )

    def fetch_chunks(self, collection: str | None = None) -> list[KnowledgeChunk]:
        sql = (
            "SELECT chunk_id, source_uri, ordinal, content, content_hash, title, "
            "experience_status, project, topics_json, skills_json, metadata_json FROM chunks"
        )
        params: tuple[object, ...] = ()
        if collection is not None:
            sql += " WHERE collection = ?"
            params = (collection,)
        sql += " ORDER BY collection, source_uri, ordinal"

        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._row_to_chunk(row) for row in rows]

    @staticmethod
    def _row_to_chunk(row: sqlite3.Row) -> KnowledgeChunk:
        return KnowledgeChunk(
            chunk_id=row["chunk_id"],
            source_uri=row["source_uri"],
            ordinal=int(row["ordinal"]),
            content=row["content"],
            content_hash=row["content_hash"],
            title=row["title"],
            experience_status=ExperienceStatus(row["experience_status"]),
            project=row["project"],
            topics=tuple(json.loads(row["topics_json"])),
            skills=tuple(json.loads(row["skills_json"])),
            metadata=json.loads(row["metadata_json"]),
        )


# Compatibility alias for the local-only implementation introduced by the first feature.
SQLiteLocalStore = SQLiteKnowledgeStore
