from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, TypeVar

R = TypeVar("R")


class AsyncWorkerPool:
    def __init__(self, max_workers: int | None = None) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="fliq-async")

    async def run(self, fn: Callable[..., R], *args: Any, **kwargs: Any) -> R:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, lambda: fn(*args, **kwargs))

    async def gather(self, *calls: tuple[Callable[..., R], tuple[Any, ...], dict[str, Any]]) -> list[R]:
        tasks = [self.run(fn, *args, **kwargs) for fn, args, kwargs in calls]
        return await asyncio.gather(*tasks)

    def close(self) -> None:
        self._executor.shutdown(wait=True)
