from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from factories import make_genai, make_mcp

from multimcp_api.domain.models import (
    CompareQuery,
    EvalJob,
    EvalOutcome,
    WindowQuery,
)
from multimcp_api.repositories.memory import MemoryEventRepository
from multimcp_api.repositories.stats import percentile_cont


@pytest.fixture
def repo() -> MemoryEventRepository:
    return MemoryEventRepository()


@pytest.mark.asyncio
async def test_insert_genai_is_idempotent(repo: MemoryEventRepository) -> None:
    event = make_genai()
    first = await repo.insert_genai([event])
    second = await repo.insert_genai([event])
    assert first.accepted == 1 and first.duplicates == 0
    assert second.accepted == 0 and second.duplicates == 1


@pytest.mark.asyncio
async def test_finops_excludes_judge_by_default(repo: MemoryEventRepository) -> None:
    start = datetime(2026, 11, 14, tzinfo=UTC)
    end = start + timedelta(days=1)
    await repo.insert_genai(
        [
            make_genai(cost="0.010", occurred_at=start),
            make_genai(
                cost="0.050",
                occurred_at=start,
                metadata={"role": "judge"},
            ),
        ]
    )
    rows = await repo.finops_summary(
        WindowQuery.model_validate(
            {"from": start, "to": end, "group_by": "model", "include_judge": False}
        )
    )
    assert len(rows) == 1
    assert rows[0].request_count == 1
    assert rows[0].estimated_cost_usd == Decimal("0.010")


@pytest.mark.asyncio
async def test_finops_mcp_server_has_zero_model_cost(repo: MemoryEventRepository) -> None:
    start = datetime(2026, 11, 14, tzinfo=UTC)
    end = start + timedelta(days=1)
    await repo.insert_mcp([make_mcp(occurred_at=start), make_mcp(occurred_at=start)])
    rows = await repo.finops_summary(
        WindowQuery.model_validate({"from": start, "to": end, "group_by": "mcp_server"})
    )
    assert rows[0].key == "docs"
    assert rows[0].request_count == 2
    assert rows[0].estimated_cost_usd == Decimal("0")
    assert rows[0].input_tokens == 0


@pytest.mark.asyncio
async def test_latency_percentiles(repo: MemoryEventRepository) -> None:
    start = datetime(2026, 11, 14, tzinfo=UTC)
    end = start + timedelta(days=1)
    samples = [10.0, 20.0, 30.0, 40.0, 100.0]
    await repo.insert_genai(
        [make_genai(latency_ms=value, occurred_at=start) for value in samples]
    )
    rows = await repo.latency(
        WindowQuery.model_validate({"from": start, "to": end, "group_by": "model"})
    )
    assert len(rows) == 1
    assert rows[0].p50_ms == pytest.approx(percentile_cont(samples, 0.50))
    assert rows[0].p95_ms == pytest.approx(percentile_cont(samples, 0.95))
    assert rows[0].count == 5


@pytest.mark.asyncio
async def test_trace_merges_genai_and_mcp(repo: MemoryEventRepository) -> None:
    trace = "trace-1"
    t0 = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
    t1 = t0 + timedelta(milliseconds=5)
    await repo.insert_genai([make_genai(trace_id=trace, occurred_at=t0)])
    await repo.insert_mcp([make_mcp(trace_id=trace, occurred_at=t1)])
    spans = await repo.get_trace(trace)
    assert [span.kind for span in spans] == ["genai", "mcp"]
    assert await repo.get_trace("missing") == []


@pytest.mark.asyncio
async def test_compare_prompt_versions(repo: MemoryEventRepository) -> None:
    start = datetime(2026, 11, 14, tzinfo=UTC)
    end = start + timedelta(days=1)
    await repo.insert_genai(
        [
            make_genai(prompt_version="a", cost="0.001", occurred_at=start),
            make_genai(prompt_version="a", cost="0.001", occurred_at=start),
            make_genai(prompt_version="b", cost="0.002", occurred_at=start),
        ]
    )
    result = await repo.compare(
        CompareQuery.model_validate(
            {
                "from": start,
                "to": end,
                "dimension": "prompt_version",
                "left": "a",
                "right": "b",
            }
        )
    )
    assert result.left.request_count == 2
    assert result.right.request_count == 1
    assert result.left.estimated_cost_usd == Decimal("0.002")


@pytest.mark.asyncio
async def test_eval_claim_and_complete(repo: MemoryEventRepository) -> None:
    job = EvalJob(
        rubric_version="rag-judge-1.0",
        query="q",
        contexts=["c"],
        answer="a",
    )
    await repo.enqueue_eval(job)
    claimed = await repo.claim_eval_jobs(limit=1, lock_seconds=30)
    assert len(claimed) == 1
    assert claimed[0].status == "running"
    assert claimed[0].attempt == 1
    await repo.complete_eval(
        claimed[0].job_id,
        EvalOutcome(
            status="succeeded",
            context_relevance=1.0,
            hallucination_label="supported",
            rationale="ok",
        ),
    )
    assert repo.evals[job.job_id].status == "succeeded"
