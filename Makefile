# .env 파일에서 환경변수 로드
include .env
export

# bash를 기본 쉘로 설정
SHELL := /bin/bash

# 개발 환경 설정
install:
	poetry install

dev:
	poetry run uvicorn surgiform.main:app \
		--reload \
		--port 8000 \
		--host 0.0.0.0

# 코드 품질 검사
lint:
	poetry run flake8 . \
	&& poetry run mypy .

test:
	poetry run pytest -q

# API 테스트
test-health:
	curl -X GET http://localhost:8000/health

test-chat:
	echo '{ \
	  "message": "안녕하세요! 수술 동의서에 대해 궁금한 것이 있어요." \
	}' | \
	curl -X POST http://localhost:8000/chat \
	     -H "Content-Type: application/json" \
	     -d @-

test-edit-chat:
	echo '{ \
	  "message": "6번 섹션을 영어로 번역해주세요", \
	  "edit_sections": ["6"], \
	  "consents": { \
	    "possible_complications_sequelae": "출혈, 감염, 신경 손상 등의 합병증이 발생할 수 있습니다." \
	  } \
	}' | \
	curl -X POST http://localhost:8000/chat/edit \
	     -H "Content-Type: application/json" \
	     -d @-

test-consent:
	echo '{ \
	  "surgery_name": "복강경 담낭절제술", \
	  "registration_no": "123456", \
	  "patient_name": "김환자", \
	  "age": 45, \
	  "gender": "M", \
	  "scheduled_date": "2025-01-15", \
	  "diagnosis": "담낭결석", \
	  "surgical_site_mark": "RUQ", \
	  "participants": [ \
	    { "name": "박의사", "is_specialist": true, "department": "일반외과" } \
	  ], \
	  "patient_condition": "양호", \
	  "special_conditions": { \
	    "past_history": false, \
	    "diabetes": false, \
	    "smoking": false, \
	    "hypertension": false, \
	    "allergy": false, \
	    "cardiovascular": false, \
	    "respiratory": false, \
	    "coagulation": false, \
	    "medications": false, \
	    "renal": false, \
	    "drug_abuse": false, \
	    "other": null \
	  } \
	}' | \
	curl -X POST http://localhost:8000/consent \
	     -H "Content-Type: application/json" \
	     -d @-

# 배포 관련 (Production)
deploy-ssl:
	sudo certbot certonly --standalone -d api.surgi-form.com

deploy:
	@UVICORN_PATH=$$(poetry run which uvicorn) && \
	sudo $$UVICORN_PATH surgiform.main:app \
	  --host 0.0.0.0 \
	  --port 443 \
	  --ssl-keyfile /etc/letsencrypt/live/api.surgi-form.com/privkey.pem \
	  --ssl-certfile /etc/letsencrypt/live/api.surgi-form.com/fullchain.pem \
	  > >(sudo tee /var/log/surgiform_https.log) 2>&1 &

# 데이터베이스 관리
neo4j-up:
	docker run -d --name neo4j \
		-e NEO4J_AUTH=neo4j/${NEO4J_PASSWORD} \
		-e NEO4J_PLUGINS='["apoc"]' \
		-p 7687:7687 -p 7474:7474 \
		neo4j:5.26

neo4j-down:
	docker rm -f neo4j

neo4j-reset:
	make neo4j-down && make neo4j-up

# Elasticsearch 관리
es-up:
	docker run -d --name es \
		-e "discovery.type=single-node" \
		-e "xpack.security.enabled=false" \
		-p 9200:9200 \
		docker.elastic.co/elasticsearch/elasticsearch:8.13.0

es-down:
	docker rm -f es

es-reset:
	make es-down && make es-up

# RAG 시스템 구축
build-rag:
	poetry run python -m surgiform.core.ingest.uptodate.medical_graph_rag \
	    --directory data/uptodate/general-surgery

build-es:
	poetry run python -m surgiform.core.ingest.uptodate.fast_medical_rag \
		--directory data/uptodate/general-surgery \
		--workers 8 \
		--search