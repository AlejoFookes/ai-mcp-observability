from __future__ import annotations

import httpx
import pytest
from fastapi import APIRouter

from multimcp_api.errors import AppError
from multimcp_api.main import create_app
from multimcp_api.settings import Settings


@pytest.mark.asyncio
async def test_unhandled_exception_has_no_traceback() -> None:
    app = create_app(settings=Settings(ingest_token="t"))

    boom = APIRouter()

    @boom.get("/boom")
    async def _boom() -> None:
        raise RuntimeError("secret stack")

    app.include_router(boom)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/boom")

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert "secret stack" not in response.text
    assert "traceback" not in response.text.lower()


@pytest.mark.asyncio
async def test_app_error_envelope() -> None:
    app = create_app(settings=Settings(ingest_token="t"))
    router = APIRouter()

    @router.get("/gone")
    async def _gone() -> None:
        raise AppError(404, "not_found", "missing")

    app.include_router(router)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/gone")

    assert response.status_code == 404
    assert response.json() == {
        "schema_version": "1.0",
        "error": {"code": "not_found", "message": "missing", "details": []},
    }
