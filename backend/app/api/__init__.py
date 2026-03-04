from fastapi import APIRouter

from app.api.v1.endpoints import api_router_v1

api_router = APIRouter()
api_router.include_router(api_router_v1, prefix="/v1")
