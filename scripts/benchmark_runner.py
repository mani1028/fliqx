from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from fliq import Fliq
from fliq.benchmarks import benchmark_classroom_load, benchmark_recognition


def run_loop(engine: Fliq, image: np.ndarray, iterations: int = 50) -> dict[str, object]:
    result = benchmark_recognition(engine, image, iterations=iterations)
    return result.to_dict()


def run_load(engine: Fliq, classroom_count: int = 3, frames_per_classroom: int = 12) -> dict[str, object]:
    classrooms = {
        f"class-{index}": [
            np.random.default_rng(index * 100 + frame).integers(0, 255, size=(128, 128, 3), dtype=np.uint8)
            for frame in range(frames_per_classroom)
        ]
        for index in range(classroom_count)
    }
    result = benchmark_classroom_load(engine, classrooms, max_workers=min(4, classroom_count))
    return result.to_dict()


def main() -> None:
    engine = Fliq(warmup=True, detector="scrfd", embedder="buffalo", tracking=False)
    image = np.random.default_rng(1).integers(0, 255, size=(128, 128, 3), dtype=np.uint8)
    stats = {
        "single_image": run_loop(engine, image, iterations=10),
        "multi_classroom": run_load(engine, classroom_count=3, frames_per_classroom=8),
    }
    out = Path("benchmark_result.json")
    out.write_text(json.dumps(stats, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(stats, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
