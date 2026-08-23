from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .chunking import chunk_document
from .embeddings import EmbeddingModel
from .manifest import ManifestValidationError, load_manifest, read_document_text
from .models import ManifestDocument, RefreshReport, SearchResult
from .store import SQLiteLocalStore


class LocalKnowledgeIndex:
    def __init__(
        self,
        corpus_root: str | Path,
        database_path: str | Path,
        embedder: EmbeddingModel,
    ) -> None:
        self.corpus_root = Path(corpus_root).expanduser().resolve()
        self.embedder = embedder
        self.store = SQLiteLocalStore(database_path)

    def refresh(self) -> RefreshReport:
        documents = load_manifest(self.corpus_root)
        config_reset = self.store.prepare_embedding_config(
            self.embedder.model_id,
            self.embedder.dimension,
        )

        indexed = 0
        reused = 0
        chunks_written = 0
        active_sources: set[str] = set()

        for document in documents:
            active_sources.add(document.source_uri)
            source_hash = hashlib.sha256(document.path.read_bytes()).hexdigest()
            manifest_hash = self._manifest_hash(document)
            state = self.store.get_document_state(document.source_uri)
            if (
                state is not None
                and state["source_hash"] == source_hash
                and state["manifest_hash"] == manifest_hash
                and state["embedding_model"] == self.embedder.model_id
                and int(state["embedding_dimension"]) == self.embedder.dimension
            ):
                reused += 1
                continue

            text = read_document_text(document)
            chunks = chunk_document(document, text)
            if not chunks:
                raise ManifestValidationError(
                    f"{document.source_uri}: source contains no indexable text"
                )
            vectors = self.embedder.embed_documents([chunk.content for chunk in chunks])
            self.store.replace_document(
                document,
                source_hash=source_hash,
                manifest_hash=manifest_hash,
                chunks=chunks,
                vectors=vectors,
                model_id=self.embedder.model_id,
                dimension=self.embedder.dimension,
            )
            indexed += 1
            chunks_written += len(chunks)

        stale_sources = self.store.list_source_uris() - active_sources
        for source_uri in stale_sources:
            self.store.delete_document(source_uri)

        return RefreshReport(
            indexed=indexed,
            reused=reused,
            removed=len(stale_sources),
            chunks_written=chunks_written,
            embedding_config_reset=config_reset,
        )

    def query(self, text: str, top_k: int = 5) -> list[SearchResult]:
        if not text.strip():
            return []
        return self.store.search(self.embedder.embed_query(text), top_k=top_k)

    @staticmethod
    def _manifest_hash(document: ManifestDocument) -> str:
        payload = {
            "source_uri": document.source_uri,
            "title": document.title,
            "experience_status": document.experience_status.value,
            "project": document.project,
            "topics": document.topics,
            "skills": document.skills,
            "metadata": document.metadata,
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
