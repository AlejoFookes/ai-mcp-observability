from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from httpx import ASGITransport

from multimcp_api.main import create_app
from multimcp_api.repositories.memory import MemoryEventRepository
from multimcp_api.settings import Settings
from factories import make_genai

START = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
END = START + timedelta(days=1)


def _auth() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def repo() -> MemoryEventRepository:
    return MemoryEventRepository()


@pytest.fixture
def app(repo: MemoryEventRepository):
    return create_app(
        settings=Settings(ingest_token="test-token", storage_backend="memory"),
        repository=repo,
    )


@pytest.mark.asyncio
async def test_list_traces_newest_first(app, repo: MemoryEventRepository) -> None:
    await repo.insert_genai(
        [
            make_genai(
                trace_id="old",
                occurred_at=START,
                prompt_version="support-v1",
            ),
            make_genai(
                trace_id="new",
                occurred_at=START + timedelta(minutes=5),
                prompt_version="support-v2",
            ),
        ]
    )
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/traces",
            params={"from": START.isoformat(), "to": END.isoformat(), "limit": 10},
            headers=_auth(),
        )
    assert response.status_code == 200
    rows = response.json()["rows"]
    assert [row["trace_id"] for row in rows] == ["new", "old"]
    assert rows[0]["prompt_version"] == "support-v2"
