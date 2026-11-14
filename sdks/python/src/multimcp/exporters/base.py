from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from multimcp.models import GenAIEvent, McpEvent

Event = GenAIEvent | McpEvent


@runtime_checkable
class Exporter(Protocol):
    def insert(self, events: Sequence[Event]) -> None:
        """Accept events without blocking on the network. Must not raise for transport errors."""
        ...
