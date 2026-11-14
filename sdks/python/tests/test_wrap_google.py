import asyncio
from types import SimpleNamespace as NS

import pytest

from multimcp import MultimcpConfigError, wrap_google


class FakeClientError(Exception):
    pass


USAGE = NS(
    prompt_token_count=100,
    candidates_token_count=40,
    thoughts_token_count=10,
    cached_content_token_count=30,
)


def chunk(text, usage=None):
    return NS(candidates=[NS(content=NS(parts=[NS(text=text)]))], usage_metadata=usage)


CHUNKS = [chunk(""), chunk("Hel"), chunk("lo", USAGE)]


class Models:
    def __init__(self, respond=None):
        self.respond = respond

    def generate_content(self, *, model, contents, config=None):
        if self.respond:
            return self.respond()
        return NS(usage_metadata=USAGE, text="Hello")

    def generate_content_stream(self, *, model, contents, config=None):
        return iter(CHUNKS)


class AsyncModels:
    async def generate_content(self, *, model, contents, config=None):
        return NS(usage_metadata=USAGE)

    async def generate_content_stream(self, *, model, contents, config=None):
        async def chunks():
            for item in CHUNKS:
                yield item

        return chunks()


def make_client(models=None):
    return NS(models=models or Models(), aio=NS(models=AsyncModels()), vertexai=False)


def test_generate_content_maps_thoughts_into_output(events):
    client = wrap_google(make_client())

    client.models.generate_content(model="gemini-3.8-flash", contents="hi")

    (event,) = events.events
    assert (event.provider, event.operation) == ("google", "models.generate_content")
    assert (event.input_tokens, event.output_tokens) == (100, 50)
    assert (event.reasoning_tokens, event.cache_read_tokens) == (10, 30)
    assert event.ttft_ms is None


def test_google_calls_are_unpriced_until_the_catalog_has_rows(events):
    client = wrap_google(make_client())

    client.models.generate_content(model="models/gemini-3.8-flash", contents="hi")

    (event,) = events.events
    assert (event.price_status, event.estimated_cost_usd) == ("unpriced", None)
    assert event.catalog_version == "2026-11-01"
    assert event.model == "models/gemini-3.8-flash"


def test_generate_content_stream_measures_ttft_on_first_text(events):
    client = wrap_google(make_client())

    received = list(client.models.generate_content_stream(model="gemini-3.8-flash", contents="hi"))

    assert received == CHUNKS
    (event,) = events.events
    assert event.ttft_ms is not None
    assert event.output_tokens == 50


def test_aio_models_are_instrumented(events):
    client = wrap_google(make_client())

    async def main():
        await client.aio.models.generate_content(model="gemini-3.8-flash", contents="hi")
        stream = await client.aio.models.generate_content_stream(
            model="gemini-3.8-flash", contents="hi"
        )
        return [item async for item in stream]

    assert asyncio.run(main()) == CHUNKS
    unary, streamed = events.events
    assert unary.ttft_ms is None
    assert streamed.ttft_ms is not None
    assert streamed.input_tokens == 100


def test_enterprise_client_is_rejected():
    with pytest.raises(MultimcpConfigError, match="enterprise"):
        wrap_google(NS(models=Models(), vertexai=True))


def test_error_is_reraised(events):
    error = FakeClientError("quota")

    def fail():
        raise error

    client = wrap_google(make_client(Models(respond=fail)))

    with pytest.raises(FakeClientError) as caught:
        client.models.generate_content(model="gemini-3.8-flash", contents="hi")

    assert caught.value is error
    (event,) = events.events
    assert (event.status, event.error_type) == ("error", "FakeClientError")
