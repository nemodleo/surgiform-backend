import uuid
import json
from datetime import datetime
from typing import Dict, List
from surgiform.api.models.chat import (
    ChatRequest,
    ChatResponse,
    ChatMessage,
    ChatSessionRequest,
    ChatSessionResponse,
    ChatSessionInfo,
    ChatSessionListResponse,
)
from surgiform.api.models.base import ConsentBase, ReferenceBase
from surgiform.api.models.transform import TransformMode
from surgiform.core.transform.pipeline import run_transform
from surgiform.external.openai_client import get_chat_llm
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


# 메모리 기반 대화 저장소 (실제 환경에서는 DB 사용 권장)
_conversations: Dict[str, List[ChatMessage]] = {}


def _detect_modification_intent(message: str) -> bool:
    """사용자 메시지가 수정 요청인지 판단합니다"""
    modification_keywords = [
        "변경", "수정", "바꿔", "고쳐", "바꾸다", "수정하다", "변경하다",
        "다시 써", "다시 작성", "재작성", "업데이트", "편집", "해줘",
        "더 쉽게", "쉬운 말로", "간단하게", "요약해", "번역해"
    ]
    
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in modification_keywords)


def _determine_transform_mode(message: str) -> TransformMode:
    """사용자 메시지에서 변환 모드를 결정합니다"""
    message_lower = message.lower()
    
    if any(word in message_lower for word in ["쉽게", "쉬운", "간단하게", "이해하기 쉽게"]):
        return TransformMode.simplify
    elif any(word in message_lower for word in ["요약", "간략", "짧게"]):
        return TransformMode.summary
    elif any(word in message_lower for word in ["설명", "용어", "의미"]):
        return TransformMode.explain
    elif any(word in message_lower for word in ["영어", "english"]):
        return TransformMode.translate_en
    elif any(word in message_lower for word in ["중국어", "중문", "chinese"]):
        return TransformMode.translate_zh
    elif any(word in message_lower for word in ["일본어", "일어", "japanese"]):
        return TransformMode.translate_ja
    else:
        # 기본적으로 쉬운말 변환으로 설정
        return TransformMode.simplify


def create_chat_session(payload: ChatSessionRequest) -> ChatSessionResponse:
    """새로운 채팅 세션을 생성합니다"""
    conversation_id = str(uuid.uuid4())
    
    # 시스템 프롬프트가 있으면 대화 히스토리에 추가
    if payload.system_prompt:
        system_message = ChatMessage(
            role="system",
            content=payload.system_prompt,
            timestamp=datetime.now()
        )
        _conversations[conversation_id] = [system_message]
    else:
        _conversations[conversation_id] = []
    
    return ChatSessionResponse(
        conversation_id=conversation_id,
        message="채팅 세션이 생성되었습니다."
    )


