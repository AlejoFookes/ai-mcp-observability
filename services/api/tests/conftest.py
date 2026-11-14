from __future__ import annotations

import pytest

from multimcp_api.health import AlwaysOkProbe
from multimcp_api.main import create_app
from multimcp_api.repositories.memory import MemoryEventRepository
from multimcp_api.settings import Settings, clear_settings_cache


@pytest.fixture(autouse=True)
def _clear_settings() -> None:
    clear_settings_cache()
    yield
    clear_settings_cache()


@pytest.fixture
def settings() -> Settings:
    return Settings(ingest_token="test-token", storage_backend="postgres")


@pytest.fixture
def app(settings: Settings):
    return create_app(
        settings=settings,
        repository=MemoryEventRepository(),
        health_probe=AlwaysOkProbe(),
    )
