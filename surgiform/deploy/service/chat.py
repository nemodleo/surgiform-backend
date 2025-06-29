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
    
    if is_modification_request and payload.consents and payload.references:
        # 수술 동의서 변환 처리
        try:
            transform_mode = _determine_transform_mode(payload.message)
            
            # 변환 실행
            transformed_consents, transformed_references = run_transform(
                payload.consents, 
                payload.references, 
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
        # 수술 동의서 내용이 있으면 컨텍스트로 활용
        context_message = ""
        if payload.consents:
            context_message = f"\n\n[참고: 현재 수술 동의서 내용]\n{json.dumps(payload.consents.model_dump(), ensure_ascii=False, indent=2)}"
        
        # LangChain 메시지 형식으로 변환
        messages = []
        for msg in history:
            if msg.role == "system":
                messages.append(SystemMessage(content=msg.content))
            elif msg.role == "user":
                # 마지막 사용자 메시지에 컨텍스트 추가
                content = msg.content + context_message if msg == history[-1] else msg.content
                messages.append(HumanMessage(content=content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))
        
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