from enum import Enum
from pydantic import BaseModel
from pydantic import Field

from surgiform.api.models.base import ConsentBase


class TransformMode(str, Enum):
    """지원되는 변환 모드."""
    simplify      = "simplify"       # 쉬운말 변환
    summary       = "summary"        # 5줄 요약
    explain       = "explain"        # 용어 풀이
    translate_en  = "translate_en"   # 영어 번역
    translate_zh  = "translate_zh"   # 중국어 번역
    translate_ja  = "translate_ja"   # 일본어 번역


class ConsentTransformIn(BaseModel):
    """
    수술 동의서 변환 요청 DTO
    """
    consents: ConsentBase = Field(..., description="원본 수술동의서")
    mode: TransformMode = Field(..., description="변환 모드")


class ConsentTransformOut(BaseModel):
    """
    수술 동의서 변환 응답 DTO
    """
    transformed_consents: ConsentBase = Field(..., description="변환된 수술동의서(plain text)")
