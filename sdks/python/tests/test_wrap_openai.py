import asyncio
from decimal import Decimal
from types import SimpleNamespace as NS

import pytest

from multimcp import MemoryExporter, prompt_context, wrap_openai


class FakeAPIError(Exception):
    pass


class FakeStream:
    def __init__(self, items, fail_at=None):
        self.items = items
        self.fail_at = fail_at
        self.closed = False

    def __iter__(self):
        for index, item in enumerate(self.items):
            if index == self.fail_at:
                raise FakeAPIError("stream broke")
            yield item

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.closed = True

    def close(self):
        self.closed = True


class FakeAsyncStream:
    def __init__(self, items):
        self.items = items

    async def __aiter__(self):
        for item in self.items:
            yield item


class Resource:
    def __init__(self, respond):
        self.respond = respond
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.respond(kwargs)


class AsyncResource(Resource):
    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.respond(kwargs)


def make_client(responses=None, chat=None, resource=Resource):
    def unavailable(kwargs):
        raise AssertionError("not configured")

    return NS(
        responses=resource(responses or unavailable),
        chat=NS(completions=resource(chat or unavailable)),
    )


RESPONSES_USAGE = NS(
    input_tokens=1000,
    output_tokens=500,
    input_tokens_details=NS(cached_tokens=200),
    output_tokens_details=NS(reasoning_tokens=100),
)

RESPONSES_EVENTS = [
    NS(type="response.created"),
    NS(type="response.output_text.delta", delta="Hel"),
    NS(type="response.output_text.delta", delta="lo"),
    NS(type="response.completed", response=NS(usage=RESPONSES_USAGE)),
]


def test_responses_unary_records_usage_and_cost(events):
    response = NS(usage=RESPONSES_USAGE, output_text="Hello")
    client = wrap_openai(make_client(responses=lambda kw: response))

    result = client.responses.create(model="gpt-5.5", input="hi")

    assert result is response
    (event,) = events.events
    assert (event.provider, event.model) == ("openai", "gpt-5.5")
    assert event.operation == "responses.create"
    assert (event.input_tokens, event.output_tokens) == (1000, 500)
    assert (event.cache_read_tokens, event.reasoning_tokens) == (200, 100)
    # 800 * 5.00 + 200 * 0.50 + 500 * 30.00 = 19100 per million
    assert event.estimated_cost_usd == Decimal("0.01910000")
    assert (event.price_status, event.catalog_version) == ("priced", "2026-11-01")
    assert event.status == "ok"
    assert event.ttft_ms is None
    assert event.latency_ms >= 0
    assert event.environment == "test"


def test_responses_stream_measures_ttft_and_reads_completed_usage(events):
    stream = FakeStream(RESPONSES_EVENTS)
    client = wrap_openai(make_client(responses=lambda kw: stream))

    with client.responses.create(model="gpt-5.5", input="hi", stream=True) as wrapped:
        received = list(wrapped)

    assert received == RESPONSES_EVENTS
    assert stream.closed
    (event,) = events.events
    assert event.ttft_ms is not None
    assert 0 <= event.ttft_ms <= event.latency_ms
    assert (event.input_tokens, event.output_tokens) == (1000, 500)
    assert event.price_status == "priced"


def test_async_responses_unary_and_stream(events):
    client = wrap_openai(
        make_client(
            responses=lambda kw: FakeAsyncStream(RESPONSES_EVENTS)
            if kw.get("stream")
            else NS(usage=RESPONSES_USAGE),
            resource=AsyncResource,
        )
    )

    async def main():
        await client.responses.create(model="gpt-5.5", input="hi")
        stream = await client.responses.create(model="gpt-5.5", input="hi", stream=True)
        return [item async for item in stream]

    assert asyncio.run(main()) == RESPONSES_EVENTS
    unary, streamed = events.events
    assert unary.ttft_ms is None
    assert streamed.ttft_ms is not None
    assert streamed.output_tokens == 500


def test_async_method_behind_a_plain_def_decorator(events):
    class DecoratedAsync(Resource):
        def create(self, **kwargs):
            async def call():
                await asyncio.sleep(0.01)
                return self.respond(kwargs)

            return call()

    completion = NS(usage=NS(prompt_tokens=5, completion_tokens=2))
    client = wrap_openai(make_client(chat=lambda kw: completion, resource=DecoratedAsync))

    result = asyncio.run(client.chat.completions.create(model="gpt-4o", messages=[]))

    assert result.usage.prompt_tokens == 5
    (event,) = events.events
    assert (event.input_tokens, event.output_tokens) == (5, 2)
    assert event.latency_ms >= 10


def test_chat_unary(events):
    completion = NS(
        usage=NS(
            prompt_tokens=50,
            completion_tokens=20,
            prompt_tokens_details=NS(cached_tokens=0),
            completion_tokens_details=NS(reasoning_tokens=5),
        )
    )
    client = wrap_openai(make_client(chat=lambda kw: completion))

    assert client.chat.completions.create(model="gpt-4o-mini", messages=[]) is completion

    (event,) = events.events
    assert event.operation == "chat.completions.create"
    assert (event.input_tokens, event.output_tokens, event.reasoning_tokens) == (50, 20, 5)
    assert event.price_status == "priced"


