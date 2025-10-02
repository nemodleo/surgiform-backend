from fastapi import APIRouter
from surgiform.api.endpoint import consent
from surgiform.api.endpoint import transform
from surgiform.api.endpoint import health
from surgiform.api.endpoint import chat
from surgiform.api.endpoint import surgical_image

api_router = APIRouter()
api_router.include_router(consent.router)
api_router.include_router(transform.router)
api_router.include_router(health.router)
api_router.include_router(chat.router)
api_router.include_router(surgical_image.router)