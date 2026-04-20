import time
from typing import Any

_STALE_TIMEOUT = 3600  # seconds; stale data older than this is dropped even on error


class Cache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float, float]] = {}

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        now = time.monotonic()
        expiry = now + ttl_seconds
        stale_expiry = now + ttl_seconds + _STALE_TIMEOUT
        self._store[key] = (value, expiry, stale_expiry)

    def get(self, key: str, return_stale: bool = False) -> Any:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expiry, stale_expiry = entry
        now = time.monotonic()
        if now <= expiry:
            return value
        if return_stale and now <= stale_expiry:
            return value
        return None

    def is_expired(self, key: str) -> bool:
        entry = self._store.get(key)
        if entry is None:
            return True
        _, expiry, _ = entry
        return time.monotonic() > expiry
