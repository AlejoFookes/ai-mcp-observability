import functools
import logging
from collections.abc import AsyncIterator, Callable, Iterator, Mapping
from typing import Any

from multimcp.exporters.base import Exporter
from multimcp.instrument._core import (
    AsyncStream,
    CallRecorder,
    Instrumentation,
    SyncStream,
    add,
    as_int,
    field,
    instrument_call,
    mark_wrapped,
    patch_method,
)
from multimcp.models import MetadataValue

logger = logging.getLogger("multimcp")

_USAGE_KEYS = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)


def wrap_anthropic[ClientT](
    client: ClientT,
    *,
    exporter: Exporter | None = None,
    metadata: Mapping[str, MetadataValue] | None = None,
) -> ClientT:
    """Instrument `messages.create` (unary and `stream=True`) and `messages.stream` on an
    Anthropic or AsyncAnthropic client, in place. Returns the same client."""
    inst = Instrumentation("anthropic", exporter, dict(metadata or {}))
    messages = field(client, "messages")
    if messages is None:
        return client
    patch_method(
        messages,
        "create",
        lambda original: instrument_call(
            original,
            inst,
            operation="messages.create",
            read_usage=_read_message,
            observe_item=_observe_raw_event,
        ),
    )
    patch_method(messages, "stream", lambda original: _instrument_stream_helper(original, inst))
    return client


def _record_usage(recorder: CallRecorder, usage: Any) -> None:
    """Anthropic reports cache reads and writes outside `input_tokens`; fold them into the total.
    Usage on `message_delta` is cumulative and may omit fields, so values overwrite, never add."""
    raw = recorder.raw_usage
    for key in _USAGE_KEYS:
        value = as_int(field(usage, key))
        if value is not None:
            raw[key] = value
    cache_read = raw.get("cache_read_input_tokens")
    cache_write = raw.get("cache_creation_input_tokens")
    recorder.update_usage(
        input_tokens=add(raw["input_tokens"], cache_read, cache_write)
        if "input_tokens" in raw
        else None,
        output_tokens=raw.get("output_tokens"),
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
    )


def _read_message(recorder: CallRecorder, message: Any) -> None:
    _record_usage(recorder, field(message, "usage"))


def _observe_raw_event(recorder: CallRecorder, event: Any) -> None:
    kind = field(event, "type")
    if kind == "message_start":
        _record_usage(recorder, field(field(event, "message"), "usage"))
    elif kind == "content_block_delta":
        recorder.first_token()
    elif kind == "message_delta":
        _record_usage(recorder, field(event, "usage"))


def _observe_helper_event(recorder: CallRecorder, event: Any) -> None:
    if field(event, "type") in ("text", "content_block_delta"):
        recorder.first_token()


def _record_snapshot(recorder: CallRecorder, stream: Any) -> None:
    try:
        snapshot = stream.current_message_snapshot
    except Exception as exc:
        logger.debug("multimcp: no message snapshot to read usage from: %s", type(exc).__name__)
        return
    _record_usage(recorder, field(snapshot, "usage"))


def _instrument_stream_helper(
    original: Callable[..., Any], inst: Instrumentation
) -> Callable[..., Any]:
    @functools.wraps(original)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        recorder = CallRecorder(
            inst, operation="messages.stream", model=kwargs.get("model"), streaming=True
        )
        try:
            manager = original(*args, **kwargs)
        except Exception as exc:
            recorder.finish(exc)
            raise
        return _StreamManager(manager, recorder)

    return mark_wrapped(wrapper)


class _StreamManager:
    """Stands in for MessageStreamManager / AsyncMessageStreamManager."""

    def __init__(self, inner: Any, recorder: CallRecorder) -> None:
        self._inner = inner
        self._recorder = recorder
        self._stream: Any = None

    def __enter__(self) -> "_HelperStream":
        try:
            self._stream = self._inner.__enter__()
        except Exception as exc:
            self._recorder.finish(exc)
            raise
        return _HelperStream(self._stream, self._recorder)

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> Any:
        try:
            return self._inner.__exit__(exc_type, exc, tb)
        finally:
            self._finish(exc)

    async def __aenter__(self) -> "_AsyncHelperStream":
        try:
            self._stream = await self._inner.__aenter__()
        except Exception as exc:
            self._recorder.finish(exc)
            raise
        return _AsyncHelperStream(self._stream, self._recorder)

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> Any:
        try:
            return await self._inner.__aexit__(exc_type, exc, tb)
        finally:
            self._finish(exc)

    def _finish(self, exc: Any) -> None:
        if self._stream is not None:
            self._recorder.observe(_record_snapshot, self._stream)
        self._recorder.finish(exc if isinstance(exc, Exception) else None)


class _HelperStream(SyncStream):
    def __init__(self, inner: Any, recorder: CallRecorder) -> None:
        super().__init__(inner, recorder, _observe_helper_event, finishes_call=False)

    @property
    def text_stream(self) -> Iterator[str]:
        for event in self:
            if field(event, "type") == "text":
                yield field(event, "text")


class _AsyncHelperStream(AsyncStream):
    def __init__(self, inner: Any, recorder: CallRecorder) -> None:
        super().__init__(inner, recorder, _observe_helper_event, finishes_call=False)

    @property
    def text_stream(self) -> AsyncIterator[str]:
        return self._texts()

    async def _texts(self) -> AsyncIterator[str]:
        async for event in self:
            if field(event, "type") == "text":
                yield field(event, "text")
