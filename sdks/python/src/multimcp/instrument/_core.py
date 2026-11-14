"""Provider-agnostic call recording. Provider objects are untyped here on purpose: `Any` stays
inside the instrument package, at the edge of the external SDKs."""

import functools
import inspect
import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import Any

from multimcp.config import emit, get_catalog
from multimcp.context import current_context
from multimcp.exporters.base import Exporter
from multimcp.models import GenAIEvent, MetadataValue, Operation, Provider
from multimcp.pricing.estimator import estimate_cost

logger = logging.getLogger("multimcp")

WRAPPED_MARKER = "__multimcp_wrapped__"


@dataclass(frozen=True, slots=True)
class Usage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class Instrumentation:
    provider: Provider
    exporter: Exporter | None
    metadata: Mapping[str, MetadataValue]


def field(obj: Any, name: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)


def as_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def add(*values: int | None) -> int | None:
    present = [v for v in values if v is not None]
    return sum(present) if present else None


class CallRecorder:
    """Measures one call and emits exactly one event. Never raises into the caller."""

    def __init__(
        self,
        inst: Instrumentation,
        *,
        operation: Operation,
        model: Any,
        streaming: bool,
    ) -> None:
        self._inst = inst
        self._operation = operation
        self._model = model if isinstance(model, str) and model else "unknown"
        self._streaming = streaming
        self._context = current_context()
        self._started = time.perf_counter()
        self._ttft_ms: float | None = None
        self._finished = False
        self.usage = Usage()
        self.raw_usage: dict[str, int] = {}

    def first_token(self) -> None:
        if self._streaming and self._ttft_ms is None:
            self._ttft_ms = (time.perf_counter() - self._started) * 1000

    def update_usage(self, **fields: int | None) -> None:
        changes = {k: v for k, v in fields.items() if v is not None}
        if changes:
            self.usage = replace(self.usage, **changes)

    def observe(self, observer: Callable[["CallRecorder", Any], None], item: Any) -> None:
        try:
            observer(self, item)
        except Exception:
            logger.exception("multimcp: could not read telemetry from a %s item", self._operation)

    def finish(self, error: BaseException | None = None) -> None:
        if self._finished:
            return
        self._finished = True
        latency_ms = (time.perf_counter() - self._started) * 1000
        try:
            usage = self.usage
            estimate = estimate_cost(
                get_catalog(),
                provider=self._inst.provider,
                model=self._model,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_read_tokens=usage.cache_read_tokens,
                cache_write_tokens=usage.cache_write_tokens,
            )
            event = GenAIEvent(
                environment=self._context.environment,
                trace_id=self._context.trace_id,
                prompt_version=self._context.prompt_version,
                provider=self._inst.provider,
                model=self._model,
                operation=self._operation,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                reasoning_tokens=usage.reasoning_tokens,
                cache_read_tokens=usage.cache_read_tokens,
                cache_write_tokens=usage.cache_write_tokens,
                ttft_ms=self._ttft_ms,
                latency_ms=latency_ms,
                estimated_cost_usd=estimate.estimated_cost_usd,
                catalog_version=estimate.catalog_version,
                price_status=estimate.price_status,
                status="error" if error is not None else "ok",
                error_type=type(error).__name__ if error is not None else None,
                metadata=dict(self._inst.metadata),
            )
        except Exception:
            logger.exception("multimcp: could not build the %s event", self._operation)
            return
        emit(event, self._inst.exporter)


Observer = Callable[[CallRecorder, Any], None]


