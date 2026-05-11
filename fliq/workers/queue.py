from __future__ import annotations

from queue import Empty, Full, Queue
from threading import Lock
from typing import Generic, TypeVar

T = TypeVar("T")


class BoundedQueue(Generic[T]):
    def __init__(self, max_size: int = 256) -> None:
        self._queue: Queue[T] = Queue(maxsize=max_size)
        self._lock = Lock()

    def put(self, item: T, drop_oldest: bool = True) -> bool:
        with self._lock:
            if self._queue.full() and drop_oldest:
                try:
                    self._queue.get_nowait()
                except Empty:
                    pass
            try:
                self._queue.put_nowait(item)
                return True
            except Full:
                return False

    def get(self, timeout: float | None = None) -> T:
        return self._queue.get(timeout=timeout)

    def empty(self) -> bool:
        return self._queue.empty()

    def qsize(self) -> int:
        return self._queue.qsize()
