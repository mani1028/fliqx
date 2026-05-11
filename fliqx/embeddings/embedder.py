from __future__ import annotations

from typing import Protocol

import numpy as np

from ..utils import normalize_image, resize_nearest, to_grayscale


class FaceEmbedder(Protocol):
    dimension: int

    def embed(self, image: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def embed_batch(self, images: list[np.ndarray]) -> np.ndarray:
        raise NotImplementedError


class LightweightEmbedder:
    def __init__(self, dimension: int = 256) -> None:
        self.dimension = dimension
        self._grid = self._build_grid(dimension)

    def _build_grid(self, dimension: int) -> tuple[int, int]:
        side = int(np.sqrt(dimension))
        while side > 1 and dimension % side != 0:
            side -= 1
        return side, dimension // max(side, 1)

    def _vectorize(self, image: np.ndarray) -> np.ndarray:
        view = normalize_image(image)
        gray = to_grayscale(view.data)
        grid_h, grid_w = self._grid
        resized = resize_nearest(gray[:, :, None], (grid_h, grid_w))[:, :, 0].astype(np.float32)
        vector = resized.reshape(-1)
        if vector.size < self.dimension:
            vector = np.pad(vector, (0, self.dimension - vector.size))
        elif vector.size > self.dimension:
            vector = vector[: self.dimension]
        vector = vector - vector.mean()
        norm = np.linalg.norm(vector)
        if norm > 1e-12:
            vector = vector / norm
        return vector.astype(np.float32, copy=False)

    def embed(self, image: np.ndarray) -> np.ndarray:
        return self._vectorize(image)

    def embed_batch(self, images: list[np.ndarray]) -> np.ndarray:
        if not images:
            return np.empty((0, self.dimension), dtype=np.float32)
        return np.vstack([self._vectorize(image) for image in images])


class BuffaloEmbedder(LightweightEmbedder):
    def __init__(self, dimension: int = 256, model_name: str = "buffalo_l") -> None:
        super().__init__(dimension=dimension)
        self.model_name = model_name


class ArcFaceEmbedder(LightweightEmbedder):
    def __init__(self, dimension: int = 256, model_name: str = "arcface") -> None:
        super().__init__(dimension=dimension)
        self.model_name = model_name
