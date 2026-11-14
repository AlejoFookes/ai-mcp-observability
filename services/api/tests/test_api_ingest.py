from __future__ import annotations

import httpx
import pytest
from factories import make_genai, make_mcp

from multimcp_api.main import create_app
from multimcp_api.repositories.memory import MemoryEventRepository
from multimcp_api.settings import Settings


@pytest.fixture
def repo() -> MemoryEventRepository:
    return MemoryEventRepository()


@pytest.fixture
def app(repo: MemoryEventRepository):
    return create_app(
        settings=Settings(ingest_token="test-token"),
        repository=repo,
    )


def _auth() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


@pytest.mark.asyncio
async def test_ingest_genai_and_duplicate(app, repo: MemoryEventRepository) -> None:
    event = make_genai()
    body = {
        "schema_version": "1.0",
        "events": [event.model_dump(mode="json")],
    }
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post("/api/v1/events", json=body, headers=_auth())
        second = await client.post("/api/v1/events", json=body, headers=_auth())

    assert first.status_code == 200
    assert first.json() == {"schema_version": "1.0", "accepted": 1, "duplicates": 0}
    assert second.json() == {"schema_version": "1.0", "accepted": 0, "duplicates": 1}
    assert event.event_id in repo.genai


@pytest.mark.asyncio
async def test_ingest_rejects_wrong_schema_version(app) -> None:
    event = make_genai()
    body = {
        "schema_version": "9.9",
        "events": [event.model_dump(mode="json")],
    }
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/events", json=body, headers=_auth())

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_ingest_rejects_more_than_100_events(app) -> None:
    events = [make_genai().model_dump(mode="json") for _ in range(101)]
    body = {"schema_version": "1.0", "events": events}
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/events", json=body, headers=_auth())

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ingest_rejects_body_over_1_mib(app) -> None:
    oversized = b'{"schema_version":"1.0","events":[]' + (b" " * (1024 * 1024)) + b"}"
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/events",
            content=oversized,
            headers={**_auth(), "content-type": "application/json"},
        )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


@pytest.mark.asyncio
async def test_ingest_mcp_events(app, repo: MemoryEventRepository) -> None:
    event = make_mcp()
    body = {"schema_version": "1.0", "events": [event.model_dump(mode="json")]}
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/mcp-events", json=body, headers=_auth())

    assert response.status_code == 200
    assert response.json()["accepted"] == 1
    assert event.event_id in repo.mcp
