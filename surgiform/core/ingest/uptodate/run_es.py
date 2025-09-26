import sys
import os
import logging
from elasticsearch import AsyncElasticsearch, NotFoundError, ConnectionError
from dotenv import load_dotenv

load_dotenv()

ES_HOST = os.getenv("ES_HOST")

# 로깅 설정
logger = logging.getLogger(__name__)


def filter_score(response, score_threshold=50):
    return [hit for hit in response['hits']['hits'] if hit['_score'] >= score_threshold]


async def get_es_response(query, k=100, score_threshold=50):    
    """
    Elasticsearch에서 의료 문서 검색
    
    Args:
        query: 검색 쿼리
        k: 반환할 최대 결과 수
        score_threshold: 최소 점수 임계값
        
    Returns:
        list: 검색 결과 리스트 (오류 시 빈 리스트)
    """
    if not ES_HOST:
        logger.warning("ES_HOST 환경변수가 설정되지 않았습니다. 빈 결과를 반환합니다.")
        return []
        
    es = AsyncElasticsearch([ES_HOST])

    try:
        # 인덱스 존재 여부 확인
        index_exists = await es.indices.exists(index="fast-sentences")
        if not index_exists:
            logger.warning("Elasticsearch 인덱스 'fast-sentences'가 존재하지 않습니다. 빈 결과를 반환합니다.")
            return []

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

        results = [{
            "url": hit['_source']['document_url'],
            "text": hit['_source']['text'],
            "title": hit['_source']['document_title'],
            "section": hit['_source']['section'],
            "entities": hit['_source']['entities'],
            "score": hit['_score']
        } for hit in filtered_response]
        
        logger.info(f"Elasticsearch 검색 완료: 쿼리='{query}', 결과 수={len(results)}")
        return results
        
    except NotFoundError:
        logger.warning("Elasticsearch 인덱스 'fast-sentences'가 존재하지 않습니다. 빈 결과를 반환합니다.")
        return []
    except ConnectionError as e:
        logger.error(f"Elasticsearch 연결 오류: {e}. 빈 결과를 반환합니다.")
        return []
    except Exception as e:
        logger.error(f"Elasticsearch 검색 중 오류 발생: {type(e).__name__}: {e}. 빈 결과를 반환합니다.")
        return []
    finally:
        try:
            await es.close()
        except Exception as e:
            logger.debug(f"Elasticsearch 연결 종료 중 오류: {e}")


# 동기 버전도 유지 (기존 코드 호환성을 위해)
def get_es_response_sync(query, k=100, score_threshold=50):
    """
    Elasticsearch에서 의료 문서 검색 (동기 버전)
    """
    from elasticsearch import Elasticsearch
    
    if not ES_HOST:
        logger.warning("ES_HOST 환경변수가 설정되지 않았습니다. 빈 결과를 반환합니다.")
        return []
    
    try:
        es = Elasticsearch([ES_HOST])
        
        # 인덱스 존재 여부 확인
        if not es.indices.exists(index="fast-sentences"):
            logger.warning("Elasticsearch 인덱스 'fast-sentences'가 존재하지 않습니다. 빈 결과를 반환합니다.")
            return []

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

        results = [{
            "url": hit['_source']['document_url'],
            "text": hit['_source']['text'],
            "title": hit['_source']['document_title'],
            "section": hit['_source']['section'],
            "entities": hit['_source']['entities'],
            "score": hit['_score']
        } for hit in filtered_response]
        
        logger.info(f"Elasticsearch 검색 완료: 쿼리='{query}', 결과 수={len(results)}")
        return results
        
    except NotFoundError:
        logger.warning("Elasticsearch 인덱스 'fast-sentences'가 존재하지 않습니다. 빈 결과를 반환합니다.")
        return []
    except ConnectionError as e:
        logger.error(f"Elasticsearch 연결 오류: {e}. 빈 결과를 반환합니다.")
        return []
    except Exception as e:
        logger.error(f"Elasticsearch 검색 중 오류 발생: {type(e).__name__}: {e}. 빈 결과를 반환합니다.")
        return []


if __name__ == "__main__":
    import asyncio
    
    async def main():
        # 테스트 검색
        print("=== Elasticsearch 연결 테스트 ===")
        response = await get_es_response("lung cancer")
        print(f"검색 결과: {len(response)}개")
        
        if response:
            print("첫 번째 결과:")
            print(response[0])
        else:
            print("검색 결과가 없습니다. (인덱스가 비어있거나 연결 오류)")
    
    asyncio.run(main())