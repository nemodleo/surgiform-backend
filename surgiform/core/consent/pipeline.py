from copy import deepcopy
from functools import partial
import re
import asyncio
import logging

from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
import openai

from surgiform.api.models.consent import ConsentGenerateIn
from surgiform.api.models.consent import PublicConsentGenerateIn
from surgiform.api.models.base import ConsentBase
from surgiform.api.models.base import SurgeryDetails
from surgiform.api.models.base import ReferenceBase
from surgiform.api.models.base import SurgeryDetailsReference
from surgiform.core.ingest.uptodate.run_es import get_es_response
from surgiform.external.openai_client import get_chat_llm
from surgiform.external.openai_client import get_key_word_list_from_text
from surgiform.external.openai_client import translate_text
from surgiform.api.models.consent import Gender

# 로깅 설정
logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """\
You are an expert in writing surgical consent forms.
Generate **ONLY** the field <{field}> in **plain, easy-to-understand Korean**, using **5 to 10 sentences** that even a middle school student can understand.  

Base your answer on:
1. Patient-specific context (provided in JSON)
2. Evidence sentences (from UpToDate) — include them **only if relevant**

Use **official Korean medical terms**, but explain them in **simple, everyday language**.  
Avoid academic, technical, or formal expressions.  
Do **not** mention the patient's name or registration number.  
Do **not** quote evidence sentences verbatim.\
"""

USER_PROMPT = """\
### PATIENT_CONTEXT
```json
{patient_json}
```

## EVIDENCE_BLOCK
{evidence_block}
"""


def remove_xml_tags(text: str) -> str:
    """
    XML 태그를 제거하는 함수 (한쪽 태그만 있어도 삭제)
    예: 
    - <emergency_measures>내용</emergency_measures> -> 내용
    - <emergency_measures>내용 -> 내용  
    - 내용</emergency_measures> -> 내용
    """
    # 모든 XML 태그 제거 (여는 태그, 닫는 태그 모두)
    # <태그명> 또는 </태그명> 패턴 제거
    pattern = r'<[^>]*>'
    cleaned_text = re.sub(pattern, '', text)
    
    return cleaned_text.strip()


def preprocess(in_data: ConsentGenerateIn) -> PublicConsentGenerateIn:
    data = deepcopy(in_data).dict()
    data.pop("registration_no", None)
    data.pop("patient_name", None)

    return PublicConsentGenerateIn(**data)


class ProcessedPayload:
    """미리 계산된 공통 데이터를 담는 클래스"""
    def __init__(self, payload: PublicConsentGenerateIn):
        self.payload = payload
        self.diagnosis = translate_text(payload.diagnosis)
        self.surgery_name = translate_text(payload.surgery_name)
        self.patient_condition_keys = get_key_word_list_from_text(payload.patient_condition)
        self.special_conditions_other_keys = get_key_word_list_from_text(payload.special_conditions.other)


def is_rate_limit_error(exception):
    """레이트 리밋 관련 오류인지 확인하는 함수"""
    # 예외 타입과 메시지를 로깅
    logger.debug(f"예외 타입 확인: {type(exception).__name__}, 메시지: {str(exception)}")
    
    # OpenAI 직접 예외들
    if isinstance(exception, openai.RateLimitError):
        logger.debug("OpenAI RateLimitError 감지")
        return True
    
    if isinstance(exception, openai.APIError):
        if hasattr(exception, 'status_code') and exception.status_code == 429:
            logger.debug("OpenAI APIError 429 감지")
            return True
    
    if isinstance(exception, openai.APIConnectionError):
        logger.debug("OpenAI APIConnectionError 감지")
        return True
        
    if isinstance(exception, openai.APITimeoutError):
        logger.debug("OpenAI APITimeoutError 감지")
        return True
    
    # LangChain에서 래핑된 예외들도 확인
    exception_str = str(exception).lower()
    if 'rate limit' in exception_str or 'error code: 429' in exception_str:
        logger.debug("문자열 패턴으로 레이트 리밋 감지")
        return True
        
    # 일반적인 Exception에서 rate limit 관련 메시지 확인
    if hasattr(exception, 'response') and hasattr(exception.response, 'status_code'):
        if exception.response.status_code == 429:
            logger.debug("HTTP 429 상태 코드 감지")
            return True
    
    logger.debug("레이트 리밋 오류가 아님")
    return False


def log_retry_attempt(retry_state):
    """재시도 시도 시 로그를 출력하는 함수"""
    # retry_state.args에서 task_name 추출 (첫 번째 인자)
    task_name = "unknown"
    if retry_state.args and len(retry_state.args) > 0:
        task_name = retry_state.args[0]  # task_name은 첫 번째 파라미터
    
    logger.warning(f"OpenAI API 오류로 인한 재시도 - 작업: '{task_name}', 시도: {retry_state.attempt_number}회차, "
                  f"다음 재시도까지 대기: {retry_state.next_action.sleep if retry_state.next_action else 0}초")


