from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

from .similarity import cosine_similarity_matrix, l2_normalize, topk_indices
from .storage import read_array, read_json, write_array, write_json

try:  # pragma: no cover - optional dependency
    import faiss  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    faiss = None


@dataclass(slots=True)
class RecognitionMatch:
    user_id: str
    confidence: float
    distance: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    track_id: str | None = None
    unknown: bool = False


class VectorIndex:
    def add(self, user_id: str, embedding: np.ndarray, metadata: dict[str, Any] | None = None) -> None:
        raise NotImplementedError

    def add_batch(
        self,
        user_ids: Sequence[str],
        embeddings: np.ndarray,
        metadata: Sequence[dict[str, Any] | None] | None = None,
    ) -> None:
        raise NotImplementedError

    def search(self, embeddings: np.ndarray, top_k: int = 1) -> list[list[RecognitionMatch]]:
        raise NotImplementedError

    def remove_user(self, user_id: str) -> None:
        raise NotImplementedError

    def save(self, directory: str | Path) -> None:
        raise NotImplementedError

    @classmethod
    def load(cls, directory: str | Path) -> "VectorIndex":
        raise NotImplementedError


class FaissVectorIndex(VectorIndex):
    def __init__(self, dimension: int, use_ann: bool = True) -> None:
        self.dimension = dimension
        self.use_ann = use_ann and faiss is not None
        self._next_id = 1
        self._id_to_user: dict[int, str] = {}
        self._id_to_metadata: dict[int, dict[str, Any]] = {}
        self._embeddings = np.empty((0, dimension), dtype=np.float32)
        self._external_ids = np.empty((0,), dtype=np.int64)
        self._faiss_index = self._build_index()

    def _build_index(self):
        if faiss is None:
            return None
        index = faiss.IndexHNSWFlat(self.dimension, 32, faiss.METRIC_INNER_PRODUCT) if self.use_ann else faiss.IndexFlatIP(self.dimension)
        return faiss.IndexIDMap2(index)

    def _normalize(self, embedding: np.ndarray) -> np.ndarray:
        vector = np.asarray(embedding, dtype=np.float32).reshape(1, -1)
        if vector.shape[1] != self.dimension:
            raise ValueError(f"Expected embedding dimension {self.dimension}, got {vector.shape[1]}")
        return l2_normalize(vector, axis=1)

    def add(self, user_id: str, embedding: np.ndarray, metadata: dict[str, Any] | None = None) -> None:
        self.add_batch([user_id], np.asarray(embedding, dtype=np.float32).reshape(1, -1), [metadata or {}])

    def add_batch(
        self,
        user_ids: Sequence[str],
        embeddings: np.ndarray,
        metadata: Sequence[dict[str, Any] | None] | None = None,
    ) -> None:
        if len(user_ids) == 0:
            return
        normalized = l2_normalize(np.asarray(embeddings, dtype=np.float32), axis=1)
        if normalized.ndim != 2 or normalized.shape[1] != self.dimension:
            raise ValueError(f"Expected embeddings of shape (n, {self.dimension})")
        if metadata is None:
            metadata = [{} for _ in user_ids]
        if len(metadata) != len(user_ids):
            raise ValueError("metadata length must match user_ids length")
        new_ids = np.arange(self._next_id, self._next_id + len(user_ids), dtype=np.int64)
        self._next_id += len(user_ids)
        for external_id, user_id, meta, vector in zip(new_ids, user_ids, metadata, normalized, strict=True):
            self._id_to_user[int(external_id)] = user_id
            self._id_to_metadata[int(external_id)] = dict(meta or {})
        self._embeddings = np.vstack([self._embeddings, normalized]) if self._embeddings.size else normalized.copy()
        self._external_ids = np.concatenate([self._external_ids, new_ids]) if self._external_ids.size else new_ids.copy()
        if self._faiss_index is not None:
            self._faiss_index.add_with_ids(normalized, new_ids)

    def search(self, embeddings: np.ndarray, top_k: int = 1) -> list[list[RecognitionMatch]]:
        queries = np.asarray(embeddings, dtype=np.float32)
        if queries.size == 0:
            return []
        if queries.ndim == 1:
            queries = queries.reshape(1, -1)
        queries = l2_normalize(queries, axis=1)
        if self._embeddings.size == 0:
            return [[] for _ in range(queries.shape[0])]
        if self._faiss_index is not None:
            scores, ids = self._faiss_index.search(queries, min(top_k, len(self._external_ids)))
            return self._decode_search_results(scores, ids)
        scores = cosine_similarity_matrix(queries, self._embeddings)
        indices, ranked_scores = topk_indices(scores, top_k)
        results: list[list[RecognitionMatch]] = []
        for row_indices, row_scores in zip(indices, ranked_scores, strict=True):
            row_matches: list[RecognitionMatch] = []
            for vector_index, score in zip(row_indices, row_scores, strict=True):
                external_id = int(self._external_ids[int(vector_index)])
                row_matches.append(self._make_match(external_id, float(score)))
            results.append(row_matches)
        return results

    def _decode_search_results(self, scores: np.ndarray, ids: np.ndarray) -> list[list[RecognitionMatch]]:
        results: list[list[RecognitionMatch]] = []
        for row_scores, row_ids in zip(scores, ids, strict=True):
            row_matches: list[RecognitionMatch] = []
            for score, external_id in zip(row_scores, row_ids, strict=True):
                if int(external_id) == -1:
                    continue
                row_matches.append(self._make_match(int(external_id), float(score)))
            results.append(row_matches)
        return results

    def _make_match(self, external_id: int, confidence: float) -> RecognitionMatch:
        user_id = self._id_to_user.get(external_id, "unknown")
        metadata = self._id_to_metadata.get(external_id, {})
        return RecognitionMatch(user_id=user_id, confidence=confidence, distance=1.0 - confidence, metadata=dict(metadata))

    def remove_user(self, user_id: str) -> None:
        removed_ids = {int(external_id) for external_id in self._external_ids if self._id_to_user[int(external_id)] == user_id}
        keep_mask = np.array([int(external_id) not in removed_ids for external_id in self._external_ids], dtype=bool)
        self._embeddings = self._embeddings[keep_mask]
        self._external_ids = self._external_ids[keep_mask]
        self._id_to_user = {external_id: name for external_id, name in self._id_to_user.items() if external_id not in removed_ids}
        self._id_to_metadata = {external_id: meta for external_id, meta in self._id_to_metadata.items() if external_id not in removed_ids}
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        if faiss is None:
            self._faiss_index = None
            return
        self._faiss_index = self._build_index()
        if self._embeddings.size:
            self._faiss_index.add_with_ids(self._embeddings, self._external_ids)

    def save(self, directory: str | Path) -> None:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        write_json(path / "meta.json", {"dimension": self.dimension, "next_id": self._next_id, "use_ann": self.use_ann})
        write_json(path / "users.json", {str(external_id): user_id for external_id, user_id in self._id_to_user.items()})
        write_json(path / "metadata.json", {str(external_id): meta for external_id, meta in self._id_to_metadata.items()})
        write_array(path / "embeddings.npy", self._embeddings)
        write_array(path / "external_ids.npy", self._external_ids)
        if self._faiss_index is not None:
            faiss.write_index(self._faiss_index, str(path / "index.faiss"))

    @classmethod
    def load(cls, directory: str | Path) -> "FaissVectorIndex":
        path = Path(directory)
        meta = read_json(path / "meta.json", {})
        index = cls(int(meta.get("dimension", 0)), use_ann=bool(meta.get("use_ann", True)))
        index._next_id = int(meta.get("next_id", 1))
        index._id_to_user = {int(external_id): user_id for external_id, user_id in read_json(path / "users.json", {}).items()}
        index._id_to_metadata = {int(external_id): meta for external_id, meta in read_json(path / "metadata.json", {}).items()}
        embeddings_path = path / "embeddings.npy"
        ids_path = path / "external_ids.npy"
        if embeddings_path.exists() and ids_path.exists():
            index._embeddings = read_array(embeddings_path, mmap_mode="r")
            index._external_ids = read_array(ids_path, mmap_mode="r")
        index._faiss_index = None
        faiss_path = path / "index.faiss"
        if faiss is not None and faiss_path.exists():
            index._faiss_index = faiss.read_index(str(faiss_path))
        elif index._embeddings.size:
            index._rebuild_index()
        return index

    @property
    def size(self) -> int:
        return int(self._external_ids.shape[0])
