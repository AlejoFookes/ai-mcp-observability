import pytest

from multimcp import MemoryExporter, configure


@pytest.fixture
def events(monkeypatch):
    """Route every instrumented call in the test to an in-memory exporter."""
    monkeypatch.delenv("MULTIMCP_INGEST_URL", raising=False)
    monkeypatch.setenv("MULTIMCP_ENVIRONMENT", "test")
    exporter = MemoryExporter()
    configure(exporter=exporter)
    yield exporter
    configure(exporter=None)
