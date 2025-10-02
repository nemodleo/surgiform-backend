from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class StepExtractionRequest(BaseModel):
    procedure_name: str = Field(..., alias="procedureName", description="수술명 (예: '복강경하 담낭절제술')")
    max_steps: int = Field(default=2, ge=1, le=5, alias="maxSteps", description="추출할 최대 단계 수")
    language: str = Field(default="ko", description="응답 언어 (ko/en)")

    class Config:
        populate_by_name = True


class SurgicalStep(BaseModel):
    id: str = Field(..., description="단계 ID (예: 's1', 's2')")
    index: int = Field(..., description="단계 순서")
    title: str = Field(..., description="단계 제목")
    desc: str = Field(..., description="단계 설명")
    nanobanana_prompt: str = Field(..., alias="geminiPrompt", description="Gemini API용 프롬프트")

    class Config:
        populate_by_name = True


class StepExtractionResponse(BaseModel):
    version: str = Field(default="v1", description="API 버전")
    procedure: Dict[str, str] = Field(..., description="수술 정보")
    steps: List[SurgicalStep] = Field(..., description="추출된 수술 단계들")

    class Config:
        populate_by_name = True


class ImageGenerationRequest(BaseModel):
    steps: List[SurgicalStep] = Field(..., description="이미지 생성할 수술 단계들")


class GeneratedImage(BaseModel):
    step_id: str = Field(..., alias="stepId", description="단계 ID")
    mime_type: str = Field(default="image/png", alias="mimeType", description="이미지 MIME 타입")
    data: str = Field(..., description="Base64 인코딩된 이미지 데이터")
    url: Optional[str] = Field(None, description="이미지 URL (Gemini API에서 제공시)")

    class Config:
        populate_by_name = True


class ImageGenerationResponse(BaseModel):
    job_id: str = Field(..., alias="jobId", description="작업 ID")
    images: List[GeneratedImage] = Field(..., description="생성된 이미지들")

    class Config:
        populate_by_name = True


class SurgicalImageGenerationRequest(BaseModel):
    procedure_name: str = Field(..., alias="procedureName", description="수술명")
    max_steps: int = Field(default=2, ge=1, le=5, alias="maxSteps", description="생성할 최대 단계 수")
    language: str = Field(default="ko", description="응답 언어")

    class Config:
        populate_by_name = True


class SurgicalImageGenerationResponse(BaseModel):
    procedure_name: str = Field(..., alias="procedureName", description="수술명")
    steps: List[SurgicalStep] = Field(..., description="추출된 단계들")
    images: List[GeneratedImage] = Field(..., description="생성된 이미지들")
    job_id: str = Field(..., alias="jobId", description="작업 ID")

    class Config:
        populate_by_name = True