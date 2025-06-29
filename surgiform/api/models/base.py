from pydantic import BaseModel
from pydantic import Field


class SurgeryDetails(BaseModel):
    """수술 관련 세부 정보"""
    overall_description: str = Field(..., description="수술 과정 전반에 대한 설명")
    estimated_duration: str = Field(..., description="수술 추정 소요시간")
    method_change_or_addition: str = Field(..., description="수술 방법 변경 및 수술 추가 가능성")
    transfusion_possibility: str = Field(..., description="수혈 가능성")
    surgeon_change_possibility: str = Field(..., description="집도의 변경 가능성")


class ConsentBase(BaseModel):
    """
    수술동의서
    """
    prognosis_without_surgery: str = Field(..., description="예정된 수술을 하지 않을 경우의 예후")
    alternative_treatments: str = Field(..., description="예정된 수술 이외의 시행 가능한 다른 방법")
    surgery_purpose_necessity_effect: str = Field(..., description="수술의 목적/필요성/효과")
    surgery_method_content: SurgeryDetails = Field(..., description="수술의 방법 및 내용")
    possible_complications_sequelae: str = Field(..., description="발생 가능한 합병증/후유증/부작용")
    emergency_measures: str = Field(..., description="문제 발생시 조치사항")
    mortality_risk: str = Field(..., description="진단/수술 관련 사망 위험성")


class ReferenceItem(BaseModel):
    """
    참고 문헌 항목
    """
    title: str = Field(..., description="참고 문헌 제목")
    url: str = Field(..., description="참고 문헌 URL")
    text: str = Field(..., description="참고 문헌 텍스트")


class SurgeryDetailsReference(BaseModel):
    """
    수술 관련 세부 정보 참고 문헌
    """
    overall_description: list[ReferenceItem] = Field(default_factory=list, description="수술 과정 전반에 대한 설명")
    estimated_duration: list[ReferenceItem] = Field(default_factory=list, description="수술 추정 소요시간")
    method_change_or_addition: list[ReferenceItem] = Field(default_factory=list, description="수술 방법 변경 및 수술 추가 가능성")
    transfusion_possibility: list[ReferenceItem] = Field(default_factory=list, description="수혈 가능성")
    surgeon_change_possibility: list[ReferenceItem] = Field(default_factory=list, description="집도의 변경 가능성")


class ReferenceBase(BaseModel):
    """
    참고 문헌
    """
    prognosis_without_surgery: list[ReferenceItem] = Field(default_factory=list, description="예정된 수술을 하지 않을 경우의 예후")
    alternative_treatments: list[ReferenceItem] = Field(default_factory=list, description="예정된 수술 이외의 시행 가능한 다른 방법")
    surgery_purpose_necessity_effect: list[ReferenceItem] = Field(default_factory=list, description="수술의 목적/필요성/효과")
    surgery_method_content: SurgeryDetailsReference = Field(default_factory=SurgeryDetailsReference, description="수술의 방법 및 내용")
    possible_complications_sequelae: list[ReferenceItem] = Field(default_factory=list, description="발생 가능한 합병증/후유증/부작용")
    emergency_measures: list[ReferenceItem] = Field(default_factory=list, description="문제 발생시 조치사항")
    mortality_risk: list[ReferenceItem] = Field(default_factory=list, description="진단/수술 관련 사망 위험성")
