from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from threading import RLock
from time import monotonic
from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


@dataclass(slots=True)
class CacheEntry(Generic[V]):
    value: V
    expires_at: float | None = None

    def is_expired(self) -> bool:
        return self.expires_at is not None and monotonic() >= self.expires_at


class ThreadSafeTTLCache(Generic[K, V]):
    def __init__(self, max_size: int = 1024, ttl_seconds: float | None = 60.0) -> None:
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._lock = RLock()
        self._store: OrderedDict[K, CacheEntry[V]] = OrderedDict()

    def get(self, key: K, default: V | None = None) -> V | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return default
            if entry.is_expired():
                self._store.pop(key, None)
                return default
            self._store.move_to_end(key)
            return entry.value

    def set(self, key: K, value: V) -> None:
        with self._lock:
            expires_at = None if self.ttl_seconds is None else monotonic() + self.ttl_seconds
            self._store[key] = CacheEntry(value=value, expires_at=expires_at)
            self._store.move_to_end(key)
            while len(self._store) > self.max_size:
                self._store.popitem(last=False)

    def pop(self, key: K, default: V | None = None) -> V | None:
        with self._lock:
            entry = self._store.pop(key, None)
            if entry is None or entry.is_expired():
                return default
            return entry.value

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def __contains__(self, key: K) -> bool:
        return self.get(key) is not None

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)