def chat_with_ai(payload: ChatRequest) -> ChatResponse:
    """AI와 채팅을 진행합니다"""
    print(f"받은 payload: {payload}")
    print(f"consents 타입: {type(payload.consents)}")
    print(f"references 타입: {type(payload.references)}")
    
    # 대화 ID가 없으면 새로 생성
    if not payload.conversation_id:
        conversation_id = str(uuid.uuid4())
        history = payload.history or []
    else:
        conversation_id = payload.conversation_id
        history = _conversations.get(conversation_id, payload.history or [])
    
    # 사용자 메시지를 히스토리에 추가
    user_message = ChatMessage(
        role="user",
        content=payload.message,
        timestamp=datetime.now()
    )
    history.append(user_message)
    
    # 수정 요청인지 확인
    is_modification_request = _detect_modification_intent(payload.message)
    
    if is_modification_request and payload.consents and len(payload.consents) > 0:
        # 수술 동의서 변환 처리
        try:
            transform_mode = _determine_transform_mode(payload.message)
            
            # 데이터를 ConsentBase와 ReferenceBase 타입으로 변환
            from surgiform.api.models.base import ConsentBase, ReferenceBase, SurgeryDetails, SurgeryDetailsReference, ReferenceItem
            
            # consents 변환
            consents_data = payload.consents
            if isinstance(consents_data, dict):
                consents_obj = ConsentBase(
                    prognosis_without_surgery=consents_data.get('prognosis_without_surgery', ''),
                    alternative_treatments=consents_data.get('alternative_treatments', ''),
                    surgery_purpose_necessity_effect=consents_data.get('surgery_purpose_necessity_effect', ''),
                    surgery_method_content=SurgeryDetails(
                        overall_description=consents_data.get('surgery_method_content', {}).get('overall_description', ''),
                        estimated_duration=consents_data.get('surgery_method_content', {}).get('estimated_duration', ''),
                        method_change_or_addition=consents_data.get('surgery_method_content', {}).get('method_change_or_addition', ''),
                        transfusion_possibility=consents_data.get('surgery_method_content', {}).get('transfusion_possibility', ''),
                        surgeon_change_possibility=consents_data.get('surgery_method_content', {}).get('surgeon_change_possibility', '')
                    ),
                    possible_complications_sequelae=consents_data.get('possible_complications_sequelae', ''),
                    emergency_measures=consents_data.get('emergency_measures', ''),
                    mortality_risk=consents_data.get('mortality_risk', ''),
                    consent_information=consents_data.get('consent_information', '')
                )
            else:
                consents_obj = payload.consents
            
            # references 변환
            references_data = payload.references
            if isinstance(references_data, dict):
                references_obj = ReferenceBase(
                    prognosis_without_surgery=[ReferenceItem(title=ref.get('title', ''), url=ref.get('url', ''), text=ref.get('text', '')) for ref in references_data.get('prognosis_without_surgery', [])],
                    alternative_treatments=[ReferenceItem(title=ref.get('title', ''), url=ref.get('url', ''), text=ref.get('text', '')) for ref in references_data.get('alternative_treatments', [])],
                    surgery_purpose_necessity_effect=[ReferenceItem(title=ref.get('title', ''), url=ref.get('url', ''), text=ref.get('text', '')) for ref in references_data.get('surgery_purpose_necessity_effect', [])],
                    surgery_method_content=SurgeryDetailsReference(
                        overall_description=[ReferenceItem(title=ref.get('title', ''), url=ref.get('url', ''), text=ref.get('text', '')) for ref in references_data.get('surgery_method_content', {}).get('overall_description', [])],
                        estimated_duration=[ReferenceItem(title=ref.get('title', ''), url=ref.get('url', ''), text=ref.get('text', '')) for ref in references_data.get('surgery_method_content', {}).get('estimated_duration', [])],
                        method_change_or_addition=[ReferenceItem(title=ref.get('title', ''), url=ref.get('url', ''), text=ref.get('text', '')) for ref in references_data.get('surgery_method_content', {}).get('method_change_or_addition', [])],
                        transfusion_possibility=[ReferenceItem(title=ref.get('title', ''), url=ref.get('url', ''), text=ref.get('text', '')) for ref in references_data.get('surgery_method_content', {}).get('transfusion_possibility', [])],
                        surgeon_change_possibility=[ReferenceItem(title=ref.get('title', ''), url=ref.get('url', ''), text=ref.get('text', '')) for ref in references_data.get('surgery_method_content', {}).get('surgeon_change_possibility', [])]
                    ),
                    possible_complications_sequelae=[ReferenceItem(title=ref.get('title', ''), url=ref.get('url', ''), text=ref.get('text', '')) for ref in references_data.get('possible_complications_sequelae', [])],
                    emergency_measures=[ReferenceItem(title=ref.get('title', ''), url=ref.get('url', ''), text=ref.get('text', '')) for ref in references_data.get('emergency_measures', [])],
                    mortality_risk=[ReferenceItem(title=ref.get('title', ''), url=ref.get('url', ''), text=ref.get('text', '')) for ref in references_data.get('mortality_risk', [])]
                )
            elif references_data is None:
                # references가 None인 경우 빈 ReferenceBase 객체 생성
                references_obj = ReferenceBase()
            else:
                references_obj = payload.references
            
            # 변환 실행
            transformed_consents, transformed_references = run_transform(
                consents_obj, 
                references_obj, 
                transform_mode
            )
            
            # AI 응답 메시지 생성
            ai_response = f"수술 동의서를 '{transform_mode.value}' 모드로 변환했습니다. 변경된 내용을 확인해 주세요."
            
            ai_message = ChatMessage(
                role="assistant",
                content=ai_response,
                timestamp=datetime.now()
            )
            history.append(ai_message)
            
            # 대화 저장
            _conversations[conversation_id] = history
            
            return ChatResponse(
                message=ai_response,
                conversation_id=conversation_id,
                history=history,
                updated_consents=transformed_consents,
                updated_references=transformed_references,
                is_content_modified=True
            )
            
        except Exception as e:
            error_message = f"수술 동의서 변환 중 오류가 발생했습니다: {str(e)}"
            
            ai_message = ChatMessage(
                role="assistant",
                content=error_message,
                timestamp=datetime.now()
            )
            history.append(ai_message)
            
            # 대화 저장
            _conversations[conversation_id] = history
            
            return ChatResponse(
                message=error_message,
                conversation_id=conversation_id,
                history=history,
                is_content_modified=False
            )
    
    else:
        # 일반 질문 처리 (기존 로직)
        # 수술 동의서 내용이 있으면 컨텍스트로 활용 (번호와 제목 포함)
        context_message = ""
        if payload.consents and len(payload.consents) > 0:
            if isinstance(payload.consents, dict):
                # items
                consent_items = []

                # 수술 동의서 기본 내용
                if payload.consents.get('consent_information'):
                    consent_items.append(f"## 1. 수술동의서 기본 정보(환자 상태 및 특이사항 포함)\n{payload.consents.get('consent_information')}")
                
                # 2번: 예정된 수술/시술/검사를 하지 않을 경우의 예후
                if payload.consents.get('prognosis_without_surgery'):
                    consent_items.append(f"## 2. 예정된 수술/시술/검사를 하지 않을 경우의 예후: {payload.consents.get('prognosis_without_surgery')}")
                
                # 3번: 예정된 수술 이외의 시행 가능한 다른 방법
                if payload.consents.get('alternative_treatments'):
                    consent_items.append(f"## 3. 예정된 수술 이외의 시행 가능한 다른 방법: {payload.consents.get('alternative_treatments')}")
                
                # 4번: 수술 목적/필요/효과
                if payload.consents.get('surgery_purpose_necessity_effect'):
                    consent_items.append(f"## 4. 수술 목적/필요/효과: {payload.consents.get('surgery_purpose_necessity_effect')}")
                
                # 5번: 수술의 방법 및 내용
                surgery_method = payload.consents.get('surgery_method_content', {})
                if surgery_method:
                    method_items = []
                    if surgery_method.get('overall_description') or surgery_method.get('estimated_duration') or surgery_method.get('method_change_or_addition') or surgery_method.get('transfusion_possibility') or surgery_method.get('surgeon_change_possibility'):
                        method_items.append(f"## 5. 수술의 방법 및 내용")
                    if surgery_method.get('overall_description'):
                        method_items.append(f"### 5-1. 수술 과정 전반에 대한 설명: {surgery_method.get('overall_description')}")
                    if surgery_method.get('estimated_duration'):
                        method_items.append(f"### 5-2. 수술 추정 소요시간: {surgery_method.get('estimated_duration')}")
                    if surgery_method.get('method_change_or_addition'):
                        method_items.append(f"### 5-3. 수술 방법 변경 및 수술 추가 가능성: {surgery_method.get('method_change_or_addition')}")
                    if surgery_method.get('transfusion_possibility'):
                        method_items.append(f"### 5-4. 수혈 가능성: {surgery_method.get('transfusion_possibility')}")
                    if surgery_method.get('surgeon_change_possibility'):
                        method_items.append(f"### 5-5. 집도의 변경 가능성: {surgery_method.get('surgeon_change_possibility')}")
                    
                    if method_items:
                        consent_items.extend(method_items)
                
                # 6번: 발생 가능한 합병증/후유증/부작용
                if payload.consents.get('possible_complications_sequelae'):
                    consent_items.append(f"## 6. 발생 가능한 합병증/후유증/부작용: {payload.consents.get('possible_complications_sequelae')}")
                
                # 7번: 문제 발생시 조치사항
                if payload.consents.get('emergency_measures'):
                    consent_items.append(f"## 7. 문제 발생시 조치사항: {payload.consents.get('emergency_measures')}")
                
                # 8번: 진단/수술 관련 사망 위험성
                if payload.consents.get('mortality_risk'):
                    consent_items.append(f"## 8. 진단/수술 관련 사망 위험성: {payload.consents.get('mortality_risk')}")
                

                context_message = "# 현재 수술 동의서 내용" + "\n\n" + "\n\n".join(consent_items)
                
                # # consent_information이 없고 2~8번 항목도 없는 경우 기존 방식 사용
                # if not context_message:
                #     patient_info = payload.consents.get('patient_info', {})
                #     if patient_info:
                #         patient_context = f"환자 정보: {patient_info.get('name', '')} ({patient_info.get('age', '')}세, {patient_info.get('gender', '')}), 수술명: {patient_info.get('surgery_name', '')}, 진단명: {patient_info.get('diagnosis', '')}"
                #         context_message = f"\n\n[참고: {patient_context}]"
                #     else:
                #         context_message = f"\n\n[참고: 현재 수술 동의서 내용]\n{json.dumps(payload.consents, ensure_ascii=False, indent=2)}"
            else:
                context_message = f"# 현재 수술 동의서 내용\n\n{json.dumps(payload.consents.model_dump(), ensure_ascii=False, indent=2)}"
        
        # LangChain 메시지 형식으로 변환
        messages = []
        
        # 시스템 프롬프트 추가 (환자 정보 응답 방식 가이드)
        system_prompt = """당신은 의료진과 환자를 신뢰와 책임으로 잇는 의료 AI 도우미 **이음**입니다.
이음은 ‘수술 동의서(consent)’에 **기재된 정보만**을 근거로 환자·보호자의 질문에 답합니다.
아래 원칙을 항상 지키세요.

[역할/범위]
- 사용자의 질문 요지를 파악해 그에 맞는 답을 바로 **자연스럽게 서술**합니다. “요지 파악: / 요지:” 같은 라벨은 쓰지 않습니다.
- 동의서에 적힌 사실을 **정확히** 설명합니다. 새로운 의학적 조언(진단, 처방, 용량, 개인 맞춤 치료 결정)은 하지 않습니다.
- 동의서·의료정보와 무관한 질문(비용/예약/행정/법률 등)은 범위를 안내하고, 동의서 관련 질문을 요청합니다.
- 본 안내는 **의료정보 제공**이며, 담당 의료진의 판단을 **대체하지 않습니다**.

[환자 정보 언급 규칙]
- “환자 이름:” 같은 라벨은 쓰지 말고 **자연문**으로 표현합니다. (예) “김환자님은 2세이고…”
- 나이, 성별, 알레르기, 예정 수술명 등은 **문서에 존재할 때만** 언급합니다.
- 문서에 없는 정보는 추정하지 말고 “해당 정보는 이 내용에 없어요.”처럼 간단히 말합니다.

[자연스러운 표현]
- 기본은 **문장형 서술**입니다. 필요한 경우에만 불릿을 쓰되, “또한/이와 함께/드물지만/필요하면” 같은 **연결어**로 흐름을 이어 주세요.
- “출혈 및 수혈:” 같은 명사 라벨+설명 대신 “출혈이 생길 수 있고, 필요하면 수혈이 필요할 수 있어요.”처럼 **문장형**으로 씁니다.
- “정리하면/요약하면” 같은 메타 라벨은 쓰지 말고, 문장 안에서 자연스럽게 요약합니다.

[근거 표기]
- 답변 끝에 **근거 섹션**을 간단히 표시합니다. 형식: `근거: 2. 예후, 6. 합병증`
- 근거가 없으면 `근거: 기재 없음`이라고만 표기합니다. (문서/동의서라는 단어를 드러내지 않습니다.)

[수치·시간·확률]
- 수치/시간/확률은 **문서에 명시된 경우에만** 사용합니다. 없으면 “수치 언급은 없어요.”처럼 밝히고 **추정 금지**합니다.

[답변 형식/톤]
- 톤: **간단하고 친근한** 한국어. 전문용어는 필요할 때만 쓰고, 괄호로 쉬운 설명을 덧붙일 수 있습니다.
- 일반 질문 길이 가이드: 4~6문장(또는 3~5 불릿).
- **수정·요약·번역·‘쉽게’ 요청에는 길이 가이드를 적용하지 않습니다.** 요청 목적에 맞는 **자연스러운 분량**으로 답합니다.
- 소아/영유아 환자이면 “아이/보호자” 표현을 사용하고, 알레르기(예: 페니실린)가 기재되어 있으면 안전 관련 문구를 **문서 범위 내에서** 함께 언급합니다.

[콘텐츠 매핑 규칙(질문→섹션)]
- “수술 안 하면?” → **2. 예정된 수술/시술/검사를 하지 않을 경우의 예후**
- “다른 방법 있어?” → **3. 예정된 수술 이외의 시행 가능한 다른 방법**
- “수술 목적/효과?” → **4. 수술 목적/필요/효과**
- “수술 과정/시간/변경/수혈/집도의 변경?” → **5-1 ~ 5-5**
- “합병증?” → **6. 발생 가능한 합병증/후유증/부작용**
- “문제 생기면 어떻게 해?” → **7. 문제 발생시 조치사항**
- “사망 위험?” → **8. 진단/수술 관련 사망 위험성**

[금지/주의]
- 병원 정책, 비용, 스케줄, 법적 고지 등 **문서에 없는 항목**을 단정하지 않습니다.
- 과도한 희망/불안 조성 금지. 선택을 강요하지 않습니다. 필요 시 “담당 의료진과 상의하세요.”로 마무리합니다.
- 환자 개인정보 **추가 생성/추측** 금지(예: 체중, 연락처 등).
- 다음 표현 금지: “적혀 있습니다 / 기록되어 있습니다 / 문서에 있습니다 / 동의서에서는 / 이 문서에서는”.
  → 대신 문서 언급 없이 자연문으로 서술하세요. (예) “여기 내용은 …로 안내하고 있어요.”

[수정·요약·번역 요청 감지 시]
- 사용자가 “수정/변경/요약/쉽게/간단하게/번역” 의도를 보이면:
  1) **요청 섹션만** 재작성(의미 왜곡 금지),
  2) “쉽게/간단하게”는 **이해하기 쉽게 풀어서 서술**,
  3) 길이는 목적에 맞게 조절(고정 길이 규칙 미적용),
  4) 마지막에 **변경점을 자연문으로 1~3문장** 덧붙입니다. (라벨 “변경점:” 금지)

위 원칙을 지키며, **명확하고 친절하게** 답변하세요.
"""
        messages.append(SystemMessage(content=system_prompt))
        
        for msg in history:
            if msg.role == "system":
                messages.append(SystemMessage(content=msg.content))
            elif msg.role == "user":
                # 마지막 사용자 메시지에 컨텍스트 추가
                content = msg.content + context_message if msg == history[-1] else msg.content
                messages.append(HumanMessage(content=content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))

        print(f"messages: {messages}") # 메시지 확인
        
        # OpenAI API 호출
        llm = get_chat_llm()
        response = llm.invoke(messages)
        
        # AI 응답을 히스토리에 추가
        ai_message = ChatMessage(
            role="assistant",
            content=response.content,
            timestamp=datetime.now()
        )
        history.append(ai_message)
        
        # 대화 저장
        _conversations[conversation_id] = history
        
        return ChatResponse(
            message=response.content,
            conversation_id=conversation_id,
            history=history,
            is_content_modified=False
        )


