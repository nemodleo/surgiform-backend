from fastapi import APIRouter
from surgiform.api.endpoint import consent
from surgiform.api.endpoint import transform
from surgiform.api.endpoint import health

api_router = APIRouter()
api_router.include_router(consent.router)
api_router.include_router(transform.router)
api_router.include_router(health.router)