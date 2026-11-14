from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from factories import make_genai

from multimcp_api.domain.models import WindowQuery
from multimcp_api.repositories.postgres import PostgresEventRepository, create_async_engine
from multimcp_api.repositories.stats import percentile_cont

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set; Postgres integration tests are optional",
)


@pytest.fixture
async def repo():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    repository = PostgresEventRepository(engine)
    assert await repository.ping()
    yield repository
    await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_insert_idempotent_and_latency(repo: PostgresEventRepository) -> None:
    start = datetime(2026, 11, 14, tzinfo=UTC)
    end = start + timedelta(days=1)
    samples = [10.0, 20.0, 30.0, 40.0, 100.0]
    events = [make_genai(latency_ms=value, occurred_at=start) for value in samples]
    first = await repo.insert_genai(events)
    second = await repo.insert_genai(events)
    assert first.accepted == 5 and first.duplicates == 0
    assert second.accepted == 0 and second.duplicates == 5

    rows = await repo.latency(
        WindowQuery.model_validate({"from": start, "to": end, "group_by": "model"})
    )
    assert len(rows) == 1
    assert rows[0].p50_ms == pytest.approx(percentile_cont(samples, 0.50))
    assert rows[0].p95_ms == pytest.approx(percentile_cont(samples, 0.95))
    assert rows[0].count == 5


@pytest.mark.asyncio
async def test_postgres_finops_cost(repo: PostgresEventRepository) -> None:
    start = datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=1)
    end = start + timedelta(hours=1)
    event = make_genai(cost="0.010", occurred_at=start, model="unique-model-m32")
    await repo.insert_genai([event])
    rows = await repo.finops_summary(
        WindowQuery.model_validate({"from": start, "to": end, "group_by": "model"})
    )
    match = [row for row in rows if row.key.endswith("unique-model-m32")]
    assert match
    assert match[0].estimated_cost_usd == Decimal("0.010")
