from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from .embedder import LightweightEmbedder

try:  # optional dependency
    import onnxruntime as ort  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    ort = None


class BuffaloOnnxEmbedder(LightweightEmbedder):
    def __init__(self, model_path: str | Path | None = None, dimension: int = 512, device: str = "auto", **_) -> None:
        super().__init__(dimension=dimension)
        self.model_path = Path(model_path) if model_path is not None else None
        self._session = None
        if ort is None:
            return
        if self.model_path is None or not self.model_path.exists():
            return
        providers = ["CPUExecutionProvider"]
        try:
            if device.lower() in ("cuda", "gpu"):
                providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        except Exception:
            pass
        try:
            self._session = ort.InferenceSession(str(self.model_path), providers=providers)
        except Exception:
            self._session = None

    def embed(self, image: np.ndarray) -> np.ndarray:
        if self._session is None:
            return super().embed(image)
        img = np.asarray(image).astype(np.float32)
        if img.ndim == 2:
            img = np.repeat(img[:, :, None], 3, axis=2)
        inp = img.transpose(2, 0, 1)[None, :, :, :].astype(np.float32)
        try:
            out = self._session.run(None, {self._session.get_inputs()[0].name: inp})
            emb = np.asarray(out[0]).reshape(-1)[: self.dimension].astype(np.float32)
            # L2 normalize
            norm = np.linalg.norm(emb)
            if norm > 1e-12:
                emb = emb / norm
            return emb
        except Exception:
            return super().embed(image)

    def embed_batch(self, images: list[np.ndarray]) -> np.ndarray:
        if self._session is None:
            return super().embed_batch(images)
        batch = [np.asarray(img).astype(np.float32) for img in images]
        # Very small batch path: call embed repeatedly
        return np.vstack([self.embed(img) for img in batch])


__all__ = ["BuffaloOnnxEmbedder"]
