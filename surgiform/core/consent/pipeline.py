from surgiform.api.models.consent import ConsentGenerateIn


def generate_consent(payload: ConsentGenerateIn) -> str:
    """
    Graph-RAG 파이프라인 준비 전 임시 동의서 목업
    """
    return (
        f"수술동의서(가제) - 환자: {payload.patient_name}, "
        f"진단명: {payload.diagnosis}, 예정일: {payload.scheduled_date}"
    )