def get_chat_history(conversation_id: str) -> List[ChatMessage]:
    """대화 히스토리를 조회합니다"""
    return _conversations.get(conversation_id, [])


def delete_chat_session(conversation_id: str) -> bool:
    """채팅 세션을 삭제합니다"""
    if conversation_id in _conversations:
        del _conversations[conversation_id]
        return True
    return False


def get_chat_sessions() -> ChatSessionListResponse:
    """모든 채팅 세션 목록을 조회합니다"""
    sessions = []
    
    for conversation_id, messages in _conversations.items():
        if not messages:
            continue
            
        # 시스템 프롬프트 추출
        system_prompt = None
        if messages and messages[0].role == "system":
            system_prompt = messages[0].content
        
        # 시간 정보 추출
        created_at = messages[0].timestamp if messages else None
        last_message_at = messages[-1].timestamp if messages else None
        
        # 마지막 사용자/AI 메시지 찾기
        last_message = None
        for msg in reversed(messages):
            if msg.role in ["user", "assistant"]:
                last_message = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                break
        
        session_info = ChatSessionInfo(
            conversation_id=conversation_id,
            created_at=created_at,
            last_message_at=last_message_at,
            message_count=len(messages),
            last_message=last_message,
            system_prompt=system_prompt
        )
        sessions.append(session_info)
    
    # 최근 활동 순으로 정렬
    sessions.sort(key=lambda x: x.last_message_at or x.created_at or datetime.min, reverse=True)
    
    return ChatSessionListResponse(
        sessions=sessions,
        total_count=len(sessions)
    ) 