"""Pricing catalog read endpoint (SPEC §6.3)."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from multimcp.pricing.catalog import DEFAULT_CATALOG_VERSION, load_catalog
from multimcp_api.auth import require_ingest_token
from multimcp_api.schemas.common import ApiModel

router = APIRouter(tags=["pricing"], dependencies=[Depends(require_ingest_token)])


class PricingCatalogResponse(ApiModel):
    schema_version: Literal["1.0"] = "1.0"
    catalog_version: str
    currency: Literal["USD"] = "USD"
    models: list[str]


@router.get("/pricing/catalog", response_model=PricingCatalogResponse)
async def pricing_catalog(
    catalog_version: Annotated[str | None, Query()] = None,
) -> PricingCatalogResponse:
    version = catalog_version or DEFAULT_CATALOG_VERSION
    catalog = load_catalog(version)
    models = sorted(f"{entry.provider}/{entry.model}" for entry in catalog.entries)
    return PricingCatalogResponse(
        catalog_version=catalog.catalog_version,
        currency=catalog.currency,
        models=models,
    )
