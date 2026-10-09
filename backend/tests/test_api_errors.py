"""Public graph-query limits and the stable API error envelope."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from atlas.api.main import create_app
from atlas.config import Settings, get_settings


@pytest.fixture
def limited_api() -> Iterator[TestClient]:
    app = create_app(Settings())
    app.dependency_overrides[get_settings] = lambda: Settings(QUERY_RATE_PER_MINUTE=2)
    with TestClient(app) as client:
        yield client


def test_search_rate_limit_is_per_forwarded_client(limited_api: TestClient) -> None:
    headers = {"x-forwarded-for": "203.0.113.7"}
    codes = [
        limited_api.get("/api/v1/search", params={"q": "gaucher"}, headers=headers).status_code
        for _ in range(3)
    ]
    blocked = limited_api.get("/api/v1/search", params={"q": "gaucher"}, headers=headers)
    other = limited_api.get(
        "/api/v1/search",
        params={"q": "gaucher"},
        headers={"x-forwarded-for": "198.51.100.8"},
    )

    assert codes == [200, 200, 429]
    assert blocked.headers["retry-after"] == "60"
    assert blocked.json()["error"] == {
        "code": "rate_limited",
        "message": "Too many graph requests; try again soon.",
    }
    assert other.status_code == 200


def test_search_and_graph_share_the_query_limit(limited_api: TestClient) -> None:
    headers = {"x-forwarded-for": "203.0.113.9"}
    assert (
        limited_api.get("/api/v1/search", params={"q": "gaucher"}, headers=headers).status_code
        == 200
    )
    assert limited_api.get("/api/v1/graph", headers=headers).status_code == 200
    response = limited_api.get("/api/v1/graph", headers=headers)

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"


@pytest.mark.parametrize(
    ("path", "params", "status", "code"),
    [
        ("/api/v1/search", {"q": " "}, 422, "validation_error"),
        ("/api/v1/search", {"q": "gaucher", "limit": 0}, 422, "validation_error"),
        ("/api/v1/graph", {"center": "MONDO:0000000"}, 404, "not_found"),
    ],
)
def test_query_errors_use_the_stable_envelope(
    limited_api: TestClient, path: str, params: dict[str, object], status: int, code: str
) -> None:
    response = limited_api.get(path, params=params)

    assert response.status_code == status
    body = response.json()
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]
