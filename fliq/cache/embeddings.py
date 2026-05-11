from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..utils import image_fingerprint
from .memory import ThreadSafeTTLCache


@dataclass(slots=True)
class CachedEmbedding:
    embedding: np.ndarray
    metadata: dict[str, Any] = field(default_factory=dict)


class EmbeddingCache:
    def __init__(self, max_size: int = 1024, ttl_seconds: float | None = 300.0) -> None:
        self._cache = ThreadSafeTTLCache[str, CachedEmbedding](max_size=max_size, ttl_seconds=ttl_seconds)

    def get(self, image: np.ndarray) -> np.ndarray | None:
        cached = self._cache.get(image_fingerprint(image))
        return None if cached is None else cached.embedding

    def set(self, image: np.ndarray, embedding: np.ndarray, metadata: dict[str, Any] | None = None) -> None:
        self._cache.set(image_fingerprint(image), CachedEmbedding(embedding=np.asarray(embedding, dtype=np.float32), metadata=metadata or {}))

    def clear(self) -> None:
        self._cache.clear()
