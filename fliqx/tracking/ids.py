from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TrackIdGenerator:
    prefix: str = "track"
    _next_value: int = 1

    def next(self) -> str:
        value = f"{self.prefix}-{self._next_value}"
        self._next_value += 1
        return value
