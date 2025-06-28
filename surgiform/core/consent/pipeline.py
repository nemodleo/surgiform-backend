from surgiform.api.models.consent import ConsentGenerateIn
from surgiform.api.models.base import ConsentBase


def generate_consent(payload: ConsentGenerateIn) -> ConsentBase:
    """
    Graph-RAG 파이프라인 준비 전 임시 동의서 목업
    """

    return ConsentBase(
        prognosis_without_surgery=f"{payload.diagnosis}에 대해 수술을 시행하지 않을 경우, 증상이 지속되거나 악화될 수 있으며, 합병증이 발생할 위험이 있습니다. 환자의 현재 상태({payload.patient_condition})를 고려할 때 적절한 치료가 필요합니다.",
        alternative_treatments=f"{payload.diagnosis} 치료를 위한 다른 방법으로는 약물치료, 물리치료, 방사선치료 등이 있으나, 환자의 상태와 진단을 종합적으로 고려했을 때 수술적 치료가 가장 적합한 것으로 판단됩니다.",
        surgery_purpose_necessity_effect=f"본 수술의 목적은 {payload.diagnosis}의 근본적 치료를 통해 환자의 증상을 개선하고 삶의 질을 향상시키는 것입니다. 수술은 질병의 진행을 막고 합병증을 예방하기 위해 필요하며, 성공적인 수술 시 좋은 예후를 기대할 수 있습니다.",
        surgery_method_content=f"{payload.surgical_site_mark} 부위에 대한 수술을 시행합니다. 수술은 전신마취 하에 진행되며, 최소침습적 방법을 통해 병변을 제거하고 정상 해부학적 구조를 복원할 예정입니다. 수술 시간은 약 2-4시간 소요될 것으로 예상됩니다.",
        possible_complications_sequelae=f"{payload.diagnosis} 수술과 관련하여 발생 가능한 합병증으로는 출혈, 감염, 마취 관련 합병증, 신경 손상, 혈관 손상 등이 있을 수 있습니다. 또한 수술 부위의 흉터, 일시적 또는 영구적 기능 장애가 발생할 수 있으며, 드물게는 재수술이 필요할 수도 있습니다. 환자의 개별적 상태에 따라 위험도는 달라질 수 있습니다.",
        emergency_measures="수술 중 또는 수술 후 응급상황 발생 시 즉시 응급처치를 시행하고, 필요시 중환자실 입원, 재수술, 전문의 협진 등의 조치를 취하게 됩니다. 24시간 의료진이 대기하여 응급상황에 대비하고 있습니다.",
        mortality_risk=f"{payload.diagnosis} 수술과 관련된 사망 위험은 일반적으로 낮으나, 환자의 연령({payload.age}세), 전신상태, 동반질환 등을 종합적으로 고려할 때 약 1% 미만의 위험도가 있을 수 있습니다. 마취 관련 사망 위험도 포함되어 있으며, 모든 안전조치를 통해 위험을 최소화하고 있습니다."
    )