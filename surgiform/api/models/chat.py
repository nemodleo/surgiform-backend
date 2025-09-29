from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Any
from datetime import datetime
from surgiform.api.models.base import ConsentBase, ReferenceBase


class ChatMessage(BaseModel):
    """채팅 메시지"""
    role: Literal["user", "assistant", "system"] = Field(..., description="메시지 역할")
    content: str = Field(..., description="메시지 내용")
    timestamp: Optional[datetime] = Field(default=None, description="메시지 시간")


class ChatRequest(BaseModel):
    """채팅 요청"""
    message: str = Field(..., description="사용자 메시지")
    conversation_id: Optional[str] = Field(default=None, description="대화 ID")
    history: Optional[List[ChatMessage]] = Field(default=[], description="대화 히스토리")
    system_prompt: Optional[str] = Field(default=None, description="시스템 프롬프트")
    consents: Optional[Any] = Field(default=None, description="원본 수술동의서")
    references: Optional[Any] = Field(default=None, description="참고 문헌")


class ChatResponse(BaseModel):
    """채팅 응답"""
    message: str = Field(..., description="AI 응답 메시지")
    conversation_id: str = Field(..., description="대화 ID")
    history: List[ChatMessage] = Field(..., description="업데이트된 대화 히스토리")
    updated_consents: Optional[ConsentBase] = Field(default=None, description="업데이트된 수술동의서 (변경 요청시에만)")
    updated_references: Optional[ReferenceBase] = Field(default=None, description="업데이트된 참고 문헌 (변경 요청시에만)")
    is_content_modified: bool = Field(default=False, description="동의서 내용이 수정되었는지 여부")


class ChatSessionRequest(BaseModel):
    """채팅 세션 생성 요청"""
    system_prompt: Optional[str] = Field(default=None, description="시스템 프롬프트")


class ChatSessionResponse(BaseModel):
    """채팅 세션 생성 응답"""
    conversation_id: str = Field(..., description="생성된 대화 ID")
    message: str = Field(..., description="세션 생성 확인 메시지")


class ChatSessionInfo(BaseModel):
    """채팅 세션 정보"""
    conversation_id: str = Field(..., description="대화 ID")
    created_at: Optional[datetime] = Field(default=None, description="세션 생성 시간")
    last_message_at: Optional[datetime] = Field(default=None, description="마지막 메시지 시간")
    message_count: int = Field(..., description="메시지 개수")
    last_message: Optional[str] = Field(default=None, description="마지막 메시지 (미리보기)")
    system_prompt: Optional[str] = Field(default=None, description="시스템 프롬프트")


class ChatSessionListResponse(BaseModel):
    """채팅 세션 목록 응답"""
    sessions: List[ChatSessionInfo] = Field(..., description="채팅 세션 목록")
    total_count: int = Field(..., description="전체 세션 개수")


class EditChatRequest(BaseModel):
    """채팅 편집 요청"""
    message: str = Field(..., description="사용자 메시지")
    conversation_id: Optional[str] = Field(default=None, description="대화 ID")
    history: Optional[List[ChatMessage]] = Field(default=[], description="대화 히스토리")
    system_prompt: Optional[str] = Field(default=None, description="시스템 프롬프트")
    consents: Optional[Any] = Field(default=None, description="원본 수술동의서")
    references: Optional[Any] = Field(default=None, description="참고 문헌")
    edit_sections: List[Literal["2", "3", "4", "5-1", "5-2", "5-3", "5-4", "5-5", "6", "7", "8"]] = Field(..., description="수정하고자 하는 섹션 목록")


class EditChatResponse(BaseModel):
    """채팅 편집 응답"""
    message: str = Field(..., description="AI 응답 메시지")
    conversation_id: str = Field(..., description="대화 ID")
    history: List[ChatMessage] = Field(..., description="업데이트된 대화 히스토리")
    edited_sections: dict[str, str] = Field(..., description="수정된 섹션별 내용")
    updated_consents: Optional[ConsentBase] = Field(default=None, description="업데이트된 수술동의서")
    updated_references: Optional[ReferenceBase] = Field(default=None, description="업데이트된 참고 문헌") 