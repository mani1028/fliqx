from __future__ import annotations

import cProfile
import pstats
from pathlib import Path
from typing import Callable, TypeVar

T = TypeVar("T")


def profile_call(fn: Callable[[], T], output_path: str | Path | None = None) -> T:
    profiler = cProfile.Profile()
    result = profiler.runcall(fn)
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            stats = pstats.Stats(profiler, stream=handle)
            stats.sort_stats("cumtime")
            stats.print_stats(50)
    return result
