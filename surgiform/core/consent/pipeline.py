from copy import deepcopy
from functools import partial

from surgiform.api.models.consent import ConsentGenerateIn
from surgiform.api.models.consent import PublicConsentGenerateIn
from surgiform.api.models.base import ConsentBase
from surgiform.api.models.base import SurgeryDetails
from surgiform.api.models.base import ReferenceBase
from surgiform.api.models.base import SurgeryDetailsReference
from surgiform.core.ingest.uptodate.run_es import get_es_response
from surgiform.external.openai_client import get_chat_llm
from surgiform.external.openai_client import get_key_word_list_from_text
from surgiform.api.models.consent import Gender


SYSTEM_PROMPT = """\
You are an expert surgical consent writer. 
Generate **ONLY** the field <{field}> in concise Korean (2-4 문장). 
Base your answer on:
1. Patient‐specific context (JSON).
2. Evidence sentences (UpToDate) — use only when relevant.

Use official Korean medical terminology, but express it in **plain, easy-to-understand language**. 
Avoid academic or technical expressions. 
Never mention patient name or registration number; never quote sentences verbatim.\
"""

USER_PROMPT = """\
### PATIENT_CONTEXT
```json
{patient_json}
```

## EVIDENCE_BLOCK
{evidence_block}
"""


def preprocess(in_data: ConsentGenerateIn) -> PublicConsentGenerateIn:
    data = deepcopy(in_data).dict()
    data.pop("registration_no", None)
    data.pop("patient_name", None)

    return PublicConsentGenerateIn(**data)


def generate_rag_response(payload: PublicConsentGenerateIn, task_name: str) -> tuple[str, list[str]]:
    """
    공통 RAG 로직: 키워드 추출, 문서 검색, LLM 응답 생성
    """
    patient_condition_keys = get_key_word_list_from_text(payload.patient_condition)
    special_conditions_other_keys = get_key_word_list_from_text(payload.special_conditions.other)

    evidence_blocks = []
    references = []
    es_query = f"{task_name.replace('_', ' ')} {payload.diagnosis} {payload.surgery_name}" 
    
    for key_word in [
        f"{payload.age} years old",
        "male" if payload.gender is Gender.male else "female",
        f"{payload.surgical_site_mark}",
        *patient_condition_keys,
        "past_history" if payload.special_conditions.past_history else None,
        "diabetes" if payload.special_conditions.diabetes else None,
        "smoking" if payload.special_conditions.smoking else None,
        "hypertension" if payload.special_conditions.hypertension else None,
        "allergy" if payload.special_conditions.allergy else None,
        "cardiovascular" if payload.special_conditions.cardiovascular else None,
        "respiratory" if payload.special_conditions.respiratory else None,
        "coagulation" if payload.special_conditions.coagulation else None,
        "medications" if payload.special_conditions.medications else None,
        "renal" if payload.special_conditions.renal else None,
        "drug_abuse" if payload.special_conditions.drug_abuse else None,
        *special_conditions_other_keys
    ]:
        if key_word is None:
            continue

        _es_query = f"{es_query} {key_word}"
        evidence_block = get_es_response(_es_query, k=10, score_threshold=1)
        evidence_blocks.extend([hit["text"] for hit in evidence_block])
        references.extend([hit["url"] for hit in evidence_block])

    llm = get_chat_llm()
    prompt = SYSTEM_PROMPT.format(field=task_name)
    evidence_blocks = "\n\n".join(evidence_blocks)
    prompt += USER_PROMPT.format(patient_json=payload.model_dump_json(), evidence_block=evidence_blocks)
    response = llm.invoke(prompt)

    references = list(set(references))
    return response.content, references


# Partial 함수들을 사용해서 각 동의서 필드별 함수 생성
def _create_consent_func(task_name: str, payload: PublicConsentGenerateIn) -> tuple[str, list[str]]:
    return generate_rag_response(payload, task_name)

