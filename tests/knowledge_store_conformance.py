from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod

import pytest

from interview_copilot.knowledge import (
    ChunkWrite,
    CollectionSpec,
    EmbeddingCompatibilityError,
    ExperienceStatus,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeStore,
    QueryRequest,
)


def _document(source_uri: str, *, status: ExperienceStatus) -> KnowledgeDocument:
    return KnowledgeDocument(
        source_uri=source_uri,
        title=source_uri,
        source_hash=hashlib.sha256(source_uri.encode()).hexdigest(),
        manifest_hash=hashlib.sha256(f"manifest:{source_uri}".encode()).hexdigest(),
        experience_status=status,
        project="project-a",
        topics=("architecture",),
        skills=("python",),
        metadata={"fixture": True},
    )


def _write(document: KnowledgeDocument, chunk_id: str, embedding: tuple[float, ...]) -> ChunkWrite:
    content = f"content for {chunk_id}"
    return ChunkWrite(
        chunk=KnowledgeChunk(
            chunk_id=chunk_id,
            source_uri=document.source_uri,
            ordinal=0,
            content=content,
            content_hash=hashlib.sha256(content.encode()).hexdigest(),
            title=document.title,
            experience_status=document.experience_status,
            project=document.project,
            topics=document.topics,
            skills=document.skills,
            metadata=dict(document.metadata),
        ),
        embedding=embedding,
    )


class KnowledgeStoreConformanceTests(ABC):
    @abstractmethod
    def make_store(self, tmp_path) -> KnowledgeStore:
        raise NotImplementedError

    def test_health_stats_and_protocol_shape(self, tmp_path):
        store = self.make_store(tmp_path)
        assert isinstance(store, KnowledgeStore)
        assert store.health().healthy is True
        assert store.stats().collections == 0

        created = store.ensure_collection(CollectionSpec("career", "fixture-v1", 3))
        assert created.created is True
        assert created.rebuilt is False
        assert store.stats().collections == 1

    def test_incompatible_collection_requires_explicit_rebuild(self, tmp_path):
        store = self.make_store(tmp_path)
        store.ensure_collection(CollectionSpec("career", "fixture-v1", 3))

        with pytest.raises(EmbeddingCompatibilityError):
            store.ensure_collection(CollectionSpec("career", "fixture-v2", 3))

        rebuilt = store.ensure_collection(
            CollectionSpec("career", "fixture-v2", 3),
            rebuild_if_incompatible=True,
        )
        assert rebuilt.rebuilt is True

    def test_atomic_document_chunk_replacement_and_chunk_lookup(self, tmp_path):
        store = self.make_store(tmp_path)
        store.ensure_collection(CollectionSpec("career", "fixture-v1", 3))
        document = _document("project.md", status=ExperienceStatus.IMPLEMENTED)
        first = _write(document, "chunk-1", (1.0, 0.0, 0.0))
        second = _write(document, "chunk-2", (0.0, 1.0, 0.0))

        store.replace_document_chunks("career", document, [first])
        assert store.get_chunk("career", "chunk-1") == first.chunk
        assert store.stats(["career"]).chunks == 1

        store.replace_document_chunks("career", document, [second])
        assert store.get_chunk("career", "chunk-1") is None
        assert store.get_chunk("career", "chunk-2") == second.chunk
        assert store.stats(["career"]).chunks == 1

    def test_upsert_document_and_delete_document(self, tmp_path):
        store = self.make_store(tmp_path)
        store.ensure_collection(CollectionSpec("career", "fixture-v1", 3))
        document = _document("project.md", status=ExperienceStatus.IMPLEMENTED)

        store.upsert_document("career", document)
        state = store.get_document_state("career", document.source_uri)
        assert state is not None
        assert state.source_hash == document.source_hash
        assert store.list_source_uris("career") == {document.source_uri}

        store.delete_document("career", document.source_uri)
        assert store.get_document_state("career", document.source_uri) is None

    def test_query_is_explicitly_scoped_to_allowed_collections(self, tmp_path):
        store = self.make_store(tmp_path)
        for collection in ("career", "target-role"):
            store.ensure_collection(CollectionSpec(collection, "fixture-v1", 3))

        career_document = _document("career.md", status=ExperienceStatus.IMPLEMENTED)
        target_document = _document("target.md", status=ExperienceStatus.HYPOTHETICAL)
        store.replace_document_chunks(
            "career",
            career_document,
            [_write(career_document, "career-chunk", (1.0, 0.0, 0.0))],
        )
        store.replace_document_chunks(
            "target-role",
            target_document,
            [_write(target_document, "target-chunk", (1.0, 0.0, 0.0))],
        )

        career_results = store.query(
            QueryRequest(
                collections=("career",),
                embedding_model="fixture-v1",
                embedding=(1.0, 0.0, 0.0),
                top_k=5,
            )
        )
        assert {result.collection for result in career_results} == {"career"}
        assert {result.chunk.source_uri for result in career_results} == {"career.md"}

        target_results = store.query(
            QueryRequest(
                collections=("target-role",),
                embedding_model="fixture-v1",
                embedding=(1.0, 0.0, 0.0),
                top_k=5,
            )
        )
        assert {result.collection for result in target_results} == {"target-role"}
        assert {result.chunk.source_uri for result in target_results} == {"target.md"}

    def test_query_rejects_embedding_model_or_dimension_mismatch(self, tmp_path):
        store = self.make_store(tmp_path)
        store.ensure_collection(CollectionSpec("career", "fixture-v1", 3))

        with pytest.raises(EmbeddingCompatibilityError):
            store.query(
                QueryRequest(
                    collections=("career",),
                    embedding_model="fixture-v2",
                    embedding=(1.0, 0.0, 0.0),
                )
            )

        with pytest.raises(EmbeddingCompatibilityError):
            store.query(
                QueryRequest(
                    collections=("career",),
                    embedding_model="fixture-v1",
                    embedding=(1.0, 0.0),
                )
            )
