import sys
import os
from elasticsearch import Elasticsearch
from dotenv import load_dotenv

load_dotenv()

ES_HOST = os.getenv("ES_HOST")


def filter_score(response, score_threshold=20):
    return [hit for hit in response['hits']['hits'] if hit['_score'] >= score_threshold]


def get_es_response(query, k=100, score_threshold=20):    
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
    response = get_es_response("lung cancer")
    print(response)
