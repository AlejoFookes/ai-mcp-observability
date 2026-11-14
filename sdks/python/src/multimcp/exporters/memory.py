import threading
from collections import deque
from collections.abc import Sequence

from multimcp.exporters.base import Event


class MemoryExporter:
    """Keeps events in process. With `maxlen`, the oldest events are dropped first."""

    def __init__(self, maxlen: int | None = None) -> None:
        self._events: deque[Event] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def insert(self, events: Sequence[Event]) -> None:
        with self._lock:
            self._events.extend(events)

    @property
    def events(self) -> list[Event]:
        with self._lock:
            return list(self._events)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
