from __future__ import annotations

import hashlib
import os

import pytest

from interview_copilot.knowledge import PostgresKnowledgeStore
from tests.knowledge_store_conformance import KnowledgeStoreConformanceTests

_TEST_DATABASE_URL = os.getenv("INTERVIEW_COPILOT_TEST_PG_URL")
_TEST_SSLMODE = os.getenv("INTERVIEW_COPILOT_TEST_PG_SSLMODE")


def _test_schema(tmp_path) -> str:
    digest = hashlib.sha256(str(tmp_path).encode()).hexdigest()[:16]
    return f"interview_copilot_test_{digest}"


def test_postgres_provider_remains_optional_without_database_configuration(monkeypatch):
    monkeypatch.delenv("INTERVIEW_COPILOT_KB_DATABASE_URL", raising=False)
    monkeypatch.delenv("INTERVIEW_COPILOT_KB_SSLMODE", raising=False)

    store = PostgresKnowledgeStore()
    health = store.health()

    assert health.healthy is False
    assert health.provider == "postgres-pgvector"
    assert health.detail == "database URL is not configured"


def test_postgres_provider_rejects_unknown_tls_mode():
    with pytest.raises(ValueError, match="sslmode"):
        PostgresKnowledgeStore("postgresql://example.invalid/db", sslmode="not-a-mode")


def test_postgres_health_never_exposes_connection_secret(monkeypatch):
    secret = "do-not-expose-this-password"
    store = PostgresKnowledgeStore(f"postgresql://user:{secret}@db.example.invalid/copilot")

    def fail_bootstrap() -> None:
        raise RuntimeError(f"failed while connecting with {store.database_url}")

    monkeypatch.setattr(store, "_bootstrap", fail_bootstrap)
    health = store.health()

    assert health.healthy is False
    assert secret not in (health.detail or "")
    assert store.database_url not in (health.detail or "")


@pytest.mark.skipif(
    not _TEST_DATABASE_URL,
    reason="INTERVIEW_COPILOT_TEST_PG_URL is not configured",
)
class TestPgvectorKnowledgeStore(KnowledgeStoreConformanceTests):
    def make_store(self, tmp_path):
        return PostgresKnowledgeStore(
            _TEST_DATABASE_URL,
            sslmode=_TEST_SSLMODE,
            schema=_test_schema(tmp_path),
        )

    def test_health_validates_pgvector_and_schema_version(self, tmp_path):
        store = self.make_store(tmp_path)
        health = store.health()

        assert health.healthy is True
        assert health.detail is not None
        assert "schema_version=1" in health.detail
        assert "vector=" in health.detail
