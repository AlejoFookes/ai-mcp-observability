import asyncio

from multimcp import current_context, prompt_context


def test_defaults_outside_any_block(monkeypatch):
    monkeypatch.delenv("MULTIMCP_ENVIRONMENT", raising=False)
    ctx = current_context()
    assert ctx.prompt_version is None
    assert ctx.environment == "local"


def test_environment_variable_is_the_fallback(monkeypatch):
    monkeypatch.setenv("MULTIMCP_ENVIRONMENT", "staging")
    assert current_context().environment == "staging"
    with prompt_context(environment="prod"):
        assert current_context().environment == "prod"


def test_each_call_gets_a_new_trace_id_without_one_in_scope():
    assert current_context().trace_id != current_context().trace_id


def test_block_values_apply_and_reset():
    with prompt_context(prompt_version="checkout-v3", trace_id="trace-42"):
        ctx = current_context()
        assert (ctx.prompt_version, ctx.trace_id) == ("checkout-v3", "trace-42")
        assert current_context().trace_id == "trace-42"
    assert current_context().prompt_version is None


def test_nested_blocks_inherit_unset_values():
    with prompt_context(prompt_version="v1", trace_id="outer"), prompt_context(prompt_version="v2"):
        ctx = current_context()
        assert (ctx.prompt_version, ctx.trace_id) == ("v2", "outer")


def test_context_is_isolated_between_tasks():
    async def tagged(version: str) -> str | None:
        with prompt_context(prompt_version=version):
            await asyncio.sleep(0)
            return current_context().prompt_version

    async def main() -> list[str | None]:
        return await asyncio.gather(tagged("a"), tagged("b"))

    assert asyncio.run(main()) == ["a", "b"]
