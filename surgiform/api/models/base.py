from pydantic import BaseModel
from pydantic import Field


class ConsentBase(BaseModel):
    """
    수술동의서
    """
    prognosis_without_surgery: str = Field(..., description="예정된 수술을 하지 않을 경우의 예후")
    alternative_treatments: str = Field(..., description="예정된 수술 이외의 시행 가능한 다른 방법")
    surgery_purpose_necessity_effect: str = Field(..., description="수술의 목적/필요성/효과")
    surgery_method_content: str = Field(..., description="수술의 방법 및 내용")
    possible_complications_sequelae: str = Field(..., description="발생 가능한 합병증/후유증/부작용")
    emergency_measures: str = Field(..., description="문제 발생시 조치사항")
    mortality_risk: str = Field(..., description="진단/수술 관련 사망 위험성")
