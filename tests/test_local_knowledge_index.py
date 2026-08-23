from __future__ import annotations

import json
import sqlite3
import sys
import types

import numpy as np
import pytest

from interview_copilot.knowledge import (
    DeterministicHashEmbedding,
    ExperienceStatus,
    FastEmbedEmbedding,
    LocalKnowledgeIndex,
    ManifestValidationError,
    SQLiteKnowledgeStore,
)
from interview_copilot.knowledge.chunking import chunk_document
from interview_copilot.knowledge.manifest import load_manifest, read_document_text


class CountingEmbedding(DeterministicHashEmbedding):
    def __init__(self, *, model_id: str = "counting-v1") -> None:
        super().__init__(dimension=64, model_id=model_id)
        self.documents_embedded = 0

    def embed_documents(self, texts):
        self.documents_embedded += len(texts)
        return super().embed_documents(texts)


def _write_manifest(root, documents):
    (root / "corpus.json").write_text(
        json.dumps({"documents": documents}, indent=2),
        encoding="utf-8",
    )


def _build_corpus(tmp_path):
    root = tmp_path / "corpus"
    root.mkdir()
    (root / "warehouse.md").write_text(
        "# Multi-tenant warehouse\n\nBuilt Snowflake architecture and dbt models for tenant analytics.\n\n"
        "Designed incremental processing for large financial facts.",
        encoding="utf-8",
    )
    (root / "future.md").write_text(
        "# Role idea\n\nUse retrieval to compare proposed legal documents against internal standards.",
        encoding="utf-8",
    )
    documents = [
        {
            "path": "warehouse.md",
            "title": "Warehouse project",
            "project": "warehouse",
            "experience_status": "implemented",
            "topics": ["architecture", "analytics"],
            "skills": ["Snowflake", "dbt"],
        },
        {
            "path": "future.md",
            "title": "Role application idea",
            "experience_status": "hypothetical",
            "topics": ["retrieval", "legal"],
        },
    ]
    _write_manifest(root, documents)
    return root, documents


def _build_index(root, database, embedder, *, collection="career"):
    return LocalKnowledgeIndex(
        root,
        SQLiteKnowledgeStore(database),
        embedder,
        collection=collection,
    )


def test_manifest_requires_explicit_experience_status(tmp_path):
    root = tmp_path / "corpus"
    root.mkdir()
    (root / "project.md").write_text("Implemented a thing.", encoding="utf-8")
    _write_manifest(root, [{"path": "project.md", "title": "Project"}])

    with pytest.raises(ManifestValidationError, match="experience_status"):
        load_manifest(root)


def test_manifest_rejects_paths_outside_selected_corpus(tmp_path):
    root = tmp_path / "corpus"
    root.mkdir()
    (tmp_path / "outside.md").write_text("private", encoding="utf-8")
    _write_manifest(
        root,
        [{"path": "../outside.md", "experience_status": "implemented"}],
    )

    with pytest.raises(ManifestValidationError, match="escapes"):
        load_manifest(root)


def test_chunk_ids_are_stable_for_unchanged_content(tmp_path):
    root, _ = _build_corpus(tmp_path)
    document = load_manifest(root)[0]
    text = read_document_text(document)

    first = chunk_document(document, text)
    second = chunk_document(document, text)

    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]
    assert all(chunk.source_uri == "warehouse.md" for chunk in first)
    assert all(chunk.experience_status is ExperienceStatus.IMPLEMENTED for chunk in first)


def test_incremental_refresh_reuses_unchanged_documents_and_removes_deleted_sources(tmp_path):
    root, documents = _build_corpus(tmp_path)
    embedder = CountingEmbedding()
    index = _build_index(root, tmp_path / "knowledge.sqlite3", embedder)

    first = index.refresh()
    first_embed_count = embedder.documents_embedded
    assert first.indexed == 2
    assert first.reused == 0
    assert first_embed_count > 0

    second = index.refresh()
    assert second.indexed == 0
    assert second.reused == 2
    assert embedder.documents_embedded == first_embed_count

    (root / "warehouse.md").write_text(
        "# Multi-tenant warehouse\n\nBuilt Snowflake architecture and dbt models for tenant analytics.\n\n"
        "Added deterministic validation and incremental processing.",
        encoding="utf-8",
    )
    third = index.refresh()
    assert third.indexed == 1
    assert third.reused == 1
    assert embedder.documents_embedded > first_embed_count

    (root / "future.md").unlink()
    _write_manifest(root, [documents[0]])
    fourth = index.refresh()
    assert fourth.removed == 1
    assert {chunk.source_uri for chunk in index.store.fetch_chunks("career")} == {"warehouse.md"}


def test_retrieval_preserves_provenance_truth_status_and_collection(tmp_path):
    root, _ = _build_corpus(tmp_path)
    index = _build_index(
        root,
        tmp_path / "knowledge.sqlite3",
        DeterministicHashEmbedding(),
    )
    index.refresh()

    warehouse = index.query("Snowflake architecture dbt", top_k=2)
    assert warehouse
    assert warehouse[0].collection == "career"
    assert warehouse[0].chunk.source_uri == "warehouse.md"
    assert warehouse[0].chunk.experience_status is ExperienceStatus.IMPLEMENTED
    assert "Snowflake" in warehouse[0].chunk.skills

    hypothetical = index.query("legal retrieval internal standards", top_k=2)
    assert hypothetical
    assert hypothetical[0].chunk.source_uri == "future.md"
    assert hypothetical[0].chunk.experience_status is ExperienceStatus.HYPOTHETICAL


def test_embedding_configuration_change_explicitly_rebuilds_index_collection(tmp_path):
    root, _ = _build_corpus(tmp_path)
    database = tmp_path / "knowledge.sqlite3"

    first = _build_index(root, database, CountingEmbedding(model_id="model-v1"))
    assert first.refresh().embedding_config_reset is False

    second_embedder = CountingEmbedding(model_id="model-v2")
    second = _build_index(root, database, second_embedder)
    report = second.refresh()

    assert report.embedding_config_reset is True
    assert report.indexed == 2
    assert report.reused == 0
    assert second_embedder.documents_embedded > 0


def test_provider_initialization_rebuilds_legacy_unscoped_cache(tmp_path):
    database = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE documents(source_uri TEXT PRIMARY KEY);
            CREATE TABLE chunks(chunk_id TEXT PRIMARY KEY);
            CREATE TABLE index_metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """
        )

    store = SQLiteKnowledgeStore(database)
    assert store.stats().collections == 0

    with sqlite3.connect(database) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(documents)").fetchall()
        }
    assert "collection" in columns


def test_fastembed_adapter_can_require_cached_files_only(monkeypatch, tmp_path):
    captured = {}

    class FakeTextEmbedding:
        embedding_size = 3

        def __init__(self, **kwargs):
            captured.update(kwargs)

        def embed(self, documents):
            for _ in documents:
                yield np.array([1.0, 0.0, 0.0], dtype=np.float32)

        def query_embed(self, query):
            yield np.array([1.0, 0.0, 0.0], dtype=np.float32)

    monkeypatch.setitem(
        sys.modules,
        "fastembed",
        types.SimpleNamespace(TextEmbedding=FakeTextEmbedding),
    )

    adapter = FastEmbedEmbedding(
        cache_dir=tmp_path / "cache",
        local_files_only=True,
    )

    assert captured["local_files_only"] is True
    assert captured["model_name"] == "BAAI/bge-small-en-v1.5"
    assert adapter.dimension == 3
    assert adapter.embed_documents(["one"]).shape == (1, 3)
    assert adapter.embed_query("one").shape == (3,)
