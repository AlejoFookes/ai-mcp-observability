from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta

import pytest
from factories import make_genai

from multimcp_api.domain.models import WindowQuery
from multimcp_api.repositories.bigquery import (
    BigQueryEvalUnsupportedError,
    BigQueryEventRepository,
)


class FakeQueryJob:
    def __init__(self, rows: list[dict]):
        self._rows = rows

    def result(self):
        return self._rows


class FakeBigQueryClient:
    def __init__(self) -> None:
        self.inserted: list[tuple[str, list[dict], list[str] | None]] = []
        self.queries: list[str] = []
        self._latency_rows = [
            {
                "key": "openai/gpt-4.1-mini",
                "count": 2,
                "p50_ms": 15.0,
                "p95_ms": 20.0,
                "error_rate": 0.0,
            }
        ]

    def insert_rows_json(self, table, rows, row_ids=None):
        self.inserted.append((table, rows, row_ids))
        return []

    def query(self, sql, job_config=None):
        self.queries.append(sql)
        if "SELECT 1" in sql:
            return FakeQueryJob([{"f0_": 1}])
        if "APPROX_QUANTILES" in sql:
            return FakeQueryJob(self._latency_rows)
        return FakeQueryJob([])


@pytest.mark.asyncio
async def test_insert_uses_event_id_as_insert_id() -> None:
    client = FakeBigQueryClient()
    repo = BigQueryEventRepository(project="demo", dataset="multimcp", client=client)
    event = make_genai()
    result = await repo.insert_genai([event])
    assert result.accepted == 1
    table, rows, row_ids = client.inserted[0]
    assert table.endswith("genai_events")
    assert row_ids == [str(event.event_id)]
    assert rows[0]["event_id"] == str(event.event_id)


@pytest.mark.asyncio
async def test_latency_sql_uses_approx_quantiles() -> None:
    client = FakeBigQueryClient()
    repo = BigQueryEventRepository(project="demo", client=client)
    start = datetime(2026, 11, 14, tzinfo=UTC)
    rows = await repo.latency(
        WindowQuery.model_validate(
            {"from": start, "to": start + timedelta(days=1), "group_by": "model"}
        )
    )
    assert any("APPROX_QUANTILES" in sql for sql in client.queries)
    assert rows[0].p50_ms == 15.0


@pytest.mark.asyncio
async def test_claim_eval_unsupported() -> None:
    repo = BigQueryEventRepository(project="demo", client=FakeBigQueryClient())
    with pytest.raises(BigQueryEvalUnsupportedError):
        await repo.claim_eval_jobs(1, 30)


def test_postgres_import_path_does_not_load_google_bigquery() -> None:
    sys.modules.pop("google.cloud.bigquery", None)
    sys.modules.pop("multimcp_api.repositories.bigquery", None)
    import multimcp_api.repositories.factory as factory
    import multimcp_api.repositories.postgres  # noqa: F401

    assert "google.cloud.bigquery" not in sys.modules
    # Selecting postgres must not import the BQ module.
    from multimcp_api.settings import Settings

    settings = Settings(storage_backend="postgres", ingest_token="x")
    # build_repository for postgres creates an engine; we only care that importing
    # factory and choosing postgres does not pull google.cloud.bigquery.
    assert settings.storage_backend == "postgres"
    assert "google.cloud.bigquery" not in sys.modules
    assert factory.build_repository.__module__.endswith("factory")
