"""Sliding-window limiter and client IP extraction for /explain."""

from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import SecretStr

from atlas.api import ratelimit
from atlas.api.ratelimit import RateLimiter, client_ip, rate_limit_key


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


def test_client_ip_uses_the_trusted_rightmost_forwarded_hop() -> None:
    forwarded = _request({"x-forwarded-for": "203.0.113.7, 10.0.0.1"}, "10.0.0.2")

    assert client_ip(forwarded) == "10.0.0.2"
    assert client_ip(forwarded, trusted_proxy_hops=1) == "10.0.0.1"
    assert client_ip(_request({}, "10.0.0.2")) == "10.0.0.2"
    assert client_ip(_request({"x-forwarded-for": " "}, None), trusted_proxy_hops=1) == "unknown"


def test_rate_limit_key_requires_the_frontend_token() -> None:
    request = _request(
        {"x-atlas-visitor-ip": "203.0.113.7", "x-atlas-frontend": "correct"}, "10.0.0.2"
    )

    assert (
        rate_limit_key(request, trusted_proxy_hops=0, frontend_api_token=SecretStr("correct"))
        == "visitor:203.0.113.7"
    )
    assert (
        rate_limit_key(request, trusted_proxy_hops=0, frontend_api_token=SecretStr("wrong"))
        == "ip:10.0.0.2"
    )
