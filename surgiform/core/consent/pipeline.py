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
# from surgiform.external.openai_client import llm_validater
from surgiform.external.openai_client import allm_validater
from surgiform.api.models.consent import Gender

# 로깅 설정
logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """\
You are a medical communication expert who explains surgical consent forms clearly and accurately for patients.

### ROLE
- Act as an expert writer of patient consent documents.
- Your task is to generate the **content for the field <{field}> only**.

### OUTPUT RULES
- Output must be written in **plain Korean (5–10 sentences)**.
- Write the final answer as **one continuous paragraph** without bullets, extra line breaks, headings, labels, or commentary.
- Each sentence must be **short and clear** (ideally under 30 words) to improve readability.
- The tone must **remain formal enough for a consent form**, yet **sound natural as if a doctor is directly explaining to a patient**.
- Use **official Korean medical terms** (학술 용어) but explain them in everyday simple words; **append the precise term in parentheses only once at first mention**.
- After the first mention, use only the plain explanation or a short expression **without repeating the term in parentheses**.
- Do not redundantly append terms when the simple explanation and the medical term are essentially the same.
- Do not append medical terms for generic or self-explanatory words that are not true medical terminology.
- **Do NOT** include the patient's name or registration number.
- **Do NOT** output any XML/HTML/JSON tags, identifiers, or metadata—just plain text.
- **Do NOT** copy or quote evidence sentences verbatim; rephrasing and synthesis are mandatory.
- If no relevant evidence exists for the field, omit it rather than force irrelevant content.
- **Do NOT** fabricate data, numbers, or risks. Only include what is clearly supported.
- Keep sentences short **but ensure natural flow between sentences**; avoid a fragmented or list-like feel.

### ADDITIONAL RULES
- The final result must be **one paragraph**, but sentences must be clearly separated for readability.
- Medical terms must be shown in parentheses **only once**, and afterward described in short and simple expressions.
- If the same risk factors or diseases appear multiple times, mention them once and later summarize as **“이러한 기저질환”**.
- When describing risks, **clearly distinguish** between categories and **always present common ones first** using a consistent phrasing pattern:  
  **“흔히 나타날 수 있는 부작용은 …”**, 이어서 **“드물지만 심각한 합병증은 …”**.
- Only medical terms require additional explanations; all other words should remain as they are without extra rephrasing.
- Maintain **medical accuracy** while writing in **plain Korean understandable by a middle school student**.
- **Do not repeat** the same concept with duplicate explanations or redundant medical term annotations.

### EVIDENCE USAGE
- You will be provided with:
  1. **Patient context (JSON)**
  2. **Evidence (medical references)**
- Use evidence only if relevant to the patient’s context and the target field.
- Summarize and rephrase; do not include irrelevant details.
- It is acceptable to refer to the same source across sentences, but rephrasing and synthesis are the default.

### GOAL
- Produce a **clear, medically accurate, patient-friendly explanation of <{field}>** in plain Korean **as a single paragraph**, nothing else.
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
    def __init__(self, payload: PublicConsentGenerateIn, diagnosis: str, surgery_name: str, patient_condition_keys: list, special_conditions_other_keys: list):
        self.payload = payload
        self.diagnosis = diagnosis
        self.surgery_name = surgery_name
        self.patient_condition_keys = patient_condition_keys
        self.special_conditions_other_keys = special_conditions_other_keys

    @classmethod
    async def create(cls, payload: PublicConsentGenerateIn):
        """비동기 팩토리 메서드로 병렬 처리"""
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        # ThreadPoolExecutor를 사용해 동기 함수들을 병렬로 실행
        loop = asyncio.get_running_loop()
        
        tasks = [
            loop.run_in_executor(None, translate_text, payload.diagnosis),
            loop.run_in_executor(None, translate_text, payload.surgery_name), 
            loop.run_in_executor(None, get_key_word_list_from_text, payload.patient_condition),
            loop.run_in_executor(None, get_key_word_list_from_text, payload.special_conditions.other)
        ]
        
        results = await asyncio.gather(*tasks)
        diagnosis, surgery_name, patient_condition_keys, special_conditions_other_keys = results
        
        return cls(payload, diagnosis, surgery_name, patient_condition_keys, special_conditions_other_keys)


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
        MODEL_ORDER = [
            "gpt-5",
            "gpt-5-mini",
            "gpt-4.1",
            "gpt-4.1-mini",
            "gpt-3.5-turbo",
        ]
        def get_model_name(attempt: int) -> str:
            return MODEL_ORDER[min(attempt - 1, len(MODEL_ORDER) - 1)]
        
        model_name = get_model_name(attempt_number)
        
        if attempt_number > 1:
            logger.info(f"재시도 중 - 작업 '{task_name}'에서 {model_name} 사용 (시도: {attempt_number})")
        
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
            # 키워드가 많을 때 gather 폭주 가능성 있음. semaphore(n=8)로 동시성 제한
            sem = asyncio.Semaphore(8)
            async def _es(query): 
                async with sem:
                    return await get_es_response(query, k=10, score_threshold=1)
            es_results = await asyncio.gather(*[_es(q) for q in es_queries])

#             # llm validator - 모든 validation을 병렬로 처리
#             validation_tasks = []
#             hit_mappings = []  # (result_idx, hit_idx, hit) 매핑 정보 저장
            
#             for result_idx, result in enumerate(es_results):
#                 for hit_idx, hit in enumerate(result):
#                     prompt = SYSTEM_PROMPT.format(field=task_name)
#                     user_prompt = """\
# ### PATIENT_CONTEXT
# ```json
# {patient_json}
# ```

