from decimal import Decimal

import pytest

from multimcp.errors import MultimcpConfigError
from multimcp.pricing import PriceCatalog, estimate_cost, load_catalog
from multimcp.pricing.catalog import DEFAULT_CATALOG_VERSION


def _catalog(**entry_overrides) -> PriceCatalog:
    entry = {
        "provider": "openai",
        "model": "m",
        "input_per_million": "2.50",
        "output_per_million": "10.00",
        "cache_read_per_million": "0.25",
        "source_url": "https://example.com/pricing",
        "retrieved_on": "2026-11-14",
    }
    entry.update(entry_overrides)
    return PriceCatalog.model_validate(
        {"catalog_version": "2026-11-01", "currency": "USD", "entries": [entry]}
    )


def _estimate(catalog: PriceCatalog, **kwargs):
    fields = {"provider": "openai", "model": "m", "input_tokens": 1000, "output_tokens": 500}
    fields.update(kwargs)
    return estimate_cost(catalog, **fields)


def test_bundled_catalog_loads_from_the_package():
    catalog = load_catalog()
    assert catalog.catalog_version == DEFAULT_CATALOG_VERSION == "2026-11-01"
    assert catalog.currency == "USD"
    assert catalog.entries
    assert all(entry.source_url.startswith("https://") for entry in catalog.entries)


def test_bundled_catalog_prices_a_known_model():
    estimate = _estimate(
        load_catalog(), provider="anthropic", model="claude-sonnet-5-5",
        input_tokens=1_000_000, output_tokens=1_000_000,
    )
    assert estimate.price_status == "priced"
    assert estimate.estimated_cost_usd == Decimal("12.00000000")


def test_cost_formula_with_cache_reads():
    estimate = _estimate(_catalog(), input_tokens=1000, output_tokens=500, cache_read_tokens=400)
    # 600 * 2.50 + 400 * 0.25 + 500 * 10.00 = 6600 per million
    assert estimate.estimated_cost_usd == Decimal("0.00660000")
    assert estimate.catalog_version == "2026-11-01"


def test_rounds_half_even_to_eight_decimals():
    catalog = _catalog(input_per_million="0.005", output_per_million="0")
    # 3 tokens * 0.005 / 1e6 = 0.000000015 -> half-even to ...02
    assert _estimate(catalog, input_tokens=3, output_tokens=0).estimated_cost_usd == Decimal(
        "0.00000002"
    )
    # 1 token * 0.005 / 1e6 = 0.000000005 -> half-even to ...00
    assert _estimate(catalog, input_tokens=1, output_tokens=0).estimated_cost_usd == Decimal(
        "0.00000000"
    )
    assert str(_estimate(_catalog()).estimated_cost_usd) == "0.00750000"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"model": "unknown-model"},
        {"provider": "google"},
        {"input_tokens": None},
        {"output_tokens": None},
        {"cache_write_tokens": 10},
        {"cache_read_tokens": 2000},
    ],
)
def test_unpriced_cases_return_null_cost(kwargs):
    estimate = _estimate(_catalog(), **kwargs)
    assert estimate.price_status == "unpriced"
    assert estimate.estimated_cost_usd is None
    assert estimate.catalog_version == "2026-11-01"


def test_missing_cache_rate_is_unpriced_only_when_cache_was_read():
    catalog = _catalog(cache_read_per_million=None)
    assert _estimate(catalog, cache_read_tokens=0).price_status == "priced"
    assert _estimate(catalog, cache_read_tokens=1).price_status == "unpriced"


def test_context_tier_limit():
    catalog = _catalog(max_input_tokens=272_000)
    assert _estimate(catalog, input_tokens=272_000).price_status == "priced"
    assert _estimate(catalog, input_tokens=272_001).price_status == "unpriced"


def test_google_models_prefix_is_ignored_but_snapshots_are_not_folded():
    catalog = _catalog(provider="google", model="gemini-x")
    assert _estimate(catalog, provider="google", model="models/gemini-x").price_status == "priced"
    assert _estimate(catalog, provider="google", model="gemini-x-2026-01-01").price_status == (
        "unpriced"
    )


def test_currency_other_than_usd_is_rejected():
    with pytest.raises(ValueError, match="currency"):
        PriceCatalog.model_validate(
            {"catalog_version": "2026-11-01", "currency": "EUR", "entries": []}
        )


def test_float_prices_are_rejected():
    with pytest.raises(ValueError, match="exact decimals"):
        _catalog(input_per_million=2.5)


def test_duplicate_models_are_rejected():
    entry = _catalog().entries[0].model_dump(mode="json")
    with pytest.raises(ValueError, match="only once"):
        PriceCatalog.model_validate(
            {"catalog_version": "2026-11-01", "currency": "USD", "entries": [entry, entry]}
        )


def test_unknown_catalog_version_is_a_config_error():
    with pytest.raises(MultimcpConfigError):
        load_catalog("1999-01-01")
