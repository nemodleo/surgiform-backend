"""Elasticsearch 8.x 클라이언트 헬퍼"""

from functools import lru_cache
from elasticsearch import Elasticsearch
from surgiform.deploy.settings import get_settings


@lru_cache
def get_es_client() -> Elasticsearch:
    settings = get_settings()
    return Elasticsearch(
        hosts=[settings.es_host],
        basic_auth=(settings.es_user, settings.es_password)
        if settings.es_user
        else None,
        request_timeout=30,
    )


# ─────────────────────────────────────────────────────────
# 간단한 벡터 검색 util (dot-product KNN, ES 8.13+)
# ─────────────────────────────────────────────────────────
def knn_search(
    index: str,
    vector: list[float],
    k: int = 5,
    num_candidates: int = 100,
    filter_query: dict | None = None,
) -> list[dict]:
    es = get_es_client()
    body = {
        "size": k,
        "knn": {
            "field": "embedding",
            "query_vector": vector,
            "k": k,
            "num_candidates": num_candidates,
        },
    }
    if filter_query:
        body["query"] = {"bool": {"filter": filter_query}}

    resp = es.search(index=index, body=body)
    return resp["hits"]["hits"]  # 리스트[dict]