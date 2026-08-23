from __future__ import annotations

from interview_copilot.knowledge import SQLiteKnowledgeStore
from tests.knowledge_store_conformance import KnowledgeStoreConformanceTests


class TestSQLiteKnowledgeStore(KnowledgeStoreConformanceTests):
    def make_store(self, tmp_path):
        return SQLiteKnowledgeStore(tmp_path / "knowledge.sqlite3")
