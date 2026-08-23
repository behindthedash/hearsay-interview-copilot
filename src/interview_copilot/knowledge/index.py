from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .chunking import chunk_document
from .embeddings import EmbeddingModel
from .manifest import ManifestValidationError, load_manifest, read_document_text
from .models import (
    ChunkWrite,
    CollectionSpec,
    KnowledgeDocument,
    ManifestDocument,
    QueryRequest,
    RefreshReport,
    SearchResult,
)
from .provider import KnowledgeStore


class LocalKnowledgeIndex:
    def __init__(
        self,
        corpus_root: str | Path,
        store: KnowledgeStore,
        embedder: EmbeddingModel,
        *,
        collection: str = "career",
    ) -> None:
        self.corpus_root = Path(corpus_root).expanduser().resolve()
        self.store = store
        self.embedder = embedder
        self.collection = collection

    def refresh(self) -> RefreshReport:
        documents = load_manifest(self.corpus_root)
        collection_result = self.store.ensure_collection(
            CollectionSpec(
                name=self.collection,
                embedding_model=self.embedder.model_id,
                embedding_dimension=self.embedder.dimension,
            ),
            rebuild_if_incompatible=True,
        )

        indexed = 0
        reused = 0
        chunks_written = 0
        active_sources: set[str] = set()

        for document in documents:
            active_sources.add(document.source_uri)
            source_hash = hashlib.sha256(document.path.read_bytes()).hexdigest()
            manifest_hash = self._manifest_hash(document)
            state = self.store.get_document_state(self.collection, document.source_uri)
            if (
                state is not None
                and state.source_hash == source_hash
                and state.manifest_hash == manifest_hash
                and state.embedding_model == self.embedder.model_id
                and state.embedding_dimension == self.embedder.dimension
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
            writes = [
                ChunkWrite(
                    chunk=chunk,
                    embedding=tuple(float(value) for value in vector),
                )
                for chunk, vector in zip(chunks, vectors, strict=True)
            ]
            self.store.replace_document_chunks(
                self.collection,
                KnowledgeDocument(
                    source_uri=document.source_uri,
                    title=document.title,
                    source_hash=source_hash,
                    manifest_hash=manifest_hash,
                    experience_status=document.experience_status,
                    project=document.project,
                    topics=document.topics,
                    skills=document.skills,
                    metadata=dict(document.metadata),
                ),
                writes,
            )
            indexed += 1
            chunks_written += len(chunks)

        stale_sources = self.store.list_source_uris(self.collection) - active_sources
        for source_uri in stale_sources:
            self.store.delete_document(self.collection, source_uri)

        return RefreshReport(
            indexed=indexed,
            reused=reused,
            removed=len(stale_sources),
            chunks_written=chunks_written,
            embedding_config_reset=collection_result.rebuilt,
        )

    def query(self, text: str, top_k: int = 5) -> list[SearchResult]:
        if not text.strip():
            return []
        query_vector = self.embedder.embed_query(text)
        return self.store.query(
            QueryRequest(
                collections=(self.collection,),
                embedding_model=self.embedder.model_id,
                embedding=tuple(float(value) for value in query_vector),
                top_k=top_k,
            )
        )

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