async def generate_rag_response(processed_payload: ProcessedPayload, task_name: str, attempt_number: int = 1) -> tuple[str, list[str]]:
    """
    공통 RAG 로직: 키워드 추출, 문서 검색, LLM 응답 생성 (Async 버전 + 병렬 ES 검색)
    """
    try:
        # 첫 번째 시도는 gpt-4.1, 재시도부터는 gpt-3.5-turbo 사용
        model_name = "gpt-4.1" if attempt_number == 1 else "gpt-3.5-turbo"
        
        if attempt_number > 1:
            logger.info(f"재시도 중 - 작업 '{task_name}'에서 gpt-3.5-turbo 사용 (시도: {attempt_number})")
        
        logger.debug(f"작업 '{task_name}' 시작 (시도: {attempt_number}, 모델: {model_name})")
        payload = processed_payload.payload
        diagnosis = processed_payload.diagnosis
        surgery_name = processed_payload.surgery_name
        patient_condition_keys = processed_payload.patient_condition_keys
        special_conditions_other_keys = processed_payload.special_conditions_other_keys

        evidence_blocks = []
        references = []
        es_query = f"{task_name.replace('_', ' ')} {diagnosis} {surgery_name}" 
        
        # 모든 키워드 수집
        keywords = [
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
        ]
        
        # None 값 제거하고 ES 쿼리 생성
        valid_keywords = [kw for kw in keywords if kw is not None]
        es_queries = [f"{es_query} {keyword}" for keyword in valid_keywords]
        
        # 모든 ES 검색을 병렬로 실행
        if es_queries:
            es_results = await asyncio.gather(
                *[get_es_response(query, k=10, score_threshold=1) for query in es_queries]
            )
            
            # 결과 통합
            for evidence_block in es_results:
                evidence_blocks.extend([hit["text"] for hit in evidence_block])
                references.extend([{
                    "url": hit["url"],
                    "title": hit["title"],
                    "text": hit["text"]
                } for hit in evidence_block])

        llm = get_chat_llm(model_name=model_name)
        prompt = SYSTEM_PROMPT.format(field=task_name)
        evidence_blocks = "\n\n".join(evidence_blocks)
        prompt += USER_PROMPT.format(patient_json=payload.model_dump_json(), evidence_block=evidence_blocks)
        
        # LangChain의 async invoke 사용
        logger.debug(f"작업 '{task_name}' OpenAI API 호출 중... (모델: {model_name})")
        response = await llm.ainvoke(prompt)

        # XML 태그 제거
        cleaned_content = remove_xml_tags(response.content)

        # references = list(set(references))
        logger.debug(f"작업 '{task_name}' 완료")
        return cleaned_content, references
        
    except Exception as e:
        logger.error(f"작업 '{task_name}' 중 오류 발생: {str(e)}")
        # tenacity가 재시도 여부를 결정하도록 예외를 다시 발생시킴
        raise


# Async partial 함수들을 사용해서 각 동의서 필드별 함수 생성
@retry(
    wait=wait_exponential(multiplier=2, min=4, max=60),
    stop=stop_after_attempt(5),
    retry=is_rate_limit_error,
    before_sleep=log_retry_attempt
)
async def _create_consent_func(task_name: str, processed_payload: ProcessedPayload) -> tuple[str, list[str]]:
    # tenacity retry context에서 현재 시도 횟수를 가져오기 위한 트릭
    import inspect
    frame = inspect.currentframe()
    attempt_number = 1
    try:
        # 현재 실행 중인 함수의 프레임에서 retry 상태 확인
        for f in inspect.getouterframes(frame):
            if 'retry_state' in f.frame.f_locals:
                retry_state = f.frame.f_locals['retry_state']
                attempt_number = retry_state.attempt_number
                break
    finally:
        del frame
    
    return await generate_rag_response(processed_payload, task_name, attempt_number)

async def get_prognosis_without_surgery(processed_payload: ProcessedPayload) -> tuple[str, list[str]]:
    return await _create_consent_func("prognosis_without_surgery", processed_payload)

async def get_alternative_treatments(processed_payload: ProcessedPayload) -> tuple[str, list[str]]:
    return await _create_consent_func("alternative_treatments", processed_payload)

async def get_surgery_purpose_necessity_effect(processed_payload: ProcessedPayload) -> tuple[str, list[str]]:
    return await _create_consent_func("surgery_purpose_necessity_effect", processed_payload)

async def get_possible_complications_sequelae(processed_payload: ProcessedPayload) -> tuple[str, list[str]]:
    return await _create_consent_func("possible_complications_sequelae", processed_payload)

