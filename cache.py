import time
from typing import Any


class Cache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float]] = {}

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        expiry = time.monotonic() + ttl_seconds
        self._store[key] = (value, expiry)

    def get(self, key: str, return_stale: bool = False) -> Any:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expiry = entry
        if time.monotonic() > expiry:
            return value if return_stale else None
        return value

    def is_expired(self, key: str) -> bool:
        entry = self._store.get(key)
        if entry is None:
            return True
        _, expiry = entry
        return time.monotonic() > expiry
