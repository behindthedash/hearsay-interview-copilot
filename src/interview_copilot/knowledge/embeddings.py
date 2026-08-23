from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Protocol, Sequence

import numpy as np


class EmbeddingModel(Protocol):
    @property
    def model_id(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    def embed_documents(self, texts: Sequence[str]) -> np.ndarray: ...

    def embed_query(self, text: str) -> np.ndarray: ...


class FastEmbedEmbedding:
    """FastEmbed/ONNX adapter with an explicit offline-after-cache mode."""

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-en-v1.5",
        *,
        cache_dir: str | Path | None = None,
        local_files_only: bool = False,
    ) -> None:
        try:
            from fastembed import TextEmbedding
        except ImportError as exc:
            raise RuntimeError(
                "FastEmbed is not installed. Install the 'embeddings' extra to use the production embedding adapter."
            ) from exc

        kwargs: dict[str, object] = {
            "model_name": model_name,
            "local_files_only": local_files_only,
        }
        if cache_dir is not None:
            kwargs["cache_dir"] = str(Path(cache_dir).expanduser())

        self._model_name = model_name
        self._model = TextEmbedding(**kwargs)
        self._dimension = int(self._model.embedding_size)

    @property
    def model_id(self) -> str:
        return f"fastembed:{self._model_name}"

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_documents(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)
        return np.asarray(list(self._model.embed(list(texts))), dtype=np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        return np.asarray(next(iter(self._model.query_embed(text))), dtype=np.float32)


class DeterministicHashEmbedding:
    """Small deterministic lexical embedding used for tests and local development."""

    _token_pattern = re.compile(r"[A-Za-z0-9_+#.-]+")

    def __init__(self, dimension: int = 64, model_id: str = "deterministic-hash-v1") -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self._dimension = dimension
        self._model_id = model_id

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def dimension(self) -> int:
        return self._dimension

    def _embed(self, text: str) -> np.ndarray:
        vector = np.zeros(self.dimension, dtype=np.float32)
        for token in self._token_pattern.findall(text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign
        norm = float(np.linalg.norm(vector))
        if norm:
            vector /= norm
        return vector

    def embed_documents(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)
        return np.stack([self._embed(text) for text in texts])

    def embed_query(self, text: str) -> np.ndarray:
        return self._embed(text)
