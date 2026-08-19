import time

from cache import Cache


def test_set_and_get() -> None:
    c = Cache()
    c.set("key", "value", ttl_seconds=10)
    assert c.get("key") == "value"


def test_get_missing_returns_none() -> None:
    c = Cache()
    assert c.get("nonexistent") is None


def test_expired_returns_none() -> None:
    c = Cache()
    c.set("key", "value", ttl_seconds=0)
    time.sleep(0.01)
    assert c.get("key") is None


def test_stale_returns_last_value_when_flagged() -> None:
    c = Cache()
    c.set("key", "stale_value", ttl_seconds=0)
    time.sleep(0.01)
    assert c.get("key", return_stale=True) == "stale_value"


def test_overwrite() -> None:
    c = Cache()
    c.set("key", "old", ttl_seconds=10)
    c.set("key", "new", ttl_seconds=10)
    assert c.get("key") == "new"


def test_stale_window_defaults_to_one_hour() -> None:
    c = Cache()
    c.set("key", "value", ttl_seconds=10)
    _, expiry, stale_expiry = c._store["key"]
    assert stale_expiry - expiry == 3600


def test_stale_seconds_override_shortens_window() -> None:
    c = Cache()
    c.set("key", "value", ttl_seconds=0, stale_seconds=0)
    time.sleep(0.01)
    assert c.get("key", return_stale=True) is None


def test_stale_seconds_override_extends_window() -> None:
    c = Cache()
    c.set("key", "value", ttl_seconds=10, stale_seconds=86400)
    _, expiry, stale_expiry = c._store["key"]
    assert stale_expiry - expiry == 86400
