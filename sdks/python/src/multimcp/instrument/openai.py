from collections.abc import Mapping
from typing import Any

from multimcp.exporters.base import Exporter
from multimcp.instrument._core import (
    CallRecorder,
    Instrumentation,
    as_int,
    field,
    instrument_call,
    patch_method,
)
from multimcp.models import MetadataValue


def wrap_openai[ClientT](
    client: ClientT,
    *,
    exporter: Exporter | None = None,
    metadata: Mapping[str, MetadataValue] | None = None,
) -> ClientT:
    """Instrument `responses.create` and `chat.completions.create` on an OpenAI or AsyncOpenAI
    client, in place. Returns the same client."""
    inst = Instrumentation("openai", exporter, dict(metadata or {}))
    responses = field(client, "responses")
    if responses is not None:
        patch_method(
            responses,
            "create",
            lambda original: instrument_call(
                original,
                inst,
                operation="responses.create",
                read_usage=_read_responses_result,
                observe_item=_observe_responses_event,
            ),
        )
    completions = field(field(client, "chat"), "completions")
    if completions is not None:
        patch_method(
            completions,
            "create",
            lambda original: instrument_call(
                original,
                inst,
                operation="chat.completions.create",
                read_usage=_read_chat_result,
                observe_item=_observe_chat_chunk,
            ),
        )
    return client


def _record_responses_usage(recorder: CallRecorder, usage: Any) -> None:
    input_details = field(usage, "input_tokens_details")
    recorder.update_usage(
        input_tokens=as_int(field(usage, "input_tokens")),
        output_tokens=as_int(field(usage, "output_tokens")),
        reasoning_tokens=as_int(field(field(usage, "output_tokens_details"), "reasoning_tokens")),
        cache_read_tokens=as_int(field(input_details, "cached_tokens")),
        cache_write_tokens=as_int(field(input_details, "cache_write_tokens")),
    )


def _read_responses_result(recorder: CallRecorder, response: Any) -> None:
    _record_responses_usage(recorder, field(response, "usage"))


def _observe_responses_event(recorder: CallRecorder, event: Any) -> None:
    kind = field(event, "type")
    if kind == "response.output_text.delta":
        recorder.first_token()
    elif kind == "response.completed":
        _record_responses_usage(recorder, field(field(event, "response"), "usage"))


def _record_chat_usage(recorder: CallRecorder, usage: Any) -> None:
    prompt_details = field(usage, "prompt_tokens_details")
    recorder.update_usage(
        input_tokens=as_int(field(usage, "prompt_tokens")),
        output_tokens=as_int(field(usage, "completion_tokens")),
        reasoning_tokens=as_int(
            field(field(usage, "completion_tokens_details"), "reasoning_tokens")
        ),
        cache_read_tokens=as_int(field(prompt_details, "cached_tokens")),
        cache_write_tokens=as_int(field(prompt_details, "cache_write_tokens")),
    )


def _read_chat_result(recorder: CallRecorder, completion: Any) -> None:
    _record_chat_usage(recorder, field(completion, "usage"))


def _observe_chat_chunk(recorder: CallRecorder, chunk: Any) -> None:
    choices = field(chunk, "choices") or []
    if choices and field(field(choices[0], "delta"), "content"):
        recorder.first_token()
    usage = field(chunk, "usage")
    if usage is not None:
        _record_chat_usage(recorder, usage)
