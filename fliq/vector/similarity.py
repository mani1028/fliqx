from __future__ import annotations

from typing import Tuple

import numpy as np


def l2_normalize(vectors: np.ndarray, axis: int = 1, eps: float = 1e-12) -> np.ndarray:
    array = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(array, axis=axis, keepdims=True)
    norms = np.maximum(norms, eps)
    return array / norms


def cosine_similarity_matrix(queries: np.ndarray, gallery: np.ndarray) -> np.ndarray:
    if queries.size == 0 or gallery.size == 0:
        return np.empty((queries.shape[0], gallery.shape[0]), dtype=np.float32)
    normalized_queries = l2_normalize(queries, axis=1)
    normalized_gallery = l2_normalize(gallery, axis=1)
    return normalized_queries @ normalized_gallery.T


def topk_indices(scores: np.ndarray, k: int) -> Tuple[np.ndarray, np.ndarray]:
    if scores.ndim != 2:
        raise ValueError("scores must be a 2D array")
    if scores.shape[1] == 0:
        empty = np.empty((scores.shape[0], 0), dtype=np.int64)
        return empty, empty.astype(np.float32)
    k = max(1, min(k, scores.shape[1]))
    partition = np.argpartition(-scores, kth=k - 1, axis=1)[:, :k]
    row_indices = np.arange(scores.shape[0])[:, None]
    values = scores[row_indices, partition]
    order = np.argsort(-values, axis=1)
    sorted_indices = partition[row_indices, order]
    sorted_scores = scores[row_indices, sorted_indices]
    return sorted_indices, sorted_scores
