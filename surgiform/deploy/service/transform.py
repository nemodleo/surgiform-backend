from surgiform.api.models.transform import ConsentTransformIn
from surgiform.api.models.transform import ConsentTransformOut
from surgiform.core.transform.pipeline import run_transform  # TODO: 구현 예정


def transform_consent(payload: ConsentTransformIn) -> ConsentTransformOut:
    """
    변환 서비스 오케스트레이터
    """
    # ① Core 파이프라인 호출 (임시로 에코 반환)
    consents = payload.consents
    references = payload.references
    mode = payload.mode
    transformed_consents, transformed_references = run_transform(consents, references, mode)  # type: ignore[arg-type]

    # ② DTO 로 씌워 반환
    return ConsentTransformOut(transformed_consents=transformed_consents, transformed_references=transformed_references)
