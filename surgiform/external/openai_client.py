"""LangChain-OpenAI 래퍼 (ChatCompletion 전용)"""

from functools import lru_cache
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from surgiform.deploy.settings import get_settings
import openai


@lru_cache
def get_chat_llm(
        model_name: str = "gpt-4.1",
        temperature: float = 0.2
) -> BaseChatModel:
    """싱글턴 ChatOpenAI 인스턴스 반환 (gpt-4.1, temperature 0.2)."""
    settings = get_settings()
    return ChatOpenAI(
        model_name=model_name,
        temperature=temperature,
        api_key=settings.openai_api_key,
    )


@lru_cache
def get_openai_client():
    """OpenAI 클라이언트 반환 (embeddings용)"""
    settings = get_settings()
    client = openai.OpenAI(api_key=settings.openai_api_key)
    return client


# TODO: get_key_word_list_from_text
def get_key_word_list_from_text(
        text: str | None,
        max_keywords: int = -1,
        model_name: str = "gpt-3.5-turbo",
        temperature: float = 0.2
) -> list[str | None]:
    """
    텍스트에서 키워드를 추출하는 함수
    
    Args:
        text: 키워드를 추출할 텍스트
        max_keywords: 추출할 최대 키워드 수 (기본값: 10)
        
    Returns:
        추출된 키워드 리스트
    """
    if text is None:
        return []

    llm = get_chat_llm(model_name=model_name, temperature=temperature)
    
    prompt = f"""Extract the most important keywords from the following text.

Text:
{text}

Please output keywords separated by commas in a single line. Example:
keyword1, keyword2, keyword3, ...

Keywords:"""

    response = llm.invoke(prompt)
    keywords_text = response.content.strip()

    # 쉼표로 구분된 키워드를 리스트로 변환
    keywords = [keyword.strip() for keyword in keywords_text.split(',')]

    # 빈 문자열 제거 및 최대 개수 제한
    keywords = [kw for kw in keywords if kw]
    if max_keywords > 0:
        keywords = keywords[:max_keywords]

    return keywords


def translate_text(
        text: str,
        target_language: str = "English",
        model_name: str = "gpt-3.5-turbo",
        temperature: float = 0.2
) -> str:
    """
    텍스트를 번역하는 함수
    """
    llm = get_chat_llm(model_name=model_name, temperature=temperature)
    prompt = f"""Translate the following text into {target_language}.

    Text:
    {text}

    Translated text:"""

    response = llm.invoke(prompt)
    return response.content.strip()