async def get_emergency_measures(processed_payload: ProcessedPayload) -> tuple[str, list[str]]:
    return await _create_consent_func("emergency_measures", processed_payload)

async def get_mortality_risk(processed_payload: ProcessedPayload) -> tuple[str, list[str]]:
    return await _create_consent_func("mortality_risk", processed_payload)

async def get_overall_description(processed_payload: ProcessedPayload) -> tuple[str, list[str]]:
    return await _create_consent_func("overall_description", processed_payload)

async def get_estimated_duration(processed_payload: ProcessedPayload) -> tuple[str, list[str]]:
    return await _create_consent_func("estimated_duration", processed_payload)

async def get_method_change_or_addition(processed_payload: ProcessedPayload) -> tuple[str, list[str]]:
    return await _create_consent_func("method_change_or_addition", processed_payload)

async def get_transfusion_possibility(processed_payload: ProcessedPayload) -> tuple[str, list[str]]:
    return await _create_consent_func("transfusion_possibility", processed_payload)

async def get_surgeon_change_possibility(processed_payload: ProcessedPayload) -> tuple[str, list[str]]:
    return await _create_consent_func("surgeon_change_possibility", processed_payload)


async def generate_consent(payload: ConsentGenerateIn) -> tuple[ConsentBase, ReferenceBase]:
    """
    Graph-RAG 파이프라인 준비 전 임시 동의서 목업 (Async 병렬 처리 버전)
    """
    deidentified_payload: PublicConsentGenerateIn = preprocess(payload)
    # 공통 계산을 한 번만 수행
    processed_payload = ProcessedPayload(deidentified_payload)
    
    # 모든 get_* 함수들을 병렬로 실행 (개별 오류 처리를 위해 return_exceptions=True 사용)
    logger.info("동의서 생성 시작: 모든 섹션을 병렬로 생성 중...")
    
    tasks = [
        ("overall_description", get_overall_description(processed_payload)),
        ("estimated_duration", get_estimated_duration(processed_payload)),
        ("method_change_or_addition", get_method_change_or_addition(processed_payload)),
        ("transfusion_possibility", get_transfusion_possibility(processed_payload)),
        ("surgeon_change_possibility", get_surgeon_change_possibility(processed_payload)),
        ("prognosis_without_surgery", get_prognosis_without_surgery(processed_payload)),
        ("alternative_treatments", get_alternative_treatments(processed_payload)),
        ("surgery_purpose_necessity_effect", get_surgery_purpose_necessity_effect(processed_payload)),
        ("possible_complications_sequelae", get_possible_complications_sequelae(processed_payload)),
        ("emergency_measures", get_emergency_measures(processed_payload)),
        ("mortality_risk", get_mortality_risk(processed_payload))
    ]
    
    # 병렬 실행 - 개별 오류도 결과로 반환
    task_names = [name for name, _ in tasks]
    task_coroutines = [coro for _, coro in tasks]
    
    results = await asyncio.gather(*task_coroutines, return_exceptions=True)
    
    # 결과 처리 및 오류 체크
    processed_results = []
    failed_tasks = []
    successful_tasks = []
    
    for i, result in enumerate(results):
        task_name = task_names[i]
        if isinstance(result, Exception):
            logger.error(f"작업 '{task_name}' 실행 중 오류 발생: {str(result)}")
            failed_tasks.append(task_name)
            # 기본값 설정 (빈 문자열과 빈 참조 리스트)
            processed_results.append(("", []))
        else:
            logger.info(f"작업 '{task_name}' 성공적으로 완료")
            successful_tasks.append(task_name)
            processed_results.append(result)
    
    # 전체 작업 완료 통계 로깅
    total_tasks = len(task_names)
    success_count = len(successful_tasks)
    failed_count = len(failed_tasks)
    
    logger.info(f"동의서 생성 완료: 총 {total_tasks}개 작업 중 {success_count}개 성공, {failed_count}개 실패")
    if failed_tasks:
        logger.warning(f"실패한 작업들: {', '.join(failed_tasks)}")
    
    # 결과 언패킹
    (consents_overall_description, references_overall_description), \
    (consents_estimated_duration, references_estimated_duration), \
    (consents_method_change_or_addition, references_method_change_or_addition), \
    (consents_transfusion_possibility, references_transfusion_possibility), \
    (consents_surgeon_change_possibility, references_surgeon_change_possibility), \
    (consents_prognosis_without_surgery, references_prognosis_without_surgery), \
    (consents_alternative_treatments, references_alternative_treatments), \
    (consents_surgery_purpose_necessity_effect, references_surgery_purpose_necessity_effect), \
    (consents_possible_complications_sequelae, references_possible_complications_sequelae), \
    (consents_emergency_measures, references_emergency_measures), \
    (consents_mortality_risk, references_mortality_risk) = processed_results

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