def test_chat_stream_copies_final_usage_chunk(events):
    chunks = [
        NS(choices=[NS(delta=NS(role="assistant", content=None))], usage=None),
        NS(choices=[NS(delta=NS(content="Hi"))], usage=None),
        NS(choices=[], usage=NS(prompt_tokens=10, completion_tokens=3)),
    ]
    client = wrap_openai(make_client(chat=lambda kw: FakeStream(chunks)))

    assert list(client.chat.completions.create(model="gpt-4o", messages=[], stream=True)) == chunks

    (event,) = events.events
    assert event.ttft_ms is not None
    assert (event.input_tokens, event.output_tokens) == (10, 3)
    assert "stream_options" not in client.chat.completions.calls[0]


def test_chat_stream_without_usage_is_unpriced(events):
    chunks = [NS(choices=[NS(delta=NS(content="Hi"))], usage=None)]
    client = wrap_openai(make_client(chat=lambda kw: FakeStream(chunks)))

    list(client.chat.completions.create(model="gpt-4o", messages=[], stream=True))

    (event,) = events.events
    assert event.input_tokens is None
    assert (event.price_status, event.estimated_cost_usd) == ("unpriced", None)


def test_sdk_error_is_reraised_unchanged_after_recording(events):
    error = FakeAPIError("rate limited")

    def fail(kwargs):
        raise error

    client = wrap_openai(make_client(responses=fail))

    with pytest.raises(FakeAPIError) as caught:
        client.responses.create(model="gpt-5.5", input="hi")

    assert caught.value is error
    (event,) = events.events
    assert (event.status, event.error_type) == ("error", "FakeAPIError")
    assert event.price_status == "unpriced"


def test_error_mid_stream_is_reraised_and_recorded(events):
    client = wrap_openai(make_client(responses=lambda kw: FakeStream(RESPONSES_EVENTS, fail_at=2)))

    with pytest.raises(FakeAPIError):
        list(client.responses.create(model="gpt-5.5", input="hi", stream=True))

    (event,) = events.events
    assert (event.status, event.error_type) == ("error", "FakeAPIError")
    assert event.ttft_ms is not None


def test_abandoned_stream_records_once_on_close(events):
    stream = FakeStream(RESPONSES_EVENTS)
    client = wrap_openai(make_client(responses=lambda kw: stream))

    wrapped = client.responses.create(model="gpt-5.5", input="hi", stream=True)
    next(iter(wrapped))
    wrapped.close()
    wrapped.close()

    assert stream.closed
    (event,) = events.events
    assert event.status == "ok"
    assert event.input_tokens is None


def test_wrapping_twice_emits_one_event(events):
    client = make_client(responses=lambda kw: NS(usage=RESPONSES_USAGE))
    wrap_openai(wrap_openai(client))

    client.responses.create(model="gpt-5.5", input="hi")

    assert len(events.events) == 1


def test_only_the_wrapped_instance_is_instrumented(events):
    wrapped = wrap_openai(make_client(responses=lambda kw: NS(usage=RESPONSES_USAGE)))
    plain = make_client(responses=lambda kw: NS(usage=RESPONSES_USAGE))

    plain.responses.create(model="gpt-5.5", input="hi")
    assert events.events == []
    wrapped.responses.create(model="gpt-5.5", input="hi")
    assert len(events.events) == 1


def test_context_metadata_and_client_exporter(events):
    own = MemoryExporter()
    client = wrap_openai(
        make_client(responses=lambda kw: NS(usage=RESPONSES_USAGE)),
        exporter=own,
        metadata={"role": "judge", "rubric_version": "rag-judge-1.0"},
    )

    with prompt_context(prompt_version="checkout-v3", environment="staging", trace_id="trace-7"):
        client.responses.create(model="gpt-5.5", input="hi")

    assert events.events == []
    (event,) = own.events
    assert (event.prompt_version, event.environment, event.trace_id) == (
        "checkout-v3", "staging", "trace-7",
    )
    assert event.metadata == {"role": "judge", "rubric_version": "rag-judge-1.0"}


def test_telemetry_failures_never_reach_the_caller(events, caplog):
    class Broken:
        def insert(self, batch):
            raise RuntimeError("exporter down")

    weird = NS(usage=NS(input_tokens="many", output_tokens=None))
    client = wrap_openai(make_client(responses=lambda kw: weird), exporter=Broken())

    assert client.responses.create(model="gpt-5.5", input="hi") is weird
    assert "exporter failed" in caplog.text


def test_unknown_model_is_unpriced(events):
    client = wrap_openai(make_client(responses=lambda kw: NS(usage=RESPONSES_USAGE)))

    client.responses.create(model="gpt-5.5-2026-09-01", input="hi")

    (event,) = events.events
    assert (event.price_status, event.estimated_cost_usd) == ("unpriced", None)
