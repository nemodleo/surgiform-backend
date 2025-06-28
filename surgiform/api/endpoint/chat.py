from fastapi import APIRouter, HTTPException
from typing import List
from surgiform.api.models.chat import (
    ChatRequest,
    ChatResponse,
    ChatMessage,
    ChatSessionRequest,
    ChatSessionResponse,
    ChatSessionListResponse,
)
from surgiform.deploy.service.chat import (
    create_chat_session,
    chat_with_ai,
    get_chat_history,
    delete_chat_session,
    get_chat_sessions,
)

router = APIRouter(tags=["chat"])


@router.post(
    "/chat/session",
    response_model=ChatSessionResponse,
    summary="채팅 세션 생성",
    description="새로운 채팅 세션을 생성합니다. 시스템 프롬프트를 설정할 수 있습니다."
)
async def create_session(payload: ChatSessionRequest) -> ChatSessionResponse:
    return create_chat_session(payload)


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="AI와 채팅",
    description="AI와 채팅을 진행합니다. 기존 대화 ID를 제공하면 이어서 대화하고, 없으면 새로운 대화를 시작합니다."
)
async def chat(payload: ChatRequest) -> ChatResponse:
    try:
        return chat_with_ai(payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"채팅 처리 중 오류가 발생했습니다: {str(e)}")


@router.get(
    "/chat/{conversation_id}/history",
    response_model=List[ChatMessage],
    summary="대화 히스토리 조회",
    description="특정 대화 ID의 히스토리를 조회합니다."
)
async def get_history(conversation_id: str) -> List[ChatMessage]:
    history = get_chat_history(conversation_id)
    if not history:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다.")
    return history


@router.get(
    "/chat/sessions",
    response_model=ChatSessionListResponse,
    summary="채팅 세션 목록 조회",
    description="모든 채팅 세션의 목록을 조회합니다. 최근 활동 순으로 정렬됩니다."
)
async def list_sessions() -> ChatSessionListResponse:
    return get_chat_sessions()


@router.delete(
    "/chat/{conversation_id}",
    summary="채팅 세션 삭제",
    description="특정 대화 ID의 채팅 세션을 삭제합니다."
)
async def delete_session(conversation_id: str) -> dict:
    success = delete_chat_session(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다.")
    return {"message": "채팅 세션이 삭제되었습니다.", "conversation_id": conversation_id} 