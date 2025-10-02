import asyncio
import logging
import uuid
from typing import List, Dict, Any
import base64
from google import genai
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from fastapi import HTTPException

from surgiform.api.models.surgical_image import (
    StepExtractionRequest,
    StepExtractionResponse,
    ImageGenerationRequest,
    ImageGenerationResponse,
    SurgicalImageGenerationRequest,
    SurgicalImageGenerationResponse,
    SurgicalStep,
    GeneratedImage
)
from surgiform.external.openai_client import get_chat_llm, translate_text
from surgiform.deploy.settings import get_settings
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

# Semaphore for controlling concurrent Gemini API requests
GEMINI_SEMAPHORE = asyncio.Semaphore(4)  # Maximum 4 concurrent requests


def build_gemini_prompt(title: str, desc: str, labels: List[str], procedure_name: str = "", steps: List[Dict[str, Any]] = None, current_step_index: int = 0) -> str:
    """
    Build a standardized Gemini prompt for medical illustrations in WHO educational poster style.

    Args:
        title: Step title (e.g., "Laparoscope insertion")
        desc: Step description (e.g., "Create small abdominal incision")
        labels: List of anatomical structures to label (e.g., ["incision site", "trocar port"])
        procedure_name: Full procedure name for context (e.g., "laparoscopic colon cancer resection")
        steps: List of all surgical steps for context (optional)
        current_step_index: Index of current step in the steps list (0-based)

    Returns:
        Formatted prompt string optimized for image generation models
    """
    # Build context about the surgical sequence
    sequence_context = ""
    if steps and len(steps) > 1:
        total_steps = len(steps)
        step_position = ""

        if current_step_index == 0:
            step_position = "This is the first step of the procedure,"
            if len(steps) > 1:
                next_step = steps[current_step_index + 1]
                step_position += f" The next step will be: {next_step.get('title', '')}."
        elif current_step_index == total_steps - 1:
            step_position = "This is the final step of the procedure."
            prev_step = steps[current_step_index - 1]
            step_position += f" The previous step was: {prev_step.get('title', '')}."
        else:
            prev_step = steps[current_step_index - 1]
            next_step = steps[current_step_index + 1]
            step_position = f"This is step {current_step_index + 1} of {total_steps}."
            step_position += f" The previous step was: {prev_step.get('title', '')}."
            step_position += f" The next step will be: {next_step.get('title', '')}."

        sequence_context = f" {step_position} Ensure visual continuity with the surgical progression."

    # Build the main prompt following the WHO educational poster style
    prompt_parts = [
        "An educational healthcare infographic illustration in the style of a WHO patient education poster.",
        f"The image should depict a single scene from a {procedure_name} procedure," if procedure_name else "The image should depict a surgical procedure scene,",
        f"focusing on {title}: {desc}.{sequence_context}",
        "The illustration must use a simplified pictogram style with bold outlines and soft pastel colors on a clean white background.",
        "The style should remain approachable and diagrammatic, without gore, blood, patient-identifiable features, or unnecessary realism.",
        "The perspective should remain consistent with the other steps in the series.",
        "Absolutely no text, captions, numbers, dashed lines, boxes, arrows with words, or any written characters inside the image.",
        f"Label only the key anatomical structures ({', '.join(labels)}) using minimal visual markers such as arrows or simple shapes, without written language." if labels else "Label only the key anatomical structures using minimal visual markers such as arrows or simple shapes, without written language."
    ]

    return " ".join(prompt_parts)

def get_step_extraction_prompt(max_steps: int, procedure_name: str, language: str) -> str:
    """단계 추출 프롬프트 생성 (항상 영어로 생성)"""

    return f"""\
You are a medical expert. Extract {max_steps} key surgical steps and return only valid JSON.

Output JSON format:
{{
  "version": "v1",
  "procedure": {{"name": "{procedure_name}"}},
  "steps": [
    {{
      "id": "s1",
      "index": 1,
      "title": "Step title in English",
      "desc": "Step description in English",
      "geminiPrompt": "Educational medical illustration prompt"
    }}
  ],
}}

Return only JSON, no explanation.
"""


