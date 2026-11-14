from __future__ import annotations

from typing import Literal

from pydantic import Field

from multimcp.models import SCHEMA_VERSION
from multimcp_api.schemas.common import ApiModel


class DualPlaygroundRequest(ApiModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    prompt: str = Field(min_length=1, max_length=16_384)
    left_model: str = Field(min_length=1, max_length=128)
    right_model: str = Field(min_length=1, max_length=128)
    prompt_version: str = Field(default="playground", min_length=1, max_length=64)


class DualSideOut(ApiModel):
    model: str
    answer: str
    latency_ms: float | None = None


class DualPlaygroundResponse(ApiModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    trace_id: str
    prompt_version: str
    left: DualSideOut
    right: DualSideOut
