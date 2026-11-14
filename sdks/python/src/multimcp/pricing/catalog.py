from datetime import date
from decimal import Decimal
from functools import lru_cache
from importlib import resources
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PositiveInt,
    ValidationError,
    model_validator,
)

from multimcp.errors import MultimcpConfigError
from multimcp.models import Provider

DEFAULT_CATALOG_VERSION = "2026-11-01"


def _reject_float(value: object) -> object:
    if isinstance(value, float):
        raise ValueError("prices must be JSON strings so they parse as exact decimals")
    return value


Rate = Annotated[Decimal, BeforeValidator(_reject_float), Field(ge=0)]


class PriceEntry(BaseModel):
    """Standard-tier rates in USD per million tokens, copied from the provider's public page."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: Provider
    model: str = Field(min_length=1)
    input_per_million: Rate
    output_per_million: Rate
    cache_read_per_million: Rate | None
    max_input_tokens: PositiveInt | None = None
    source_url: str = Field(pattern=r"^https://")
    retrieved_on: date


class PriceCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    catalog_version: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    currency: Literal["USD"]
    entries: tuple[PriceEntry, ...]

    @model_validator(mode="after")
    def _unique_models(self) -> Self:
        keys = [(entry.provider, entry.model) for entry in self.entries]
        if len(keys) != len(set(keys)):
            raise ValueError("each provider/model pair may appear only once")
        return self

    def find(self, provider: Provider, model: str) -> PriceEntry | None:
        """Exact model id match. Dated snapshots are not folded into their alias:
        providers have priced older snapshots differently from the current alias."""
        wanted = model.removeprefix("models/")
        for entry in self.entries:
            if entry.provider == provider and entry.model == wanted:
                return entry
        return None


@lru_cache(maxsize=8)
def load_catalog(version: str = DEFAULT_CATALOG_VERSION) -> PriceCatalog:
    path = resources.files("multimcp.pricing").joinpath("catalogs", f"{version}.json")
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise MultimcpConfigError(f"price catalog {version!r} is not bundled") from exc
    try:
        catalog = PriceCatalog.model_validate_json(raw)
    except ValidationError as exc:
        raise MultimcpConfigError(f"price catalog {version!r} is invalid: {exc}") from exc
    if catalog.catalog_version != version:
        raise MultimcpConfigError(
            f"catalog file {version}.json declares version {catalog.catalog_version!r}"
        )
    return catalog
