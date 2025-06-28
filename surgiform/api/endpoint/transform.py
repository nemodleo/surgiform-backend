from fastapi import APIRouter
from surgiform.api.models.transform import ConsentTransformIn
from surgiform.api.models.transform import ConsentTransformOut
from surgiform.deploy.service.transform import transform_consent

router = APIRouter(tags=["transform"])


@router.post(
    "/transform",
    response_model=ConsentTransformOut,
    summary="수술동의서 변환",
)
async def transform_endpoint(
    payload: ConsentTransformIn,
) -> ConsentTransformOut:
    return transform_consent(payload)