@retry(
    wait=wait_exponential(multiplier=1, min=4, max=10),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(Exception)
)
async def extract_surgical_steps(request: StepExtractionRequest) -> StepExtractionResponse:
    """
    AI를 사용하여 수술 절차에서 핵심 단계를 추출합니다.
    """
    try:
        # Generate trace ID for observability
        trace_id = f"trace-{uuid.uuid4().hex[:8]}"
        logger.info(f"수술 단계 추출 시작 [traceId={trace_id}] [procedure={request.procedure_name}]")


        llm = get_chat_llm(model_name="gpt-5-mini")

        user_prompt = f"Procedure: {request.procedure_name}"

        # Get language-specific prompt
        system_prompt = get_step_extraction_prompt(
            max_steps=request.max_steps,
            procedure_name=request.procedure_name,
            language=request.language
        )

        messages = [
            HumanMessage(content=system_prompt + "\n\n" + user_prompt)
        ]

        response = await llm.ainvoke(messages)
        response_content = response.content.strip()
        logger.info(f"AI 응답 받음: {len(response_content)} 문자")
        logger.info(f"AI 원본 응답: {repr(response_content)}")  # Use repr to see exact characters

        # JSON 파싱 시도
        import json
        try:
            # ```json 블록이 있다면 제거
            if "```json" in response_content:
                start = response_content.find("```json") + 7
                end = response_content.find("```", start)
                response_content = response_content[start:end].strip()
            elif "```" in response_content:
                start = response_content.find("```") + 3
                end = response_content.rfind("```")
                response_content = response_content[start:end].strip()

            # Clean up the JSON string - remove extra whitespace and normalize
            response_content = response_content.strip()

            # Try to find JSON object boundaries
            start_brace = response_content.find('{')
            end_brace = response_content.rfind('}')

            if start_brace != -1 and end_brace != -1:
                response_content = response_content[start_brace:end_brace+1]

            # Parse JSON
            parsed_response = json.loads(response_content)

            # Clean up keys that might have newlines or extra whitespace
            if isinstance(parsed_response, dict):
                logger.info(f"원본 JSON 키들: {list(parsed_response.keys())}")
                cleaned_response = {}
                for key, value in parsed_response.items():
                    clean_key = key.strip().replace('\n', '').replace('\r', '')
                    logger.info(f"키 변환: {repr(key)} -> {repr(clean_key)}")
                    cleaned_response[clean_key] = value
                parsed_response = cleaned_response
                logger.info(f"정리된 JSON 키들: {list(parsed_response.keys())}")

            # Pydantic 모델로 변환
            steps = []
            all_steps = parsed_response.get("steps", [])  # Get all steps for context

            for step_index, step in enumerate(all_steps):
                # 원본 영어 title, desc 가져오기
                original_title = step.get("title", "")
                original_desc = step.get("desc", "")

                # 한국어 요청 시 번역 수행
                if request.language == "ko":
                    translated_title = translate_text(original_title, "Korean")
                    translated_desc = translate_text(original_desc, "Korean")
                else:
                    translated_title = original_title
                    translated_desc = original_desc

                # 항상 우리의 WHO 스타일 프롬프트 사용 (기존 프롬프트 무시)
                gemini_prompt = build_gemini_prompt(
                    original_title,  # 프롬프트는 원본 영어로 생성
                    original_desc,
                    [],  # labels는 추후 추가 가능
                    request.procedure_name,  # 수술명 추가
                    all_steps,  # 모든 단계 전달
                    step_index  # 현재 단계의 인덱스
                )

                steps.append(SurgicalStep(
                    id=step.get("id", f"s{len(steps)+1}"),
                    index=step.get("index", len(steps)+1),
                    title=translated_title,
                    desc=translated_desc,
                    nanobanana_prompt=gemini_prompt
                ))

            return StepExtractionResponse(
                version=parsed_response.get("version", parsed_response.get("version", "v1")),
                procedure=parsed_response.get("procedure", {"name": request.procedure_name}),
                steps=steps
            )

        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {e}")
            logger.error(f"AI 응답 내용: {response_content}")
            raise ValueError(f"AI 응답을 파싱할 수 없습니다: {e}")

        except KeyError as e:
            logger.error(f"필수 필드 누락: {e}")
            logger.error(f"정리된 응답 내용: {response_content}")
            logger.error(f"파싱된 응답: {parsed_response}")
            raise ValueError(f"AI 응답에 필수 필드가 누락되었습니다: {e}")

    except Exception as e:
        logger.error(f"수술 단계 추출 실패: {e}")
        logger.error(f"요청: {request}")
        raise


