from collections.abc import Mapping
from typing import Any

from multimcp.errors import MultimcpConfigError
from multimcp.exporters.base import Exporter
from multimcp.instrument._core import (
    CallRecorder,
    Instrumentation,
    add,
    as_int,
    field,
    instrument_call,
    patch_method,
)
from multimcp.models import MetadataValue


def wrap_google[ClientT](
    client: ClientT,
    *,
    exporter: Exporter | None = None,
    metadata: Mapping[str, MetadataValue] | None = None,
) -> ClientT:
    """Instrument `generate_content` and `generate_content_stream` on `client.models` and
    `client.aio.models` of a Gemini Developer API client, in place. Returns the same client."""
    if field(client, "vertexai") is True or field(client, "enterprise") is True:
        raise MultimcpConfigError(
            "wrap_google supports the Gemini Developer API client only; "
            "enterprise (Vertex AI) clients are not instrumented in multimcp 0.1"
        )
    inst = Instrumentation("google", exporter, dict(metadata or {}))
    for models in (field(client, "models"), field(field(client, "aio"), "models")):
        if models is None:
            continue
        patch_method(
            models,
            "generate_content",
            lambda original: instrument_call(
                original,
                inst,
                operation="models.generate_content",
                read_usage=_read_response,
                observe_item=_observe_chunk,
            ),
        )
        patch_method(
            models,
            "generate_content_stream",
            lambda original: instrument_call(
                original,
                inst,
                operation="models.generate_content",
                read_usage=_read_response,
                observe_item=_observe_chunk,
                always_streams=True,
            ),
        )
    return client


def _record_usage(recorder: CallRecorder, metadata: Any) -> None:
    """`prompt_token_count` already includes cached tokens. Thinking tokens are billed as
    output but reported apart from `candidates_token_count`, so they are added in."""
    if metadata is None:
        return
    thoughts = as_int(field(metadata, "thoughts_token_count"))
    candidates = as_int(field(metadata, "candidates_token_count"))
    recorder.update_usage(
        input_tokens=as_int(field(metadata, "prompt_token_count")),
        output_tokens=add(candidates, thoughts),
        reasoning_tokens=thoughts,
        cache_read_tokens=as_int(field(metadata, "cached_content_token_count")),
    )


def _read_response(recorder: CallRecorder, response: Any) -> None:
    _record_usage(recorder, field(response, "usage_metadata"))


def _has_text(chunk: Any) -> bool:
    for candidate in field(chunk, "candidates") or []:
        for part in field(field(candidate, "content"), "parts") or []:
            if field(part, "text"):
                return True
    return False


def _observe_chunk(recorder: CallRecorder, chunk: Any) -> None:
    if _has_text(chunk):
        recorder.first_token()
    _record_usage(recorder, field(chunk, "usage_metadata"))
