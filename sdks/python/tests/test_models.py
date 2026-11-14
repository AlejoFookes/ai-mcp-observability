import json
from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from multimcp import GenAIEvent, McpEvent


def _event(**overrides):
    fields = {
        "environment": "test",
        "trace_id": "trace-1",
        "provider": "openai",
        "model": "gpt-5.5",
        "operation": "responses.create",
        "input_tokens": 120,
        "output_tokens": 40,
        "latency_ms": 940.2,
        "estimated_cost_usd": Decimal("0.00123400"),
        "catalog_version": "2026-11-01",
        "price_status": "priced",
        "status": "ok",
    }
    fields.update(overrides)
    return GenAIEvent(**fields)


def test_json_shape_matches_contract():
    payload = json.loads(_event().model_dump_json())
    assert payload["schema_version"] == "1.0"
    assert payload["sdk_name"] == "multimcp"
    assert payload["sdk_version"] == "0.1.0"
    assert payload["estimated_cost_usd"] == "0.00123400"
    assert payload["ttft_ms"] is None
    assert payload["metadata"] == {}
    assert datetime.fromisoformat(payload["occurred_at"]).tzinfo is not None


def test_round_trip_through_json():
    event = _event(metadata={"role": "judge", "attempt": 2})
    assert GenAIEvent.model_validate_json(event.model_dump_json()) == event


def test_rejects_other_schema_version():
    with pytest.raises(ValidationError):
        _event(schema_version="2.0")


def test_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        _event(prompt="leaked text")


def test_rejects_naive_timestamp():
    with pytest.raises(ValidationError):
        _event(occurred_at=datetime(2026, 11, 14, 12, 0, 0))


def test_priced_requires_cost_and_unpriced_forbids_it():
    with pytest.raises(ValidationError):
        _event(estimated_cost_usd=None)
    with pytest.raises(ValidationError):
        _event(price_status="unpriced")
    assert _event(price_status="unpriced", estimated_cost_usd=None).estimated_cost_usd is None


def test_error_type_tracks_status():
    with pytest.raises(ValidationError):
        _event(status="error")
    with pytest.raises(ValidationError):
        _event(error_type="APIStatusError")
    assert _event(status="error", error_type="APIStatusError").error_type == "APIStatusError"


def test_metadata_limits():
    with pytest.raises(ValidationError):
        _event(metadata={f"k{i}": i for i in range(17)})
    with pytest.raises(ValidationError):
        _event(metadata={"long": "x" * 129})
    with pytest.raises(ValidationError):
        _event(metadata={"nested": {"a": 1}})


def test_mcp_event_contract():
    event = McpEvent(
        environment="local",
        trace_id="t",
        server_name="filesystem",
        transport="stdio",
        method="tools/call",
        tool_name="read_file",
        jsonrpc_id="1",
        latency_ms=12.5,
        payload_bytes=4096,
        status="error",
        error_code=-32602,
        error_type="jsonrpc",
    )
    assert json.loads(event.model_dump_json())["schema_version"] == "1.0"
    with pytest.raises(ValidationError):
        McpEvent.model_validate({**event.model_dump(), "transport": "sse"})
