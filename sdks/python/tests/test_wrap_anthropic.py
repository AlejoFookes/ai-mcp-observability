import asyncio
from decimal import Decimal
from types import SimpleNamespace as NS

import pytest

from multimcp import wrap_anthropic


class FakeOverloaded(Exception):
    pass


RAW_EVENTS = [
    NS(type="message_start", message=NS(usage=NS(input_tokens=10, output_tokens=1))),
    NS(type="content_block_start"),
    NS(type="content_block_delta", delta=NS(type="text_delta", text="Hi")),
    NS(type="message_delta", usage=NS(output_tokens=25, input_tokens=None)),
    NS(type="message_stop"),
]

HELPER_EVENTS = [
    NS(type="message_start"),
    NS(type="text", text="Hi", snapshot="Hi"),
    NS(type="text", text=" there", snapshot="Hi there"),
    NS(type="message_stop"),
]

SNAPSHOT = NS(usage=NS(input_tokens=12, output_tokens=7, cache_read_input_tokens=None))


class FakeMessageStream:
    current_message_snapshot = SNAPSHOT

    def __iter__(self):
        return iter(HELPER_EVENTS)

    async def __aiter__(self):
        for event in HELPER_EVENTS:
            yield event

    def get_final_message(self):
        return NS(usage=SNAPSHOT.usage)


class FakeManager:
    def __init__(self):
        self.exited = False

    def __enter__(self):
        return FakeMessageStream()

    def __exit__(self, *exc):
        self.exited = True

    async def __aenter__(self):
        return FakeMessageStream()

    async def __aexit__(self, *exc):
        self.exited = True


class Messages:
    def __init__(self, respond):
        self.respond = respond
        self.manager = FakeManager()

    def create(self, **kwargs):
        return self.respond(kwargs)

    def stream(self, **kwargs):
        return self.manager


class AsyncMessages(Messages):
    async def create(self, **kwargs):
        return self.respond(kwargs)


class AsyncRaw:
    async def __aiter__(self):
        for event in RAW_EVENTS:
            yield event


def test_unary_folds_cache_reads_into_input(events):
    message = NS(usage=NS(input_tokens=100, output_tokens=50, cache_read_input_tokens=300))
    client = wrap_anthropic(NS(messages=Messages(lambda kw: message)))

    assert client.messages.create(model="claude-sonnet-5-5", max_tokens=10, messages=[]) is message

    (event,) = events.events
    assert (event.provider, event.operation) == ("anthropic", "messages.create")
    assert (event.input_tokens, event.cache_read_tokens, event.output_tokens) == (400, 300, 50)
    # 100 * 2 + 300 * 0.10 + 50 * 10 = 730 per million
    assert event.estimated_cost_usd == Decimal("0.00073000")
    assert event.ttft_ms is None


def test_cache_writes_make_the_call_unpriced(events):
    message = NS(usage=NS(input_tokens=100, output_tokens=50, cache_creation_input_tokens=20))
    client = wrap_anthropic(NS(messages=Messages(lambda kw: message)))

    client.messages.create(model="claude-sonnet-5-5", max_tokens=10, messages=[])

    (event,) = events.events
    assert (event.input_tokens, event.cache_write_tokens) == (120, 20)
    assert (event.price_status, event.estimated_cost_usd) == ("unpriced", None)


def test_raw_stream_reads_start_and_cumulative_delta_usage(events):
    client = wrap_anthropic(NS(messages=Messages(lambda kw: iter(RAW_EVENTS))))

    received = list(client.messages.create(model="claude-opus-5-5", messages=[], stream=True))

    assert received == RAW_EVENTS
    (event,) = events.events
    assert event.ttft_ms is not None
    assert (event.input_tokens, event.output_tokens) == (10, 25)
    assert event.price_status == "priced"


def test_async_raw_stream(events):
    client = wrap_anthropic(NS(messages=AsyncMessages(lambda kw: AsyncRaw())))

    async def main():
        stream = await client.messages.create(model="claude-opus-5-5", messages=[], stream=True)
        return [event async for event in stream]

    assert asyncio.run(main()) == RAW_EVENTS
    (event,) = events.events
    assert (event.input_tokens, event.output_tokens) == (10, 25)


def test_stream_helper_text_stream_and_snapshot_usage(events):
    messages = Messages(lambda kw: None)
    client = wrap_anthropic(NS(messages=messages))

    with client.messages.stream(model="claude-haiku-5-5", messages=[]) as stream:
        texts = list(stream.text_stream)

    assert texts == ["Hi", " there"]
    assert messages.manager.exited
    (event,) = events.events
    assert event.operation == "messages.stream"
    assert event.ttft_ms is not None
    assert (event.input_tokens, event.output_tokens) == (12, 7)
    assert event.price_status == "priced"


def test_stream_helper_final_message_without_iterating(events):
    client = wrap_anthropic(NS(messages=Messages(lambda kw: None)))

    with client.messages.stream(model="claude-haiku-5-5", messages=[]) as stream:
        final = stream.get_final_message()

    assert final.usage.output_tokens == 7
    (event,) = events.events
    assert event.ttft_ms is None
    assert event.output_tokens == 7


def test_async_stream_helper(events):
    client = wrap_anthropic(NS(messages=AsyncMessages(lambda kw: None)))

    async def main():
        async with client.messages.stream(model="claude-haiku-5-5", messages=[]) as stream:
            return [text async for text in stream.text_stream]

    assert asyncio.run(main()) == ["Hi", " there"]
    (event,) = events.events
    assert event.ttft_ms is not None
    assert event.input_tokens == 12


def test_error_is_reraised(events):
    error = FakeOverloaded("overloaded")

    def fail(kwargs):
        raise error

    client = wrap_anthropic(NS(messages=Messages(fail)))

    with pytest.raises(FakeOverloaded) as caught:
        client.messages.create(model="claude-opus-5-5", messages=[])

    assert caught.value is error
    (event,) = events.events
    assert (event.status, event.error_type) == ("error", "FakeOverloaded")


def test_error_inside_stream_helper_block_is_recorded_and_propagates(events):
    client = wrap_anthropic(NS(messages=Messages(lambda kw: None)))

    manager = client.messages.stream(model="claude-opus-5-5", messages=[])
    with pytest.raises(FakeOverloaded), manager:
        raise FakeOverloaded("connection dropped")

    (event,) = events.events
    assert (event.status, event.error_type) == ("error", "FakeOverloaded")
