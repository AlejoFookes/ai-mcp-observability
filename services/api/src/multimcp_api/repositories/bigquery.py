"""BigQuery EventRepository. google.cloud.bigquery is imported only here (lazy)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from multimcp.models import GenAIEvent, McpEvent
from multimcp_api.domain.models import (
    CompareQuery,
    CompareResult,
    EvalJob,
    EvalOutcome,
    FinOpsRow,
    InsertResult,
    LatencyRow,
    TraceSpan,
    WindowQuery,
)
from multimcp_api.repositories import stats


class BigQueryEvalUnsupportedError(RuntimeError):
    """Raised when the Postgres-style eval worker tries to claim jobs on BigQuery."""


class BigQueryEventRepository:
    """Streaming-insert GenAI/MCP events. Eval jobs stay local for EVAL_BACKEND=inline."""

    def __init__(
        self,
        *,
        project: str,
        dataset: str = "multimcp",
        client: Any | None = None,
    ) -> None:
        if client is None:
            from google.cloud import bigquery

            client = bigquery.Client(project=project)
        self._client = client
        self._project = project
        self._dataset = dataset
        self._evals: dict[UUID, EvalJob] = {}

    def _table(self, name: str) -> str:
        return f"{self._project}.{self._dataset}.{name}"

    async def ping(self) -> bool:
        try:
            self._client.query("SELECT 1").result()
            return True
        except Exception:
            return False

    async def insert_genai(self, events: Sequence[GenAIEvent]) -> InsertResult:
        if not events:
            return InsertResult(accepted=0, duplicates=0)
        rows = [_genai_row(event) for event in events]
        row_ids = [str(event.event_id) for event in events]
        errors = self._client.insert_rows_json(
            self._table("genai_events"), rows, row_ids=row_ids
        )
        if errors:
            raise RuntimeError(f"BigQuery insert_genai failed: {errors}")
        return InsertResult(accepted=len(events), duplicates=0)

    async def insert_mcp(self, events: Sequence[McpEvent]) -> InsertResult:
        if not events:
            return InsertResult(accepted=0, duplicates=0)
        rows = [_mcp_row(event) for event in events]
        row_ids = [str(event.event_id) for event in events]
        errors = self._client.insert_rows_json(
            self._table("mcp_events"), rows, row_ids=row_ids
        )
        if errors:
            raise RuntimeError(f"BigQuery insert_mcp failed: {errors}")
        return InsertResult(accepted=len(events), duplicates=0)

    async def finops_summary(self, query: WindowQuery) -> list[FinOpsRow]:
        if query.group_by == "mcp_server":
            sql = f"""
            SELECT server_name AS key,
                   COUNT(*) AS request_count,
                   COUNTIF(status = 'error') AS error_count
            FROM `{self._table("mcp_events")}`
            WHERE occurred_at >= @start AND occurred_at < @end
            GROUP BY server_name
            ORDER BY key
            """
            rows = self._query(sql, query.start, query.end)
            return [
                FinOpsRow(
                    key=row["key"],
                    request_count=int(row["request_count"]),
                    error_count=int(row["error_count"]),
                    input_tokens=0,
                    output_tokens=0,
                    estimated_cost_usd=Decimal("0"),
                    unpriced_count=0,
                )
                for row in rows
            ]
        key_expr = _genai_key_expr(query.group_by)
        judge = ""
        if not query.include_judge:
            judge = "AND IFNULL(JSON_VALUE(metadata, '$.role'), '') != 'judge'"
        sql = f"""
        SELECT {key_expr} AS key,
               COUNT(*) AS request_count,
               COUNTIF(status = 'error') AS error_count,
               IFNULL(SUM(input_tokens), 0) AS input_tokens,
               IFNULL(SUM(output_tokens), 0) AS output_tokens,
               IFNULL(SUM(IF(price_status = 'priced', estimated_cost_usd, 0)), 0)
                   AS estimated_cost_usd,
               COUNTIF(price_status = 'unpriced') AS unpriced_count
        FROM `{self._table("genai_events")}`
        WHERE occurred_at >= @start AND occurred_at < @end
        {judge}
        GROUP BY key
        ORDER BY key
        """
        rows = self._query(sql, query.start, query.end)
        return [
            FinOpsRow(
                key=row["key"],
                request_count=int(row["request_count"]),
                error_count=int(row["error_count"]),
                input_tokens=int(row["input_tokens"]),
                output_tokens=int(row["output_tokens"]),
                estimated_cost_usd=Decimal(str(row["estimated_cost_usd"])),
                unpriced_count=int(row["unpriced_count"]),
            )
            for row in rows
        ]

    async def latency(self, query: WindowQuery) -> list[LatencyRow]:
        if query.group_by == "mcp_tool":
            key_expr = (
                "IF(tool_name IS NULL OR tool_name = '', server_name, "
                "CONCAT(server_name, '/', tool_name))"
            )
            table = self._table("mcp_events")
        else:
            key_expr = _genai_key_expr(query.group_by)
            table = self._table("genai_events")
        sql = f"""
        SELECT key,
               COUNT(*) AS count,
               APPROX_QUANTILES(latency_ms, 100)[OFFSET(50)] AS p50_ms,
               APPROX_QUANTILES(latency_ms, 100)[OFFSET(95)] AS p95_ms,
               COUNTIF(status = 'error') / COUNT(*) AS error_rate
        FROM (
            SELECT {key_expr} AS key, latency_ms, status
            FROM `{table}`
            WHERE occurred_at >= @start AND occurred_at < @end
        )
        GROUP BY key
        ORDER BY key
        """
        rows = self._query(sql, query.start, query.end)
        return [
            LatencyRow(
                key=row["key"],
                count=int(row["count"]),
                p50_ms=float(row["p50_ms"]),
                p95_ms=float(row["p95_ms"]),
                error_rate=float(row["error_rate"]),
            )
            for row in rows
        ]

    async def get_trace(self, trace_id: str) -> list[TraceSpan]:
        genai_sql = f"""
        SELECT * FROM `{self._table("genai_events")}`
        WHERE trace_id = @trace_id ORDER BY occurred_at
        """
        mcp_sql = f"""
        SELECT * FROM `{self._table("mcp_events")}`
        WHERE trace_id = @trace_id ORDER BY occurred_at
        """
        genai_rows = self._query_trace(genai_sql, trace_id)
        mcp_rows = self._query_trace(mcp_sql, trace_id)
        genai = [_row_to_genai(row) for row in genai_rows]
        mcp = [_row_to_mcp(row) for row in mcp_rows]
        return stats.build_trace(genai, mcp, trace_id)

    async def compare(self, query: CompareQuery) -> CompareResult:
        sql = f"""
        SELECT * FROM `{self._table("genai_events")}`
        WHERE occurred_at >= @start AND occurred_at < @end
        """
        rows = self._query(sql, query.start, query.end)
        events = [_row_to_genai(row) for row in rows]
        return stats.build_compare(events, query)

    async def enqueue_eval(self, job: EvalJob) -> None:
        stored = job.model_copy(
            update={"status": "queued", "created_at": job.created_at or datetime.now(UTC)}
        )
        self._evals[stored.job_id] = stored

    async def get_eval(self, job_id: UUID) -> EvalJob | None:
        return self._evals.get(job_id)

    async def start_eval(self, job_id: UUID, lock_seconds: int) -> EvalJob | None:
        from datetime import timedelta

        job = self._evals.get(job_id)
        if job is None:
            return None
        now = datetime.now(UTC)
        updated = job.model_copy(
            update={
                "status": "running",
                "started_at": now,
                "locked_at": now + timedelta(seconds=lock_seconds),
                "attempt": job.attempt + 1,
            }
        )
        self._evals[job_id] = updated
        return updated

    async def claim_eval_jobs(self, limit: int, lock_seconds: int) -> list[EvalJob]:
        raise BigQueryEvalUnsupportedError(
            "Eval worker claim is Postgres-only; "
            "use EVAL_BACKEND=inline with STORAGE_BACKEND=bigquery"
        )

    async def requeue_eval(self, job_id: UUID) -> None:
        job = self._evals[job_id]
        self._evals[job_id] = job.model_copy(
            update={"status": "queued", "locked_at": None, "started_at": None}
        )

    async def complete_eval(self, job_id: UUID, outcome: EvalOutcome) -> None:
        job = self._evals[job_id]
        self._evals[job_id] = job.model_copy(
            update={
                "status": outcome.status,
                "context_relevance": outcome.context_relevance,
                "hallucination_label": outcome.hallucination_label,
                "rationale": outcome.rationale,
                "error_message": outcome.error_message,
                "judge_model": outcome.judge_model or job.judge_model,
                "finished_at": datetime.now(UTC),
                "locked_at": None,
            }
        )

    def _query(self, sql: str, start: datetime, end: datetime) -> list[dict[str, Any]]:
        job = self._client.query(sql, job_config=_query_config(start=start, end=end))
        return [dict(row) for row in job.result()]

    def _query_trace(self, sql: str, trace_id: str) -> list[dict[str, Any]]:
        job = self._client.query(sql, job_config=_query_config(trace_id=trace_id))
        return [dict(row) for row in job.result()]


def _query_config(**params: Any) -> Any:
    """Build a QueryJobConfig when the real SDK is present; otherwise a simple namespace."""
    try:
        from google.cloud import bigquery
    except ImportError:
        return {"params": params}
    config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter(key, _bq_type(value), value)
            for key, value in params.items()
        ]
    )
    return config


def _bq_type(value: Any) -> str:
    if isinstance(value, datetime):
        return "TIMESTAMP"
    return "STRING"


def _genai_key_expr(group_by: str) -> str:
    if group_by == "model":
        return "CONCAT(provider, '/', model)"
    if group_by == "provider":
        return "provider"
    if group_by == "prompt_version":
        return "IFNULL(prompt_version, '')"
    if group_by == "operation":
        return "operation"
    raise ValueError(f"unsupported genai group_by: {group_by}")


def _genai_row(event: GenAIEvent) -> dict[str, Any]:
    return {
        "event_id": str(event.event_id),
        "schema_version": event.schema_version,
        "occurred_at": event.occurred_at.isoformat(),
        "environment": event.environment,
        "sdk_name": event.sdk_name,
        "sdk_version": event.sdk_version,
        "provider": event.provider,
        "model": event.model,
        "operation": event.operation,
        "prompt_version": event.prompt_version,
        "trace_id": event.trace_id,
        "span_id": event.span_id,
        "parent_span_id": event.parent_span_id,
        "input_tokens": event.input_tokens,
        "output_tokens": event.output_tokens,
        "reasoning_tokens": event.reasoning_tokens,
        "cache_read_tokens": event.cache_read_tokens,
        "cache_write_tokens": event.cache_write_tokens,
        "ttft_ms": event.ttft_ms,
        "latency_ms": event.latency_ms,
        "estimated_cost_usd": (
            float(event.estimated_cost_usd) if event.estimated_cost_usd is not None else None
        ),
        "catalog_version": event.catalog_version,
        "price_status": event.price_status,
        "status": event.status,
        "error_type": event.error_type,
        "metadata": dict(event.metadata),
    }


def _mcp_row(event: McpEvent) -> dict[str, Any]:
    return {
        "event_id": str(event.event_id),
        "schema_version": event.schema_version,
        "occurred_at": event.occurred_at.isoformat(),
        "environment": event.environment,
        "server_name": event.server_name,
        "transport": event.transport,
        "method": event.method,
        "tool_name": event.tool_name,
        "jsonrpc_id": event.jsonrpc_id,
        "latency_ms": event.latency_ms,
        "payload_bytes": event.payload_bytes,
        "status": event.status,
        "error_code": event.error_code,
        "error_type": event.error_type,
        "trace_id": event.trace_id,
    }


def _row_to_genai(row: dict[str, Any]) -> GenAIEvent:
    return GenAIEvent.model_validate(
        {
            **row,
            "event_id": row["event_id"],
            "metadata": row.get("metadata") or {},
            "estimated_cost_usd": (
                Decimal(str(row["estimated_cost_usd"]))
                if row.get("estimated_cost_usd") is not None
                else None
            ),
        }
    )


def _row_to_mcp(row: dict[str, Any]) -> McpEvent:
    return McpEvent.model_validate(row)
