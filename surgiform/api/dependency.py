from fastapi import Depends
from elasticsearch import Elasticsearch
from langchain_core.language_models.chat_models import BaseChatModel

from surgiform.external.openai_client import get_chat_llm
from surgiform.external.es_client import get_es_client


def get_llm() -> BaseChatModel:
    return get_chat_llm()


def get_es() -> Elasticsearch:
    return get_es_client()


# 사용 예시 (라우터 파일에서)
# @router.post(...)
# async def handler(..., llm: BaseChatModel = Depends(get_llm)):
#     ...