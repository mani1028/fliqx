from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from .detector import AutoDetector, DetectedFace, FaceDetector, BoundingBox

try:  # optional dependency
    import onnxruntime as ort  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    ort = None


class ScrfdOnnxDetector(FaceDetector):
    def __init__(self, model_path: str | Path | None = None, device: str = "auto", input_size: int = 640, **_) -> None:
        self.input_size = int(input_size)
        self.model_path = Path(model_path) if model_path is not None else None
        self._fallback = AutoDetector(min_face_size=24)
        self._session = None
        if ort is None:
            return
        if self.model_path is None or not self.model_path.exists():
            # Do not raise here; allow fallback to be used
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

    def detect(self, image: np.ndarray) -> list[DetectedFace]:
        if self._session is None:
            return self._fallback.detect(image)
        # Minimal preprocessing: resize to square input_size, keep aspect ratio by padding
        img = np.asarray(image)
        h, w = img.shape[:2]
        scale = float(self.input_size) / max(h, w)
        nh = int(round(h * scale))
        nw = int(round(w * scale))
        resized = np.zeros((self.input_size, self.input_size, 3), dtype=np.uint8)
        from ..utils import resize_nearest

        small = resize_nearest(img, (nh, nw))
        resized[:nh, :nw] = small if small.shape[2] == 3 else np.repeat(small, 3, axis=2)
        # Convert to float32 and CHW order
        inp = resized.astype(np.float32).transpose(2, 0, 1)[None, :, :, :]
        try:
            outputs = self._session.run(None, {self._session.get_inputs()[0].name: inp})
        except Exception:
            return self._fallback.detect(image)
        # Heuristic: if outputs resemble bounding boxes, attempt to decode; else fallback
        try:
            # outputs[0] often contains boxes; outputs[-1] may be scores. Use safe heuristics.
            boxes = np.asarray(outputs[0])
            scores = np.asarray(outputs[-1]) if len(outputs) > 1 else np.ones((boxes.shape[0],), dtype=np.float32)
            results: list[DetectedFace] = []
            for i in range(min(boxes.shape[0], scores.shape[0])):
                score = float(scores[i].max() if scores.ndim > 1 else scores[i])
                bx = boxes[i]
                # bx may be [x1,y1,x2,y2] but scaled to input_size
                x1, y1, x2, y2 = float(bx[0]), float(bx[1]), float(bx[2]), float(bx[3])
                # scale back to original image size
                x1 = int(max(0, min(w - 1, x1 / scale)))
                y1 = int(max(0, min(h - 1, y1 / scale)))
                x2 = int(max(0, min(w - 1, x2 / scale)))
                y2 = int(max(0, min(h - 1, y2 / scale)))
                bbox = BoundingBox(x=x1, y=y1, width=max(1, x2 - x1), height=max(1, y2 - y1))
                results.append(DetectedFace(bbox=bbox, score=score))
            if results:
                return results
        except Exception:
            pass
        return self._fallback.detect(image)


__all__ = ["ScrfdOnnxDetector"]
