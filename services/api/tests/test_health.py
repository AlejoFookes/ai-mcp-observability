from __future__ import annotations

import httpx
import pytest

from multimcp_api.health import AlwaysDownProbe
from multimcp_api.main import create_app
from multimcp_api.settings import Settings


@pytest.mark.asyncio
async def test_health_ok_without_token(app) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "schema_version": "1.0",
        "status": "ok",
        "storage_backend": "postgres",
    }


@pytest.mark.asyncio
async def test_health_degraded_still_200() -> None:
    app = create_app(
        settings=Settings(ingest_token="x"),
        health_probe=AlwaysDownProbe(),
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"


@pytest.mark.asyncio
async def test_health_ready_returns_503_when_storage_down() -> None:
    app = create_app(
        settings=Settings(ingest_token="x"),
        health_probe=AlwaysDownProbe(),
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health", params={"ready": "true"})

    assert response.status_code == 503
    body = response.json()
    assert body["schema_version"] == "1.0"
    assert body["error"]["code"] == "storage_unavailable"
    assert "traceback" not in response.text.lower()