@retry(
    wait=wait_exponential(multiplier=1, min=2, max=8),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(Exception)
)
async def generate_surgical_images_with_gemini(request: ImageGenerationRequest) -> ImageGenerationResponse:
    """
    Google Gemini API를 사용하여 수술 단계 이미지를 생성합니다.
    """
    settings = get_settings()
    job_id = f"job-{uuid.uuid4().hex[:12]}"

    # Generate trace ID for observability
    trace_id = f"trace-{uuid.uuid4().hex[:8]}"
    print(
        f"[DEBUG] 이미지 생성 시작 [traceId={trace_id}] "
        f"[jobId={job_id}] [steps={len(request.steps)}]"
    )
    for i, step in enumerate(request.steps):
        print(
            f"[DEBUG] Step {i+1}: id={step.id}, "
            f"title={step.title[:30]}..., "
            f"prompt={step.nanobanana_prompt[:50]}..."
        )
    logger.info(f"이미지 생성 시작 [traceId={trace_id}] [jobId={job_id}] [steps={len(request.steps)}]")

    # Gemini API 설정 확인
    gemini_api_key = getattr(settings, 'gemini_api_key', None)
    print(f"[DEBUG] Gemini API key 확인: {gemini_api_key[:10] if gemini_api_key else 'None'}...")

    if not gemini_api_key:
        print(f"[DEBUG] Gemini API 키가 없음!")
        logger.error(f"Gemini API 키가 설정되지 않음 [traceId={trace_id}] [jobId={job_id}]")
        raise HTTPException(
            status_code=502,
            detail="Gemini API key missing. Set GEMINI_API_KEY in environment."
        )

    try:
        generated_images = []

        # Gemini API 클라이언트 초기화
        import os
        print(f"[DEBUG] 환경변수 설정 중...")
        os.environ['GEMINI_API_KEY'] = gemini_api_key
        print(f"[DEBUG] Gemini 클라이언트 생성 중...")
        client = genai.Client()
        print(f"[DEBUG] Gemini 클라이언트 생성 완료")

        # Use semaphore to limit concurrent requests
        async def process_step(step: SurgicalStep) -> GeneratedImage:
            async with GEMINI_SEMAPHORE:
                step_id = step.id
                print(f"[DEBUG] process_step 시작 [stepId={step_id}]")
                logger.info(f"Gemini API 호출 시작 [traceId={trace_id}] [jobId={job_id}] [stepId={step_id}]")
                logger.info(f"단계 프롬프트: {step.nanobanana_prompt}")

                # Gemini 이미지 생성 프롬프트
                image_prompt = f"Generate a medical illustration: {step.nanobanana_prompt}. Style: clean educational diagram, white background, no text labels, professional medical illustration quality."
                print(f"[DEBUG] Gemini API 호출 시작 [stepId={step_id}]")

                try:
                    # Gemini 이미지 생성 API 사용
                    import asyncio
                    response = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: client.models.generate_content(
                            model="gemini-2.5-flash-image-preview",
                            contents=[image_prompt]
                        )
                    )

                    print(f"[DEBUG] Gemini API 응답 받음 [stepId={step_id}]")
                    logger.info(f"Gemini 이미지 API 응답 성공 [traceId={trace_id}] [jobId={job_id}] [stepId={step_id}]")

                    # Gemini 응답에서 이미지 데이터 추출
                    if response.candidates and len(response.candidates) > 0:
                        candidate = response.candidates[0]
                        if candidate.content and candidate.content.parts:
                            for part in candidate.content.parts:
                                # 텍스트 부분은 무시하고 이미지 데이터만 추출
                                if part.inline_data is not None:
                                    print(f"[DEBUG] 이미지 데이터 발견 [stepId={step_id}]")
                                    logger.info(f"이미지 데이터 발견 [stepId={step_id}]")
                                    return GeneratedImage(
                                        step_id=step_id,
                                        mime_type="image/png",
                                        data=base64.b64encode(part.inline_data.data).decode(),
                                        url=None
                                    )

                    # 이미지가 없는 경우 텍스트 응답으로 fallback
                    print(f"[DEBUG] 이미지 데이터 없음 [stepId={step_id}], 텍스트 응답으로 대체")
                    logger.warning(f"이미지 데이터 없음 [stepId={step_id}], 텍스트 응답으로 대체")

                    response_text = "No image generated"
                    if response.candidates and response.candidates[0].content.parts:
                        for part in response.candidates[0].content.parts:
                            if part.text:
                                response_text = part.text
                                break

                    image_data = base64.b64encode(response_text.encode()).decode()
                    return GeneratedImage(
                        step_id=step_id,
                        mime_type="text/plain",
                        data=image_data,
                        url=None
                    )

                except Exception as gemini_error:
                    print(f"[DEBUG] Gemini API 오류 [stepId={step_id}]: {gemini_error}")
                    logger.error(f"Gemini API 오류 [traceId={trace_id}] [stepId={step_id}]: {gemini_error}")

                    # Gemini API 에러를 적절한 HTTP 상태 코드로 매핑
                    if "authentication" in str(gemini_error).lower():
                        raise HTTPException(
                            status_code=502,
                            detail="Gemini API authentication failed. Check GEMINI_API_KEY."
                        )
                    elif "quota" in str(gemini_error).lower() or "rate" in str(gemini_error).lower():
                        raise HTTPException(
                            status_code=429,
                            detail="Gemini API rate limit exceeded. Please try again later."
                        )
                    else:
                        raise HTTPException(
                            status_code=502,
                            detail=f"Gemini API error: {str(gemini_error)}"
                        )

        # Process all steps concurrently with semaphore control
        print(f"[DEBUG] 이미지 생성 작업 시작 [traceId={trace_id}] [steps={len(request.steps)}]")
        logger.info(f"이미지 생성 작업 시작 [traceId={trace_id}] [steps={len(request.steps)}]")

        print(f"[DEBUG] 태스크 생성 중...")
        tasks = [process_step(step) for step in request.steps]
        print(f"[DEBUG] 태스크 {len(tasks)}개 생성됨, asyncio.gather 실행 중...")

        generated_images = await asyncio.gather(*tasks)
        print(f"[DEBUG] asyncio.gather 완료, 생성된 이미지: {len(generated_images)}개")
        logger.info(f"이미지 생성 작업 완료 [traceId={trace_id}] [images={len(generated_images)}]")

        logger.info(f"이미지 생성 완료 [traceId={trace_id}] [jobId={job_id}] [images={len(generated_images)}]")
        return ImageGenerationResponse(
            job_id=job_id,
            images=generated_images
        )

    except HTTPException:
        # Re-raise HTTP exceptions with proper status codes
        print(f"[DEBUG] HTTPException 발생!")
        raise
    except Exception as e:
        print(f"[DEBUG] 예외 발생: {type(e).__name__}: {e}")
        logger.error(f"Gemini 이미지 생성 실패 [traceId={trace_id}] [jobId={job_id}]: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal error during image generation. Please try again later."
        )


