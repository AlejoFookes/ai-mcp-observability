from __future__ import annotations

import httpx
import pytest

from multimcp_api.main import create_app
from multimcp_api.settings import Settings


@pytest.mark.asyncio
async def test_post_without_bearer_is_401(app) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/events")

    assert response.status_code == 401
    body = response.json()
    assert body["schema_version"] == "1.0"
    assert body["error"]["code"] == "unauthorized"
    assert body["error"]["details"] == []


@pytest.mark.asyncio
async def test_post_with_wrong_bearer_is_401(app) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/events",
            headers={"Authorization": "Bearer wrong"},
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_post_with_valid_bearer_succeeds(app) -> None:
    from factories import make_genai

    event = make_genai()
    body = {"schema_version": "1.0", "events": [event.model_dump(mode="json")]}
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/events",
            json=body,
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "schema_version": "1.0",
        "accepted": 1,
        "duplicates": 0,
    }


@pytest.mark.asyncio
async def test_empty_ingest_token_rejects_all_posts() -> None:
    app = create_app(settings=Settings(ingest_token=""))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/mcp-events",
            headers={"Authorization": "Bearer anything"},
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
