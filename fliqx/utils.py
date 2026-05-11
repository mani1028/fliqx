from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(slots=True)
class ImageView:
    data: np.ndarray
    height: int
    width: int
    channels: int


def as_uint8_image(image: Any) -> np.ndarray:
    array = np.asarray(image)
    if array.ndim == 2:
        array = array[:, :, None]
    if array.ndim != 3:
        raise ValueError("Expected an image array with 2 or 3 dimensions")
    if array.dtype != np.uint8:
        array = np.clip(array, 0, 255).astype(np.uint8, copy=False)
    return np.ascontiguousarray(array)


def normalize_image(image: Any) -> ImageView:
    array = as_uint8_image(image)
    height, width, channels = array.shape
    return ImageView(data=array, height=height, width=width, channels=channels)


def image_fingerprint(image: Any) -> str:
    array = as_uint8_image(image)
    digest = hashlib.sha1(array.tobytes()).hexdigest()
    return digest


def resize_nearest(image: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    target_height, target_width = size
    if image.ndim == 2:
        image = image[:, :, None]
    height, width, channels = image.shape
    if height == target_height and width == target_width:
        return image.copy()
    row_idx = np.linspace(0, height - 1, target_height).round().astype(np.int64)
    col_idx = np.linspace(0, width - 1, target_width).round().astype(np.int64)
    return image[row_idx][:, col_idx]


def to_grayscale(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2 or image.shape[2] == 1:
        return image.reshape(image.shape[0], image.shape[1])
    rgb = image[:, :, :3].astype(np.float32)
    gray = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    return gray.astype(np.uint8)


def safe_mean(values: np.ndarray, axis: int | None = None) -> np.ndarray:
    if values.size == 0:
        return np.array(0.0, dtype=np.float32)
    return np.mean(values, axis=axis)
