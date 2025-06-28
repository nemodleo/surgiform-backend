import uuid
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
from surgiform.external.openai_client import get_chat_llm
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


# 메모리 기반 대화 저장소 (실제 환경에서는 DB 사용 권장)
_conversations: Dict[str, List[ChatMessage]] = {}


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
    
    # LangChain 메시지 형식으로 변환
    messages = []
    for msg in history:
        if msg.role == "system":
            messages.append(SystemMessage(content=msg.content))
        elif msg.role == "user":
            messages.append(HumanMessage(content=msg.content))
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
        history=history
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