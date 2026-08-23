from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from .models import ExperienceStatus, KnowledgeChunk, ManifestDocument, SearchResult


class SQLiteLocalStore:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).expanduser()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS index_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS documents (
                    source_uri TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    source_hash TEXT NOT NULL,
                    manifest_hash TEXT NOT NULL,
                    experience_status TEXT NOT NULL,
                    project TEXT,
                    topics_json TEXT NOT NULL,
                    skills_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    embedding_model TEXT NOT NULL,
                    embedding_dimension INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id TEXT PRIMARY KEY,
                    source_uri TEXT NOT NULL REFERENCES documents(source_uri) ON DELETE CASCADE,
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
                    UNIQUE(source_uri, ordinal)
                );

                CREATE INDEX IF NOT EXISTS idx_chunks_source_uri ON chunks(source_uri);
                """
            )

    def prepare_embedding_config(self, model_id: str, dimension: int) -> bool:
        reset = False
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT key, value FROM index_metadata WHERE key IN ('embedding_model', 'embedding_dimension')"
            ).fetchall()
            current = {row["key"]: row["value"] for row in rows}
            current_model = current.get("embedding_model")
            current_dimension = current.get("embedding_dimension")
            if current_model is not None and (
                current_model != model_id or current_dimension != str(dimension)
            ):
                connection.execute("DELETE FROM chunks")
                connection.execute("DELETE FROM documents")
                reset = True

            connection.execute(
                "INSERT INTO index_metadata(key, value) VALUES('embedding_model', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (model_id,),
            )
            connection.execute(
                "INSERT INTO index_metadata(key, value) VALUES('embedding_dimension', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (str(dimension),),
            )
        return reset

    def get_document_state(self, source_uri: str) -> sqlite3.Row | None:
        with self._connect() as connection:
            return connection.execute(
                """
                SELECT source_hash, manifest_hash, embedding_model, embedding_dimension
                FROM documents WHERE source_uri = ?
                """,
                (source_uri,),
            ).fetchone()

    def list_source_uris(self) -> set[str]:
        with self._connect() as connection:
            return {
                row["source_uri"]
                for row in connection.execute("SELECT source_uri FROM documents").fetchall()
            }

    def replace_document(
        self,
        document: ManifestDocument,
        *,
        source_hash: str,
        manifest_hash: str,
        chunks: Sequence[KnowledgeChunk],
        vectors: np.ndarray,
        model_id: str,
        dimension: int,
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunk/vector count mismatch")
        if vectors.ndim != 2 or (len(vectors) and vectors.shape[1] != dimension):
            raise ValueError("embedding dimension mismatch")

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO documents(
                    source_uri, title, source_hash, manifest_hash, experience_status,
                    project, topics_json, skills_json, metadata_json,
                    embedding_model, embedding_dimension
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_uri) DO UPDATE SET
                    title = excluded.title,
                    source_hash = excluded.source_hash,
                    manifest_hash = excluded.manifest_hash,
                    experience_status = excluded.experience_status,
                    project = excluded.project,
                    topics_json = excluded.topics_json,
                    skills_json = excluded.skills_json,
                    metadata_json = excluded.metadata_json,
                    embedding_model = excluded.embedding_model,
                    embedding_dimension = excluded.embedding_dimension
                """,
                (
                    document.source_uri,
                    document.title,
                    source_hash,
                    manifest_hash,
                    document.experience_status.value,
                    document.project,
                    json.dumps(document.topics),
                    json.dumps(document.skills),
                    json.dumps(document.metadata, sort_keys=True),
                    model_id,
                    dimension,
                ),
            )
            connection.execute("DELETE FROM chunks WHERE source_uri = ?", (document.source_uri,))
            connection.executemany(
                """
                INSERT INTO chunks(
                    chunk_id, source_uri, ordinal, content, content_hash, title,
                    experience_status, project, topics_json, skills_json, metadata_json,
                    embedding, embedding_dimension
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        chunk.chunk_id,
                        chunk.source_uri,
                        chunk.ordinal,
                        chunk.content,
                        chunk.content_hash,
                        chunk.title,
                        chunk.experience_status.value,
                        chunk.project,
                        json.dumps(chunk.topics),
                        json.dumps(chunk.skills),
                        json.dumps(chunk.metadata, sort_keys=True),
                        np.asarray(vector, dtype=np.float32).tobytes(),
                        dimension,
                    )
                    for chunk, vector in zip(chunks, vectors, strict=True)
                ],
            )

    def delete_document(self, source_uri: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM documents WHERE source_uri = ?", (source_uri,))

    def fetch_chunks(self, source_uri: str | None = None) -> list[KnowledgeChunk]:
        sql = (
            "SELECT chunk_id, source_uri, ordinal, content, content_hash, title, "
            "experience_status, project, topics_json, skills_json, metadata_json "
            "FROM chunks"
        )
        params: tuple[object, ...] = ()
        if source_uri is not None:
            sql += " WHERE source_uri = ?"
            params = (source_uri,)
        sql += " ORDER BY source_uri, ordinal"

        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()

        return [self._row_to_chunk(row) for row in rows]

    def search(self, query_vector: np.ndarray, top_k: int = 5) -> list[SearchResult]:
        if top_k <= 0:
            return []

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT chunk_id, source_uri, ordinal, content, content_hash, title,
                       experience_status, project, topics_json, skills_json, metadata_json,
                       embedding, embedding_dimension
                FROM chunks
                """
            ).fetchall()

        if not rows:
            return []

        dimension = int(rows[0]["embedding_dimension"])
        query = np.asarray(query_vector, dtype=np.float32).reshape(-1)
        if query.shape[0] != dimension:
            raise ValueError(
                f"Query embedding dimension {query.shape[0]} does not match index dimension {dimension}"
            )

        matrix = np.stack(
            [np.frombuffer(row["embedding"], dtype=np.float32, count=dimension) for row in rows]
        )
        matrix_norms = np.linalg.norm(matrix, axis=1)
        query_norm = float(np.linalg.norm(query))
        if query_norm == 0:
            scores = np.zeros(len(rows), dtype=np.float32)
        else:
            safe_norms = np.where(matrix_norms == 0, 1.0, matrix_norms)
            scores = (matrix @ query) / (safe_norms * query_norm)

        ranked = np.argsort(-scores, kind="stable")[: min(top_k, len(rows))]
        return [
            SearchResult(score=float(scores[index]), chunk=self._row_to_chunk(rows[index]))
            for index in ranked
        ]

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
