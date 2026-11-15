from fastapi import APIRouter

from multimcp_api.api.v1 import evaluations, events, health, playground, pricing, queries

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health.router)
api_v1_router.include_router(events.router)
api_v1_router.include_router(queries.router)
api_v1_router.include_router(evaluations.router)
api_v1_router.include_router(pricing.router)
api_v1_router.include_router(playground.router)
