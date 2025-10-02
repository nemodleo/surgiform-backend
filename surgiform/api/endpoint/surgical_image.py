from fastapi import APIRouter, HTTPException
import logging

from surgiform.api.models.surgical_image import (
    StepExtractionRequest,
    StepExtractionResponse,
    ImageGenerationRequest,
    ImageGenerationResponse,
    SurgicalImageGenerationRequest,
    SurgicalImageGenerationResponse
)
from surgiform.deploy.service.surgical_image import (
    extract_surgical_steps,
    generate_surgical_images_with_gemini,
    generate_surgical_images_complete
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/surgical-image/extract-steps", response_model=StepExtractionResponse)
async def extract_steps_endpoint(request: StepExtractionRequest):
    """
    수술 절차에서 핵심 단계를 추출합니다.

    - **procedure_name**: 수술명 (예: "복강경하 담낭절제술")
    - **max_steps**: 추출할 최대 단계 수 (1-5, 기본값: 2)
    - **language**: 응답 언어 (ko/en, 기본값: ko)
    """
    try:
        logger.info(f"수술 단계 추출 요청: {request.procedure_name}")
        result = await extract_surgical_steps(request)
        logger.info(f"수술 단계 추출 완료: {len(result.steps)}개 단계")
        return result
    except Exception as e:
        logger.error(f"수술 단계 추출 실패: {e}")
        raise HTTPException(status_code=500, detail=f"수술 단계 추출 실패: {str(e)}")


@router.post("/surgical-image/generate-images", response_model=ImageGenerationResponse)
async def generate_images_endpoint(request: ImageGenerationRequest):
    """
    추출된 수술 단계들에 대한 이미지를 생성합니다.

    - **steps**: 이미지 생성할 수술 단계 리스트
    """
    try:
        logger.info(f"이미지 생성 요청: {len(request.steps)}개 단계")
        result = await generate_surgical_images_with_gemini(request)
        logger.info(f"이미지 생성 완료: {len(result.images)}개 이미지")
        return result
    except HTTPException:
        # Re-raise HTTP exceptions with their original status codes
        raise
    except Exception as e:
        logger.error(f"이미지 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=f"이미지 생성 실패: {str(e)}")


@router.post("/surgical-image/generate", response_model=SurgicalImageGenerationResponse)
async def generate_surgical_images_endpoint(request: SurgicalImageGenerationRequest):
    """
    수술명으로부터 단계 추출과 이미지 생성을 한번에 수행합니다.

    - **procedure_name**: 수술명 (예: "복강경하 담낭절제술")
    - **max_steps**: 생성할 최대 단계 수 (1-5, 기본값: 2)
    - **language**: 응답 언어 (ko/en, 기본값: ko)

    Returns:
    - **procedure_name**: 수술명
    - **steps**: 추출된 수술 단계들
    - **images**: 생성된 이미지들 (Base64 인코딩)
    - **job_id**: 작업 ID
    """
    try:
        logger.info(f"수술 이미지 생성 요청: {request.procedure_name}")
        result = await generate_surgical_images_complete(request)
        logger.info(f"수술 이미지 생성 완료: {len(result.steps)}개 단계, {len(result.images)}개 이미지")
        return result
    except HTTPException:
        # Re-raise HTTP exceptions with their original status codes
        raise
    except Exception as e:
        logger.error(f"수술 이미지 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=f"수술 이미지 생성 실패: {str(e)}")


@router.get("/surgical-image/health")
async def surgical_image_health():
    """
    수술 이미지 생성 서비스 헬스체크
    """
    return {"status": "healthy", "service": "surgical-image"}