get_prognosis_without_surgery = partial(_create_consent_func, "prognosis_without_surgery")
get_alternative_treatments = partial(_create_consent_func, "alternative_treatments")
get_surgery_purpose_necessity_effect = partial(_create_consent_func, "surgery_purpose_necessity_effect")
get_possible_complications_sequelae = partial(_create_consent_func, "possible_complications_sequelae")
get_emergency_measures = partial(_create_consent_func, "emergency_measures")
get_mortality_risk = partial(_create_consent_func, "mortality_risk")
get_overall_description = partial(_create_consent_func, "overall_description")
get_estimated_duration = partial(_create_consent_func, "estimated_duration")
get_method_change_or_addition = partial(_create_consent_func, "method_change_or_addition")
get_transfusion_possibility = partial(_create_consent_func, "transfusion_possibility")
get_surgeon_change_possibility = partial(_create_consent_func, "surgeon_change_possibility")


def generate_consent(payload: ConsentGenerateIn) -> tuple[ConsentBase, ReferenceBase]:
    """
    Graph-RAG 파이프라인 준비 전 임시 동의서 목업
    """
    deidentified_payload: PublicConsentGenerateIn = preprocess(payload)
    consents_overall_description, references_overall_description = get_overall_description(deidentified_payload)
    consents_estimated_duration, references_estimated_duration = get_estimated_duration(deidentified_payload)
    consents_method_change_or_addition, references_method_change_or_addition = get_method_change_or_addition(deidentified_payload)
    consents_transfusion_possibility, references_transfusion_possibility = get_transfusion_possibility(deidentified_payload)
    consents_surgeon_change_possibility, references_surgeon_change_possibility = get_surgeon_change_possibility(deidentified_payload)

    consents_prognosis_without_surgery, references_prognosis_without_surgery = get_prognosis_without_surgery(deidentified_payload)
    consents_alternative_treatments, references_alternative_treatments = get_alternative_treatments(deidentified_payload)
    consents_surgery_purpose_necessity_effect, references_surgery_purpose_necessity_effect = get_surgery_purpose_necessity_effect(deidentified_payload)
    consents_possible_complications_sequelae, references_possible_complications_sequelae = get_possible_complications_sequelae(deidentified_payload)
    consents_emergency_measures, references_emergency_measures = get_emergency_measures(deidentified_payload)
    consents_mortality_risk, references_mortality_risk = get_mortality_risk(deidentified_payload)

    consents_surgery_method_content = SurgeryDetails(
        overall_description=consents_overall_description,
        estimated_duration=consents_estimated_duration,
        method_change_or_addition=consents_method_change_or_addition,
        transfusion_possibility=consents_transfusion_possibility,
        surgeon_change_possibility=consents_surgeon_change_possibility
    )

    consents = ConsentBase(
        prognosis_without_surgery=consents_prognosis_without_surgery,
        alternative_treatments=consents_alternative_treatments,
        surgery_purpose_necessity_effect=consents_surgery_purpose_necessity_effect,
        surgery_method_content=consents_surgery_method_content,
        possible_complications_sequelae=consents_possible_complications_sequelae,
        emergency_measures=consents_emergency_measures,
        mortality_risk=consents_mortality_risk
    )

    references_surgery_method_content = SurgeryDetailsReference(
        overall_description=references_overall_description,
        estimated_duration=references_estimated_duration,
        method_change_or_addition=references_method_change_or_addition,
        transfusion_possibility=references_transfusion_possibility,
        surgeon_change_possibility=references_surgeon_change_possibility
    )

    references = ReferenceBase(
        prognosis_without_surgery=references_prognosis_without_surgery,
        alternative_treatments=references_alternative_treatments,
        surgery_purpose_necessity_effect=references_surgery_purpose_necessity_effect,
        surgery_method_content=references_surgery_method_content,
        possible_complications_sequelae=references_possible_complications_sequelae,
        emergency_measures=references_emergency_measures,
        mortality_risk=references_mortality_risk
    )

    return consents, references
