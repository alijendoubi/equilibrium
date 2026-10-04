"""Sliding-window limiter and client IP extraction for /explain."""

from types import SimpleNamespace
from typing import Any

import pytest

from atlas.api import ratelimit
from atlas.api.ratelimit import RateLimiter, client_ip


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_window_blocks_then_recovers() -> None:
    clock = Clock()
    limiter = RateLimiter(2, window_s=60.0, clock=clock)

    assert [limiter.allow("a"), limiter.allow("a"), limiter.allow("a")] == [True, True, False]
    assert limiter.allow("b") is True
    clock.now = 60.0
    assert limiter.allow("a") is True


def test_tracking_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ratelimit, "MAX_TRACKED_CLIENTS", 3)
    limiter = RateLimiter(1, window_s=60.0, clock=Clock())

    for key in "abcde":
        limiter.allow(key)

    assert limiter.allow("a") is True  # the table was reset once it exceeded the bound


def _request(headers: dict[str, str], host: str | None) -> Any:
    client = SimpleNamespace(host=host) if host else None
    return SimpleNamespace(headers=headers, client=client)


def test_client_ip_prefers_first_forwarded_hop() -> None:
    forwarded = _request({"x-forwarded-for": "203.0.113.7, 10.0.0.1"}, "10.0.0.2")

    assert client_ip(forwarded) == "203.0.113.7"
    assert client_ip(_request({}, "10.0.0.2")) == "10.0.0.2"
    assert client_ip(_request({"x-forwarded-for": " "}, None)) == "unknown"
