from __future__ import annotations

from typing import Literal

from pydantic import Field

from multimcp.models import SCHEMA_VERSION, GenAIEvent, McpEvent
from multimcp_api.schemas.common import ApiModel, IngestResponse

MAX_EVENTS_PER_BATCH = 100
MAX_BODY_BYTES = 1 * 1024 * 1024


class GenAIIngestRequest(ApiModel):
    schema_version: Literal["1.0"]
    events: list[GenAIEvent] = Field(min_length=1, max_length=MAX_EVENTS_PER_BATCH)


class McpIngestRequest(ApiModel):
    schema_version: Literal["1.0"]
    events: list[McpEvent] = Field(min_length=1, max_length=MAX_EVENTS_PER_BATCH)


__all__ = [
    "MAX_BODY_BYTES",
    "MAX_EVENTS_PER_BATCH",
    "SCHEMA_VERSION",
    "GenAIIngestRequest",
    "IngestResponse",
    "McpIngestRequest",
]
