import os
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from uuid import uuid4

ENVIRONMENT_VARIABLE = "MULTIMCP_ENVIRONMENT"
DEFAULT_ENVIRONMENT = "local"

_prompt_version: ContextVar[str | None] = ContextVar("multimcp_prompt_version", default=None)
_environment: ContextVar[str | None] = ContextVar("multimcp_environment", default=None)
_trace_id: ContextVar[str | None] = ContextVar("multimcp_trace_id", default=None)


@dataclass(frozen=True, slots=True)
class CallContext:
    prompt_version: str | None
    environment: str
    trace_id: str


@contextmanager
def prompt_context(
    *,
    prompt_version: str | None = None,
    environment: str | None = None,
    trace_id: str | None = None,
) -> Iterator[None]:
    """Tag every instrumented call inside the block. Unset arguments inherit the outer block."""
    tokens = []
    if prompt_version is not None:
        tokens.append((_prompt_version, _prompt_version.set(prompt_version)))
    if environment is not None:
        tokens.append((_environment, _environment.set(environment)))
    if trace_id is not None:
        tokens.append((_trace_id, _trace_id.set(trace_id)))
    try:
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)


def current_context() -> CallContext:
    """Resolve the context for one call. Without a trace_id in scope, each call gets a new one."""
    return CallContext(
        prompt_version=_prompt_version.get(),
        environment=_environment.get()
        or os.environ.get(ENVIRONMENT_VARIABLE)
        or DEFAULT_ENVIRONMENT,
        trace_id=_trace_id.get() or str(uuid4()),
    )
