from surgiform.api.models.consent import ConsentGenerateIn
from surgiform.api.models.consent import ConsentGenerateOut
from surgiform.core.consent.pipeline import generate_consent  # TODO


def create_consent(payload: ConsentGenerateIn) -> ConsentGenerateOut:
    """
    수술동의서 생성 오케스트레이터
    """
    consents = generate_consent(payload)  # type: ignore[arg-type]

    return ConsentGenerateOut(consents=consents)