class SyncStream:
    """Iterates the provider stream unchanged and records the call when it ends.

    With `finishes_call=False` an outer context manager owns the recording instead."""

    def __init__(
        self,
        inner: Any,
        recorder: CallRecorder,
        observer: Observer,
        *,
        finishes_call: bool = True,
    ) -> None:
        self._inner = inner
        self._recorder = recorder
        self._observer = observer
        self._finishes_call = finishes_call
        self._iterator: Any = None

    def _finish(self, error: BaseException | None = None) -> None:
        if self._finishes_call:
            self._recorder.finish(error)

    def __iter__(self) -> "SyncStream":
        return self

    def __next__(self) -> Any:
        if self._iterator is None:
            self._iterator = iter(self._inner)
        try:
            item = next(self._iterator)
        except StopIteration:
            self._finish()
            raise
        except Exception as exc:
            self._finish(exc)
            raise
        self._recorder.observe(self._observer, item)
        return item

    def __enter__(self) -> "SyncStream":
        enter = getattr(self._inner, "__enter__", None)
        if enter is not None:
            enter()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> Any:
        try:
            exit_ = getattr(self._inner, "__exit__", None)
            return exit_(exc_type, exc, tb) if exit_ is not None else None
        finally:
            self._finish(exc if isinstance(exc, Exception) else None)

    def close(self) -> None:
        try:
            close = getattr(self._inner, "close", None)
            if close is not None:
                close()
        finally:
            self._finish()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class AsyncStream:
    def __init__(
        self,
        inner: Any,
        recorder: CallRecorder,
        observer: Observer,
        *,
        finishes_call: bool = True,
    ) -> None:
        self._inner = inner
        self._recorder = recorder
        self._observer = observer
        self._finishes_call = finishes_call
        self._iterator: Any = None

    def _finish(self, error: BaseException | None = None) -> None:
        if self._finishes_call:
            self._recorder.finish(error)

    def __aiter__(self) -> "AsyncStream":
        return self

    async def __anext__(self) -> Any:
        if self._iterator is None:
            self._iterator = self._inner.__aiter__()
        try:
            item = await self._iterator.__anext__()
        except StopAsyncIteration:
            self._finish()
            raise
        except Exception as exc:
            self._finish(exc)
            raise
        self._recorder.observe(self._observer, item)
        return item

    async def __aenter__(self) -> "AsyncStream":
        enter = getattr(self._inner, "__aenter__", None)
        if enter is not None:
            await enter()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> Any:
        try:
            exit_ = getattr(self._inner, "__aexit__", None)
            return await exit_(exc_type, exc, tb) if exit_ is not None else None
        finally:
            self._finish(exc if isinstance(exc, Exception) else None)

    async def close(self) -> None:
        try:
            close = getattr(self._inner, "aclose", None) or getattr(self._inner, "close", None)
            if close is not None:
                result = close()
                if inspect.isawaitable(result):
                    await result
        finally:
            self._finish()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def instrument_call(
    original: Callable[..., Any],
    inst: Instrumentation,
    *,
    operation: Operation,
    read_usage: Callable[[CallRecorder, Any], None],
    observe_item: Observer,
    always_streams: bool = False,
) -> Callable[..., Any]:
    """Wrap a create-style method: unary results are read once, stream results are proxied."""

    def start(kwargs: dict[str, Any]) -> tuple[CallRecorder, bool]:
        streaming = always_streams or kwargs.get("stream") is True
        recorder = CallRecorder(
            inst, operation=operation, model=kwargs.get("model"), streaming=streaming
        )
        return recorder, streaming

    async def complete_async(pending: Any, recorder: CallRecorder, streaming: bool) -> Any:
        try:
            result = await pending
        except Exception as exc:
            recorder.finish(exc)
            raise
        if streaming:
            return AsyncStream(result, recorder, observe_item)
        recorder.observe(read_usage, result)
        recorder.finish()
        return result

    if inspect.iscoroutinefunction(original):

        @functools.wraps(original)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            recorder, streaming = start(kwargs)
            try:
                pending = original(*args, **kwargs)
            except Exception as exc:
                recorder.finish(exc)
                raise
            return await complete_async(pending, recorder, streaming)

        return mark_wrapped(async_wrapper)

    @functools.wraps(original)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        recorder, streaming = start(kwargs)
        try:
            result = original(*args, **kwargs)
        except Exception as exc:
            recorder.finish(exc)
            raise
        # Some SDK async methods sit behind a plain-def decorator and hand back a coroutine.
        if inspect.isawaitable(result):
            return complete_async(result, recorder, streaming)
        if streaming:
            return SyncStream(result, recorder, observe_item)
        recorder.observe(read_usage, result)
        recorder.finish()
        return result

    return mark_wrapped(sync_wrapper)


def mark_wrapped(function: Callable[..., Any]) -> Callable[..., Any]:
    setattr(function, WRAPPED_MARKER, True)
    return function


def patch_method(
    resource: Any, name: str, build: Callable[[Callable[..., Any]], Callable[..., Any]]
) -> None:
    """Replace `resource.name` on this instance only. Wrapping twice is a no-op."""
    original = getattr(resource, name, None)
    if original is None or getattr(original, WRAPPED_MARKER, False):
        return
    setattr(resource, name, build(original))
