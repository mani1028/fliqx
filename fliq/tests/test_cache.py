from __future__ import annotations

from fliq.cache.memory import ThreadSafeTTLCache


def test_cache_set_get_and_expiry() -> None:
    cache = ThreadSafeTTLCache[str, int](max_size=2, ttl_seconds=60.0)
    cache.set("a", 1)
    assert cache.get("a") == 1
    assert "a" in cache
