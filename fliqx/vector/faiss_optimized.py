from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Sequence

import numpy as np

try:  # optional dependency
    import faiss  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    faiss = None

from .faiss_index import RecognitionMatch
from .similarity import l2_normalize, cosine_similarity_matrix, topk_indices


@dataclass(slots=True)
class FaissOptimizedIndex:
    dimension: int
    index_type: str = "hnsw"  # or 'ivf'
    nlist: int = 128
    use_gpu: bool = False

    def __post_init__(self) -> None:
        self._ids: np.ndarray = np.empty((0,), dtype=np.int64)
        self._embeddings: np.ndarray = np.empty((0, self.dimension), dtype=np.float32)
        self._id_to_user: dict[int, str] = {}
        self._id_to_meta: dict[int, dict[str, Any]] = {}
        self._next_id = 1
        self._index = None
        if faiss is not None:
            self._build_index()

    def _build_index(self) -> None:
        if faiss is None:
            self._index = None
            return
        if self.index_type == "ivf":
            quant = faiss.IndexFlatL2(self.dimension)
            index = faiss.IndexIVFFlat(quant, self.dimension, max(1, int(self.nlist)), faiss.METRIC_L2)
        else:
            index = faiss.IndexHNSWFlat(self.dimension, 32, faiss.METRIC_INNER_PRODUCT)
        self._index = faiss.IndexIDMap2(index)
        if self._embeddings.size:
            self._index.add_with_ids(self._embeddings, self._ids)

    def add_batch(self, user_ids: Sequence[str], embeddings: np.ndarray, metadata: Sequence[dict[str, Any] | None] | None = None) -> None:
        normalized = l2_normalize(np.asarray(embeddings, dtype=np.float32), axis=1)
        new_ids = np.arange(self._next_id, self._next_id + len(user_ids), dtype=np.int64)
        self._next_id += len(user_ids)
        for nid, uid, meta in zip(new_ids, user_ids, metadata or [None] * len(user_ids)):
            self._id_to_user[int(nid)] = uid
            self._id_to_meta[int(nid)] = dict(meta or {})
        self._embeddings = np.vstack([self._embeddings, normalized]) if self._embeddings.size else normalized.copy()
        self._ids = np.concatenate([self._ids, new_ids]) if self._ids.size else new_ids.copy()
        if self._index is not None:
            self._index.add_with_ids(normalized, new_ids)

    def search(self, queries: np.ndarray, top_k: int = 1) -> List[List[RecognitionMatch]]:
        q = np.asarray(queries, dtype=np.float32)
        if q.ndim == 1:
            q = q.reshape(1, -1)
        q = l2_normalize(q, axis=1)
        if self._index is not None:
            scores, ids = self._index.search(q, min(top_k, int(self._ids.shape[0])))
            results: List[List[RecognitionMatch]] = []
            for row_scores, row_ids in zip(scores, ids):
                row: List[RecognitionMatch] = []
                for sc, rid in zip(row_scores, row_ids):
                    if int(rid) == -1:
                        continue
                    uid = self._id_to_user.get(int(rid), "unknown")
                    row.append(RecognitionMatch(user_id=uid, confidence=float(sc), distance=1.0 - float(sc), metadata=self._id_to_meta.get(int(rid), {})))
                results.append(row)
            return results
        # fallback: CPU brute-force cosine
        if self._embeddings.size == 0:
            return [[] for _ in range(q.shape[0])]
        scores = cosine_similarity_matrix(q, self._embeddings)
        indices, ranked_scores = topk_indices(scores, top_k)
        results: List[List[RecognitionMatch]] = []
        for row_idx, row_scores in zip(indices, ranked_scores):
            row: List[RecognitionMatch] = []
            for col_idx, sc in zip(row_idx, row_scores):
                external_id = int(self._ids[int(col_idx)])
                uid = self._id_to_user.get(external_id, "unknown")
                row.append(RecognitionMatch(user_id=uid, confidence=float(sc), distance=1.0 - float(sc), metadata=self._id_to_meta.get(external_id, {})))
            results.append(row)
        return results

    def save(self, directory: str | Path) -> None:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        np.save(path / "embeddings.npy", self._embeddings)
        np.save(path / "ids.npy", self._ids)
        # write mappings
        import json

        json.dump({str(k): v for k, v in self._id_to_user.items()}, open(path / "users.json", "w"))
        json.dump({str(k): v for k, v in self._id_to_meta.items()}, open(path / "meta.json", "w"))
        if faiss is not None and self._index is not None:
            try:
                faiss.write_index(self._index, str(path / "index.faiss"))
            except Exception:
                pass

    @classmethod
    def load(cls, directory: str | Path) -> "FaissOptimizedIndex":
        path = Path(directory)
        emb = np.load(path / "embeddings.npy") if (path / "embeddings.npy").exists() else np.empty((0, cls.dimension), dtype=np.float32)
        ids = np.load(path / "ids.npy") if (path / "ids.npy").exists() else np.empty((0,), dtype=np.int64)
        inst = cls(dimension=emb.shape[1] if emb.size else cls.dimension)
        inst._embeddings = emb
        inst._ids = ids
        import json

        try:
            users = json.load(open(path / "users.json"))
            inst._id_to_user = {int(k): v for k, v in users.items()}
        except Exception:
            inst._id_to_user = {}
        try:
            meta = json.load(open(path / "meta.json"))
            inst._id_to_meta = {int(k): v for k, v in meta.items()}
        except Exception:
            inst._id_to_meta = {}
        if faiss is not None and (path / "index.faiss").exists():
            try:
                inst._index = faiss.read_index(str(path / "index.faiss"))
            except Exception:
                inst._build_index()
        else:
            inst._build_index()
        return inst


__all__ = ["FaissOptimizedIndex"]
