"""Storage readiness probe. Wraps EventRepository.ping when available."""

from __future__ import annotations

from typing import Protocol

from multimcp_api.repositories.base import EventRepository


class HealthProbe(Protocol):
    async def ping(self) -> bool:
        """Return True when storage answers a trivial check."""


class AlwaysOkProbe:
    """Default for tests that do not care about storage."""

    async def ping(self) -> bool:
        return True


class AlwaysDownProbe:
    """Test double for degraded / ready=false paths."""

    async def ping(self) -> bool:
        return False


class RepositoryHealthProbe:
    """Delegates to EventRepository.ping (SELECT 1 on Postgres)."""

    def __init__(self, repository: EventRepository) -> None:
        self._repository = repository

    async def ping(self) -> bool:
        return await self._repository.ping()