async def generate_surgical_images_complete(
    request: SurgicalImageGenerationRequest
) -> SurgicalImageGenerationResponse:
    """
    완전한 수술 이미지 생성 플로우: 단계 추출 + 이미지 생성
    """
    # Generate trace ID for the complete flow
    trace_id = f"trace-{uuid.uuid4().hex[:8]}"
    logger.info(f"수술 이미지 생성 플로우 시작 [traceId={trace_id}] [procedure={request.procedure_name}] [maxSteps={request.max_steps}]")

    try:
        # 1단계: 수술 단계 추출
        logger.info(f"단계 추출 시작 [traceId={trace_id}]")
        step_extraction_request = StepExtractionRequest(
            procedure_name=request.procedure_name,
            max_steps=request.max_steps,
            language=request.language
        )

        step_extraction_response = await extract_surgical_steps(step_extraction_request)
        logger.info(f"단계 추출 완료 [traceId={trace_id}] [steps={len(step_extraction_response.steps)}]")

        # 2단계: 이미지 생성
        logger.info(f"이미지 생성 시작 [traceId={trace_id}]")
        logger.info(f"추출된 단계 수: {len(step_extraction_response.steps)}")

        image_generation_request = ImageGenerationRequest(
            steps=step_extraction_response.steps
        )
        logger.info(f"이미지 생성 요청 생성됨 [traceId={trace_id}]")

        image_generation_response = await generate_surgical_images_with_gemini(image_generation_request)
        logger.info(f"이미지 생성 응답 받음 [traceId={trace_id}]")
        logger.info(f"이미지 생성 완료 [traceId={trace_id}] [jobId={image_generation_response.job_id}]")

        # 결과 통합
        result = SurgicalImageGenerationResponse(
            procedure_name=request.procedure_name,
            steps=step_extraction_response.steps,
            images=image_generation_response.images,
            job_id=image_generation_response.job_id
        )

        logger.info(
            f"수술 이미지 생성 플로우 완료 [traceId={trace_id}] "
            f"[jobId={image_generation_response.job_id}] "
            f"[steps={len(result.steps)}] [images={len(result.images)}]"
        )
        return result

    except Exception as e:
        logger.error(f"수술 이미지 생성 플로우 실패 [traceId={trace_id}]: {e}")
        raise
