from fastapi import APIRouter

from multimcp_api.api.v1 import events, health

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health.router)
api_v1_router.include_router(events.router)
