import atexit
import logging
import os
import threading
from collections import deque
from collections.abc import Sequence

import httpx

from multimcp.exporters.base import Event
from multimcp.models import SCHEMA_VERSION, GenAIEvent, McpEvent

logger = logging.getLogger("multimcp")

INGEST_URL_VARIABLE = "MULTIMCP_INGEST_URL"
INGEST_TOKEN_VARIABLE = "MULTIMCP_INGEST_TOKEN"
DEFAULT_INGEST_URL = "http://localhost:8000"

GENAI_PATH = "/api/v1/events"
MCP_PATH = "/api/v1/mcp-events"


class HttpExporter:
    """Buffers events and posts them to the ingest API from a background thread.

    Fail-open: a failed POST is logged and its batch is dropped. Nothing is retried, and the
    caller's thread never waits on the network. When the buffer is full the oldest events go first.
    """

    def __init__(
        self,
        *,
        url: str | None = None,
        token: str | None = None,
        timeout: float = 2.0,
        batch_size: int = 100,
        buffer_size: int = 1000,
        flush_interval: float = 1.0,
        transport: httpx.BaseTransport | None = None,
        background: bool = True,
    ) -> None:
        if not 1 <= batch_size <= buffer_size:
            raise ValueError("batch_size must be between 1 and buffer_size")
        token = token if token is not None else os.environ.get(INGEST_TOKEN_VARIABLE)
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._client = httpx.Client(
            base_url=url or os.environ.get(INGEST_URL_VARIABLE) or DEFAULT_INGEST_URL,
            headers=headers,
            timeout=timeout,
            transport=transport,
        )
        self._batch_size = batch_size
        self._buffer: deque[Event] = deque(maxlen=buffer_size)
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stopped = threading.Event()
        self._flush_interval = flush_interval
        self._thread: threading.Thread | None = None
        if background:
            self._thread = threading.Thread(
                target=self._run, name="multimcp-http-exporter", daemon=True
            )
            self._thread.start()
            atexit.register(self.close)

    def insert(self, events: Sequence[Event]) -> None:
        with self._lock:
            overflow = len(self._buffer) + len(events) - (self._buffer.maxlen or 0)
            self._buffer.extend(events)
            pending = len(self._buffer)
        if overflow > 0:
            logger.warning("multimcp: telemetry buffer full, dropped %d oldest events", overflow)
        if pending >= self._batch_size:
            self._wake.set()

    def flush(self) -> None:
        """Post everything buffered now, in batches, from the calling thread."""
        while batch := self._take_batch():
            self._post(batch)

    def close(self) -> None:
        if self._stopped.is_set():
            return
        self._stopped.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self.flush()
        self._client.close()

    def _take_batch(self) -> list[Event]:
        with self._lock:
            count = min(self._batch_size, len(self._buffer))
            return [self._buffer.popleft() for _ in range(count)]

    def _post(self, batch: list[Event]) -> None:
        for path, events in (
            (GENAI_PATH, [e for e in batch if isinstance(e, GenAIEvent)]),
            (MCP_PATH, [e for e in batch if isinstance(e, McpEvent)]),
        ):
            if not events:
                continue
            body = {
                "schema_version": SCHEMA_VERSION,
                "events": [event.model_dump(mode="json") for event in events],
            }
            try:
                self._client.post(path, json=body).raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning(
                    "multimcp: dropped %d events, POST %s failed: %s",
                    len(events), path, type(exc).__name__,
                )

    def _run(self) -> None:
        while not self._stopped.is_set():
            self._wake.wait(self._flush_interval)
            self._wake.clear()
            try:
                self.flush()
            except Exception:
                logger.exception("multimcp: telemetry flush failed, batch dropped")
