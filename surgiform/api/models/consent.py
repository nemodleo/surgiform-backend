from datetime import date
from enum import Enum

from pydantic import BaseModel
from pydantic import Field
from pydantic import constr

from surgiform.api.models.base import ConsentBase

# -------------------------------------------------
# 1) 보조 Enum / 타입
# -------------------------------------------------
class Gender(str, Enum):
    male = "M"
    female = "F"


BoolOrStr = bool | constr(strip_whitespace=True, min_length=1)


# -------------------------------------------------
# 2) 참여 의료진
# -------------------------------------------------
class Participant(BaseModel):
    """
    참여 의료진 1인에 대한 정보
    - `is_lead`     : 집도의 여부
    - `is_specialist`: 전문의 여부
    - `department`  : 진료과 (예: GS, CS, Anesth)
    - `name`        : 성명 (선택 입력)
    """
    name: str | None = Field(None, description="의료진 성명")
    is_lead: bool = Field(..., description="집도의 여부")
    is_specialist: bool = Field(..., description="전문의 여부")
    department: str = Field(..., description="진료과 명칭")


# -------------------------------------------------
# 3) 특이사항
# -------------------------------------------------
class SpecialCondition(BaseModel):
    """
    환자 특이사항  
    각 필드는 `True / False` 또는 구체 설명 문자열 허용
    """
    past_history: BoolOrStr = False       # 과거병력
    diabetes: BoolOrStr = False           # 당뇨병
    smoking: BoolOrStr = False            # 흡연 여부
    hypertension: BoolOrStr = False       # 고혈압
    allergy: BoolOrStr = False            # 약물/음식 알레르기
    cardiovascular: BoolOrStr = False     # 심혈관 질환
    respiratory: BoolOrStr = False        # 호흡기 질환
    coagulation: BoolOrStr = False        # 혈액응고 관련 질환
    medications: BoolOrStr = False        # 복용 약물
    renal: BoolOrStr = False              # 신장 질환
    drug_abuse: BoolOrStr = False         # 마약/약물 사고
    other: str | None = None              # 기타 자유 기술


# -------------------------------------------------
# 4) 요청 & 응답 DTO
# -------------------------------------------------
class ConsentGenerateIn(BaseModel):
    """
    수술동의서 생성 요청
    """
    registration_no: str = Field(..., description="등록번호")
    patient_name: str = Field(..., description="환자 성명")
    age: int = Field(..., ge=0, le=150)
    gender: Gender
    scheduled_date: date = Field(..., description="수술 예정일")
    diagnosis: str = Field(..., description="진단명")
    surgical_site_mark: str = Field(..., description="수술 부위 표시")
    participants: list[Participant] = Field(..., min_items=1, description="참여 의료진 목록")
    patient_condition: str = Field(..., description="현재 환자 상태 요약")
    special_conditions: SpecialCondition = Field(default_factory=SpecialCondition)


class ConsentGenerateOut(BaseModel):
    """
    수술동의서 생성 결과
    """
    consents: ConsentBase = Field(..., description="수술동의서")
