from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

from multimcp.models import PriceStatus, Provider
from multimcp.pricing.catalog import PriceCatalog

_QUANTUM = Decimal("0.00000001")
_MILLION = Decimal(1_000_000)


@dataclass(frozen=True, slots=True)
class PriceEstimate:
    estimated_cost_usd: Decimal | None
    price_status: PriceStatus
    catalog_version: str


def estimate_cost(
    catalog: PriceCatalog,
    *,
    provider: Provider,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
    cache_read_tokens: int | None = None,
    cache_write_tokens: int | None = None,
) -> PriceEstimate:
    """Price one call, or mark it unpriced. Never returns a partial estimate."""
    unpriced = PriceEstimate(None, "unpriced", catalog.catalog_version)

    entry = catalog.find(provider, model)
    if entry is None or input_tokens is None or output_tokens is None:
        return unpriced
    if entry.max_input_tokens is not None and input_tokens > entry.max_input_tokens:
        return unpriced
    if cache_write_tokens:
        return unpriced

    cache_read = cache_read_tokens or 0
    if cache_read > input_tokens:
        return unpriced
    if cache_read and entry.cache_read_per_million is None:
        return unpriced

    total = (
        (input_tokens - cache_read) * entry.input_per_million
        + cache_read * (entry.cache_read_per_million or Decimal(0))
        + output_tokens * entry.output_per_million
    )
    cost = (total / _MILLION).quantize(_QUANTUM, rounding=ROUND_HALF_EVEN)
    return PriceEstimate(cost, "priced", catalog.catalog_version)
