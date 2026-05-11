from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_array(path: Path, array: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, array)


def read_array(path: Path, mmap_mode: str | None = None) -> np.ndarray:
    return np.load(path, mmap_mode=mmap_mode)
