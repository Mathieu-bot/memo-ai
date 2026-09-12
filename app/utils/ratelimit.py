import threading
import time

_WINDOWS = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}


class FixedWindowRateLimiter:
    """In-memory fixed-window rate limiter, per process."""

    def __init__(self, spec: str):
        self.spec = spec
        limit, _, unit = spec.partition("/")
        self.limit = int(limit)
        self.window_seconds = _WINDOWS.get(unit.strip().lower(), 60)
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        window_start = now - self.window_seconds
        with self._lock:
            hits = [t for t in self._hits.get(key, []) if t > window_start]
            if len(hits) >= self.limit:
                self._hits[key] = hits
                return False
            hits.append(now)
            self._hits[key] = hits
            return True
