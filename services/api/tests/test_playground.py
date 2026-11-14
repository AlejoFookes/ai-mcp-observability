from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
from httpx import ASGITransport

from multimcp_api.main import create_app
from multimcp_api.playground.dual import DualResult, DualSide
from multimcp_api.repositories.memory import MemoryEventRepository
from multimcp_api.settings import Settings


def _app():
    return create_app(
        settings=Settings(
            ingest_token="test-token",
            storage_backend="memory",
            openai_api_key="sk-test",
        ),
        repository=MemoryEventRepository(),
    )


def _auth() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


@pytest.mark.asyncio
async def test_playground_dual_returns_both_sides() -> None:
    fake = DualResult(
        trace_id="trace-1",
        prompt_version="playground",
        left=DualSide(model="gpt-4.1-mini", answer="hola left", latency_ms=12.0),
        right=DualSide(model="gpt-4.1-nano", answer="hola right", latency_ms=8.0),
    )
    with patch("multimcp_api.api.v1.playground.run_dual_completion", return_value=fake):
        transport = ASGITransport(app=_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/playground/dual",
                headers=_auth(),
                json={
                    "schema_version": "1.0",
                    "prompt": "Hola",
                    "left_model": "gpt-4.1-mini",
                    "right_model": "gpt-4.1-nano",
                },
            )
    assert response.status_code == 200
    body = response.json()
    assert body["trace_id"] == "trace-1"
    assert body["left"]["answer"] == "hola left"
    assert body["right"]["answer"] == "hola right"


@pytest.mark.asyncio
async def test_playground_dual_requires_auth() -> None:
    transport = ASGITransport(app=_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/playground/dual",
            json={
                "schema_version": "1.0",
                "prompt": "Hola",
                "left_model": "a",
                "right_model": "b",
            },
        )
    assert response.status_code == 401
