import logging
import os
import threading
from dataclasses import dataclass, field

from multimcp.exporters.base import Event, Exporter
from multimcp.exporters.http import INGEST_URL_VARIABLE, HttpExporter
from multimcp.pricing.catalog import DEFAULT_CATALOG_VERSION, PriceCatalog, load_catalog

logger = logging.getLogger("multimcp")


@dataclass
class _Settings:
    exporter: Exporter | None = None
    catalog_version: str = DEFAULT_CATALOG_VERSION
    lock: threading.Lock = field(default_factory=threading.Lock)


_settings = _Settings()


def configure(
    *,
    exporter: Exporter | None = None,
    catalog_version: str = DEFAULT_CATALOG_VERSION,
) -> None:
    """Set the process-wide exporter and price catalog.

    Without an exporter, events go to an HttpExporter when MULTIMCP_INGEST_URL is set,
    and are discarded otherwise.
    """
    load_catalog(catalog_version)
    with _settings.lock:
        _settings.exporter = exporter
        _settings.catalog_version = catalog_version


def get_catalog() -> PriceCatalog:
    return load_catalog(_settings.catalog_version)


def get_exporter() -> Exporter | None:
    with _settings.lock:
        if _settings.exporter is None and os.environ.get(INGEST_URL_VARIABLE):
            _settings.exporter = HttpExporter()
        return _settings.exporter


def emit(event: Event, exporter: Exporter | None = None) -> None:
    """Hand one event to the exporter. Telemetry failures are logged, never raised."""
    target = exporter or get_exporter()
    if target is None:
        logger.debug("multimcp: no exporter configured, event %s discarded", event.event_id)
        return
    try:
        target.insert([event])
    except Exception:
        logger.exception("multimcp: exporter failed, event %s dropped", event.event_id)
