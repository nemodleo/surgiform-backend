from fastapi import APIRouter
from surgiform.api.models.consent import ConsentGenerateIn
from surgiform.api.models.consent import ConsentGenerateOut
from surgiform.deploy.service.consent import create_consent

router = APIRouter(tags=["consent"])


@router.post(
    "/consent",
    response_model=ConsentGenerateOut,
    summary="수술동의서 생성",
)
async def consent_endpoint(
    payload: ConsentGenerateIn,
) -> ConsentGenerateOut:
    return await create_consent(payload)