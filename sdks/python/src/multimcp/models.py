from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID, uuid4

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    model_validator,
)

from multimcp._version import __version__

SCHEMA_VERSION: Literal["1.0"] = "1.0"

MAX_METADATA_KEYS = 16
MAX_METADATA_KEY_LENGTH = 64
MAX_METADATA_VALUE_LENGTH = 128

Provider = Literal["openai", "anthropic", "google"]
Operation = Literal[
    "responses.create",
    "chat.completions.create",
    "messages.create",
    "messages.stream",
    "models.generate_content",
]
Status = Literal["ok", "error"]
PriceStatus = Literal["priced", "unpriced"]
Transport = Literal["stdio", "streamable_http"]
McpErrorType = Literal["jsonrpc", "framing", "transport"]
MetadataValue = StrictStr | StrictBool | StrictInt | StrictFloat


def utc_now() -> datetime:
    return datetime.now(UTC)


class _Event(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = SCHEMA_VERSION
    event_id: UUID = Field(default_factory=uuid4)
    occurred_at: AwareDatetime = Field(default_factory=utc_now)
    environment: str = Field(min_length=1, max_length=64)
    trace_id: str = Field(min_length=1, max_length=128)


class GenAIEvent(_Event):
    """One model call. Never carries prompt or completion text.

    `input_tokens` counts every input token, including cache reads and writes.
    `output_tokens` counts every billed output token, including reasoning.
    The reasoning and cache fields are breakdowns of those totals, not additions.
    """

    sdk_name: Literal["multimcp"] = "multimcp"
    sdk_version: str = __version__
    provider: Provider
    model: str = Field(min_length=1, max_length=128)
    operation: Operation
    prompt_version: str | None = Field(default=None, max_length=128)
    span_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1, max_length=128)
    parent_span_id: str | None = Field(default=None, max_length=128)
    input_tokens: NonNegativeInt | None = None
    output_tokens: NonNegativeInt | None = None
    reasoning_tokens: NonNegativeInt | None = None
    cache_read_tokens: NonNegativeInt | None = None
    cache_write_tokens: NonNegativeInt | None = None
    ttft_ms: NonNegativeFloat | None = None
    latency_ms: NonNegativeFloat
    estimated_cost_usd: Decimal | None = Field(default=None, ge=0)
    catalog_version: str | None = None
    price_status: PriceStatus
    status: Status
    error_type: str | None = Field(default=None, max_length=128)
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        if (self.price_status == "priced") != (self.estimated_cost_usd is not None):
            raise ValueError("estimated_cost_usd must be set exactly when price_status is priced")
        if (self.status == "error") != (self.error_type is not None):
            raise ValueError("error_type must be set exactly when status is error")
        _check_metadata(self.metadata)
        return self


class McpEvent(_Event):
    """One JSON-RPC request seen by the MCP proxy. Never carries params or result bodies."""

    server_name: str = Field(min_length=1, max_length=128)
    transport: Transport
    method: str = Field(min_length=1, max_length=128)
    tool_name: str | None = Field(default=None, max_length=128)
    jsonrpc_id: str | None = Field(default=None, max_length=128)
    latency_ms: NonNegativeFloat
    payload_bytes: NonNegativeInt
    status: Status
    error_code: int | None = None
    error_type: McpErrorType | None = None

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        if (self.status == "error") != (self.error_type is not None):
            raise ValueError("error_type must be set exactly when status is error")
        return self


def _check_metadata(metadata: dict[str, MetadataValue]) -> None:
    if len(metadata) > MAX_METADATA_KEYS:
        raise ValueError(f"metadata accepts at most {MAX_METADATA_KEYS} keys")
    for key, value in metadata.items():
        if not key or len(key) > MAX_METADATA_KEY_LENGTH:
            raise ValueError(f"metadata keys must be 1-{MAX_METADATA_KEY_LENGTH} characters")
        if isinstance(value, str) and len(value) > MAX_METADATA_VALUE_LENGTH:
            raise ValueError(f"metadata values must be at most {MAX_METADATA_VALUE_LENGTH} chars")
