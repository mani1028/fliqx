from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")
R = TypeVar("R")


class ThreadPoolManager:
    def __init__(self, max_workers: int | None = None, thread_name_prefix: str = "fliq") -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix=thread_name_prefix)

    def submit(self, fn: Callable[..., R], *args: object, **kwargs: object) -> Future[R]:
        return self._executor.submit(fn, *args, **kwargs)

    def map(self, fn: Callable[[T], R], items: Iterable[T]) -> list[R]:
        futures = [self._executor.submit(fn, item) for item in items]
        return [future.result() for future in as_completed(futures)]

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait)
