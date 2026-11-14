"""Storage readiness probe. M3.1 ships a no-op; M3.2 wires Postgres SELECT 1."""

from __future__ import annotations

from typing import Protocol


class HealthProbe(Protocol):
    async def ping(self) -> bool:
        """Return True when storage answers a trivial check."""


class AlwaysOkProbe:
    """Used until a real repository is wired (tests and M3.1 skeleton)."""

    async def ping(self) -> bool:
        return True


class AlwaysDownProbe:
    """Test double for degraded / ready=false paths."""

    async def ping(self) -> bool:
        return False
