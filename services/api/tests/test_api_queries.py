from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from factories import make_genai, make_mcp

from multimcp_api.main import create_app
from multimcp_api.repositories.memory import MemoryEventRepository
from multimcp_api.settings import Settings

START = datetime(2026, 11, 1, tzinfo=UTC)
END = datetime(2026, 11, 15, tzinfo=UTC)


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


async def _seed(app, repo: MemoryEventRepository) -> None:
    await repo.insert_genai(
        [
            make_genai(prompt_version="a", cost="0.001", occurred_at=START),
            make_genai(
                prompt_version="a",
                cost="0.050",
                occurred_at=START,
                metadata={"role": "judge"},
            ),
            make_genai(prompt_version="b", cost="0.002", occurred_at=START),
        ]
    )
    await repo.insert_mcp([make_mcp(occurred_at=START, server_name="docs")])


@pytest.mark.asyncio
async def test_finops_excludes_judge_and_mcp_server_zero_cost(app, repo) -> None:
    await _seed(app, repo)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        finops = await client.get(
            "/api/v1/finops/summary",
            params={
                "from": START.isoformat(),
                "to": END.isoformat(),
                "group_by": "prompt_version",
            },
            headers=_auth(),
        )
        mcp = await client.get(
            "/api/v1/finops/summary",
            params={
                "from": START.isoformat(),
                "to": END.isoformat(),
                "group_by": "mcp_server",
            },
            headers=_auth(),
        )

    assert finops.status_code == 200
    rows = {row["key"]: row for row in finops.json()["rows"]}
    assert rows["a"]["request_count"] == 1
    assert Decimal(rows["a"]["estimated_cost_usd"]) == Decimal("0.001")
    assert "judge" not in str(finops.json())

    assert mcp.status_code == 200
    assert mcp.json()["rows"][0]["key"] == "docs"
    assert Decimal(mcp.json()["rows"][0]["estimated_cost_usd"]) == Decimal("0")
    assert mcp.json()["rows"][0]["input_tokens"] == 0


@pytest.mark.asyncio
async def test_latency_and_compare(app, repo) -> None:
    await repo.insert_genai(
        [
            make_genai(prompt_version="a", latency_ms=10, occurred_at=START),
            make_genai(prompt_version="a", latency_ms=30, occurred_at=START),
            make_genai(prompt_version="b", latency_ms=50, occurred_at=START),
        ]
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        latency = await client.get(
            "/api/v1/latency",
            params={
                "from": START.isoformat(),
                "to": END.isoformat(),
                "group_by": "model",
            },
            headers=_auth(),
        )
        compare = await client.get(
            "/api/v1/compare",
            params={
                "from": START.isoformat(),
                "to": END.isoformat(),
                "dimension": "prompt_version",
                "left": "a",
                "right": "b",
            },
            headers=_auth(),
        )

    assert latency.status_code == 200
    assert latency.json()["rows"][0]["count"] == 3
    assert compare.status_code == 200
    assert compare.json()["left"]["request_count"] == 2
    assert compare.json()["right"]["request_count"] == 1


@pytest.mark.asyncio
async def test_trace_404_and_found(app, repo) -> None:
    event = make_genai(trace_id="trace-xyz", occurred_at=START)
    tool = make_mcp(trace_id="trace-xyz", occurred_at=START + timedelta(milliseconds=1))
    await repo.insert_genai([event])
    await repo.insert_mcp([tool])

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        missing = await client.get("/api/v1/traces/nope", headers=_auth())
        found = await client.get("/api/v1/traces/trace-xyz", headers=_auth())

    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"
    assert found.status_code == 200
    assert [span["kind"] for span in found.json()["spans"]] == ["genai", "mcp"]


@pytest.mark.asyncio
async def test_window_over_31_days_is_422(app) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/finops/summary",
            params={
                "from": START.isoformat(),
                "to": (START + timedelta(days=32)).isoformat(),
                "group_by": "model",
            },
            headers=_auth(),
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_queries_require_bearer(app) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/latency",
            params={"from": START.isoformat(), "to": END.isoformat()},
        )

    assert response.status_code == 401