# Determine whether the EVIDENCE_BLOCK contains information that is directly relevant and appropriate for writing the specified section of the surgical consent form, based on the PATIENT_CONTEXT.

# If it is relevant and appropriate, answer with "Y".
# If it is not relevant, answer with "N".

# Respond with only one letter, either "Y" or "N".
# Answer:
# """
#                     full_prompt = prompt + user_prompt.format(patient_json=payload.model_dump_json(), evidence_block=hit["text"])
#                     validation_tasks.append(allm_validater(full_prompt))
#                     hit_mappings.append((result_idx, hit_idx, hit))
            
#             # 모든 validation을 병렬로 실행
#             if validation_tasks:
#                 logger.debug(f"작업 '{task_name}': {len(validation_tasks)}개의 evidence 병렬 validation 시작")
#                 validation_results = await asyncio.gather(*validation_tasks)
                
#                 # 결과를 원래 구조로 재구성
#                 filtered_results = [[] for _ in es_results]
#                 valid_count = 0
#                 for i, is_valid in enumerate(validation_results):
#                     if is_valid:
#                         result_idx, hit_idx, hit = hit_mappings[i]
#                         filtered_results[result_idx].append(hit)
#                         valid_count += 1
                
#                 logger.debug(f"작업 '{task_name}': validation 완료 - {valid_count}/{len(validation_tasks)}개 evidence 유효")
#             else:
#                 filtered_results = []
            filtered_results = es_results
            
            # 결과 통합
            for evidence_block in filtered_results:
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
        error_msg = str(e)
        logger.error(f"작업 '{task_name}' 중 오류 발생: {error_msg}")
        
        # OpenAI API 할당량 초과 오류인 경우 기본 텍스트 반환
        if "insufficient_quota" in error_msg or "rate_limit" in error_msg.lower():
            logger.warning(f"OpenAI API 할당량 초과로 인한 작업 '{task_name}' 실패. 기본 응답 반환.")
            return f"{task_name.replace('_', ' ')}에 대한 내용을 작성할 수 없습니다. OpenAI API 할당량을 확인해주세요.", []
        
        # 기타 오류는 tenacity가 재시도하도록 다시 발생시킴
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
    # 공통 계산을 병렬로 수행
    processed_payload = await ProcessedPayload.create(deidentified_payload)
    
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
