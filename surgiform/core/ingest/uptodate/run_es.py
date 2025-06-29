import sys
import os
from elasticsearch import AsyncElasticsearch
from dotenv import load_dotenv

load_dotenv()

ES_HOST = os.getenv("ES_HOST")


def filter_score(response, score_threshold=20):
    return [hit for hit in response['hits']['hits'] if hit['_score'] >= score_threshold]


async def get_es_response(query, k=100, score_threshold=20):    
    es = AsyncElasticsearch([ES_HOST])

    try:
        response = await es.search(
            index="fast-sentences",
            query={
                "multi_match": {
                    "query": query,
                    "fields": ["text^2", "document_title", "entities"]
                }
            },
            _source=["text", "document_title", "document_url", "entities", "section"],
            size=k
        )

        filtered_response = filter_score(response, score_threshold=score_threshold)

        return [{
            "url": hit['_source']['document_url'],
            "text": hit['_source']['text'],
            "title": hit['_source']['document_title'],
            "section": hit['_source']['section'],
            "entities": hit['_source']['entities'],
            "score": hit['_score']
        } for hit in filtered_response]
    finally:
        await es.close()


# 동기 버전도 유지 (기존 코드 호환성을 위해)
def get_es_response_sync(query, k=100, score_threshold=20):
    from elasticsearch import Elasticsearch
    es = Elasticsearch([ES_HOST])

    response = es.search(
        index="fast-sentences",
        query={
            "multi_match": {
                "query": query,
                "fields": ["text^2", "document_title", "entities"]
            }
        },
        _source=["text", "document_title", "document_url", "entities", "section"],
        size=k
    )

    filtered_response = filter_score(response, score_threshold=score_threshold)

    return [{
        "url": hit['_source']['document_url'],
        "text": hit['_source']['text'],
        "title": hit['_source']['document_title'],
        "section": hit['_source']['section'],
        "entities": hit['_source']['entities'],
        "score": hit['_score']
    } for hit in filtered_response]


if __name__ == "__main__":
    import asyncio
    
    async def main():
        response = await get_es_response("lung cancer")
        print(response)
    
    asyncio.run(main())
