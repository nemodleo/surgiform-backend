"""LangChain-OpenAI 래퍼 (ChatCompletion 전용)"""

from functools import lru_cache
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from surgiform.deploy.settings import get_settings


@lru_cache
def get_chat_llm() -> BaseChatModel:
    """싱글턴 ChatOpenAI 인스턴스 반환 (gpt-4.1, temperature 0.2)."""
    settings = get_settings()
    return ChatOpenAI(
        model_name="gpt-4.1",
        temperature=0.2,
        api_key=settings.openai_api_key,
    )