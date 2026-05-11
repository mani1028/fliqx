from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from time import monotonic


@dataclass(slots=True)
class SessionStats:
    session_id: str
    created_at: float = field(default_factory=monotonic)
    last_seen: float = field(default_factory=monotonic)
    hits: int = 0
    misses: int = 0
    active_tracks: set[str] = field(default_factory=set)

    def touch(self) -> None:
        self.last_seen = monotonic()


class SessionStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._sessions: dict[str, SessionStats] = {}

    def get(self, session_id: str) -> SessionStats:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                session = SessionStats(session_id=session_id)
                self._sessions[session_id] = session
            session.touch()
            return session

    def record_hit(self, session_id: str, track_id: str | None = None) -> SessionStats:
        session = self.get(session_id)
        session.hits += 1
        if track_id is not None:
            session.active_tracks.add(track_id)
        return session

    def record_miss(self, session_id: str) -> SessionStats:
        session = self.get(session_id)
        session.misses += 1
        return session

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()
