# .env 파일에서 환경변수 로드
include .env
export

install:
	poetry install

install-playwright-browser:
	poetry run playwright install chromium

dev:
	poetry run uvicorn surgiform.deploy.server:app \
		--reload \
		--port 8000 \
		--host 0.0.0.0

lint:
	poetry run flake8 . \
	&& poetry run mypy .

test:
	poetry run pytest -q

test-health:
	curl -X GET http://localhost:8000/health


test-chat-session:
	echo '\
{ \
  "system_prompt": "당신은 의료 전문가입니다. 친절하고 정확한 답변을 제공해주세요." \
}' | \
	curl -X POST http://localhost:8000/chat/session \
	     -H "Content-Type: application/json" \
	     -d @-

test-chat:
	echo '\
{ \
  "message": "안녕하세요! 수술에 대해 궁금한 것이 있어요." \
}' | \
	curl -X POST http://localhost:8000/chat \
	     -H "Content-Type: application/json" \
	     -d @-

test-chat-with-session:
	echo '\
{ \
  "message": "수술 후 회복 기간은 얼마나 걸리나요?", \
  "conversation_id": "$(CHAT_ID)" \
}' | \
	curl -X POST http://localhost:8000/chat \
	     -H "Content-Type: application/json" \
	     -d @-

test-chat-history:
	curl -X GET http://localhost:8000/chat/$(CHAT_ID)/history

test-chat-list:
	curl -X GET http://localhost:8000/chat/sessions

test-chat-delete:
	curl -X DELETE http://localhost:8000/chat/$(CHAT_ID)


# 채팅 전체 플로우 테스트
test-chat-flow:
	@echo "=== 1단계: 채팅 세션 생성 ==="
	@echo '{"system_prompt": "당신은 의료 전문가입니다."}' | \
	curl -s -X POST http://localhost:8000/chat/session \
	     -H "Content-Type: application/json" \
	     -d @- | jq '.'
	@echo ""
	@echo "=== 2단계: 첫 번째 메시지 전송 ==="
	@echo '{"message": "안녕하세요!"}' | \
	curl -s -X POST http://localhost:8000/chat \
	     -H "Content-Type: application/json" \
	     -d @- | jq '.'
	@echo ""
	@echo ""
	@echo "=== 3단계: 채팅 세션 목록 조회 ==="
	@curl -s -X GET http://localhost:8000/chat/sessions | jq '.'
	@echo ""
	@echo "✅ 채팅 테스트 완료!"
	@echo "💡 특정 세션으로 테스트하려면: make test-chat-with-session CHAT_ID=your-session-id"


test-consent:
	echo '\
{ \
  "surgery_name": "Cholelithiasis", \
  "registration_no": "123", \
  "patient_name": "김환자", \
  "age": 45, \
  "gender": "M", \
  "scheduled_date": "2025-07-01", \
  "diagnosis": "Cholelithiasis", \
  "surgical_site_mark": "RUQ", \
  "participants": [ \
    { "name": "박현", "is_specialist": true, "department": "GS" } \
  ], \
  "patient_condition": "Stable", \
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
  }, \
  "possum_score": { \
    "mortality_risk": 0.22, \
    "morbidity_risk": 5.47 \
  } \
}' | \
	curl -X POST http://localhost:8000/consent \
	     -H "Content-Type: application/json" \
	     -d @-

test-transform:
	echo '\
{ \
  "consents": { \
    "prognosis_without_surgery": "Cholelithiasis에 대해 수술을 시행하지 않을 경우, 증상이 지속되거나 악화될 수 있으며, 합병증이 발생할 위험이 있습니다. 환자의 현재 상태(Stable)를 고려할 때 적절한 치료가 필요합니다.", \
    "alternative_treatments": "Cholelithiasis 치료를 위한 다른 방법으로는 약물치료, 물리치료, 방사선치료 등이 있으나, 환자의 상태와 진단을 종합적으로 고려했을 때 수술적 치료가 가장 적합한 것으로 판단됩니다.", \
    "surgery_purpose_necessity_effect": "본 수술의 목적은 Cholelithiasis의 근본적 치료를 통해 환자의 증상을 개선하고 삶의 질을 향상시키는 것입니다. 수술은 질병의 진행을 막고 합병증을 예방하기 위해 필요하며, 성공적인 수술 시 좋은 예후를 기대할 수 있습니다.", \
    "surgery_method_content": { \
		"overall_description": "RUQ 부위에 대한 수술을 시행합니다. 수술은 전신마취 하에 진행되며, 최소침습적 방법을 통해 병변을 제거하고 정상 해부학적 구조를 복원할 예정입니다. 수술 시간은 약 2-4시간 소요될 것으로 예상됩니다.", \
		"estimated_duration": "약 2-4시간 소요될 것으로 예상됩니다.", \
		"method_change_or_addition": "수술 방법 변경 및 수술 추가 가능성", \
		"transfusion_possibility": "수혈 가능성", \
		"surgeon_change_possibility": "집도의 변경 가능성" \
	}, \
    "possible_complications_sequelae": "Cholelithiasis 수술과 관련하여 발생 가능한 합병증으로는 출혈, 감염, 마취 관련 합병증, 신경 손상, 혈관 손상 등이 있을 수 있습니다. 또한 수술 부위의 흉터, 일시적 또는 영구적 기능 장애가 발생할 수 있으며, 드물게는 재수술이 필요할 수도 있습니다. 환자의 개별적 상태에 따라 위험도는 달라질 수 있습니다.", \
    "emergency_measures": "수술 중 또는 수술 후 응급상황 발생 시 즉시 응급처치를 시행하고, 필요시 중환자실 입원, 재수술, 전문의 협진 등의 조치를 취하게 됩니다. 24시간 의료진이 대기하여 응급상황에 대비하고 있습니다.", \
    "mortality_risk": "Cholelithiasis 수술과 관련된 사망 위험은 일반적으로 낮으나, 환자의 연령(45세), 전신상태, 동반질환 등을 종합적으로 고려할 때 약 1% 미만의 위험도가 있을 수 있습니다. 마취 관련 사망 위험도 포함되어 있으며, 모든 안전조치를 통해 위험을 최소화하고 있습니다." \
  }, \
  "references": { \
    "prognosis_without_surgery": [], \
    "alternative_treatments": [], \
    "surgery_purpose_necessity_effect": [], \
    "surgery_method_content": { \
		"overall_description": [], \
		"estimated_duration": [], \
		"method_change_or_addition": [], \
		"transfusion_possibility": [], \
		"surgeon_change_possibility": [] \
	}, \
    "possible_complications_sequelae": [], \
    "emergency_measures": [], \
    "mortality_risk": [] \
  }, \
  "mode": "translate_en" \
}' | \
	curl -X POST http://localhost:8000/transform \
	     -H "Content-Type: application/json" \
	     -d @-

uptodate-crawl:
	poetry run python -m surgiform.core.ingest.uptodate.crawler

uptodate-crawl-cron:
	# 매일 새벽 3시에 크롤러 재실행
	0 3 * * * \
		poetry run python -m surgiform.core.ingest.uptodate.crawler \
			>> ~/crawler.log 2>&1

neo4j-up:
	docker run -d --name neo4j \
		-e NEO4J_AUTH=neo4j/${NEO4J_PASSWORD} \
		-e NEO4J_PLUGINS='["apoc"]' \
		-e NEO4J_apoc_export_file_enabled=true \
		-e NEO4J_apoc_import_file_enabled=true \
		-e NEO4J_apoc_import_file_use__neo4j__config=true \
		-p 7687:7687 -p 7474:7474 \
		neo4j:5.26

neo4j-down:
	docker rm -f neo4j

neo4j-reset:
	make neo4j-down
	make neo4j-up

neo4j-logs:
	docker logs -f neo4j

build-rag:
	poetry run python -m surgiform.core.ingest.uptodate.medical_graph_rag \
	    --directory data/uptodate/general-surgery

es-up:
	docker run -d --name es \
		-e "discovery.type=single-node" \
		-e "xpack.security.enabled=false" \
		-p 9200:9200 \
		docker.elastic.co/elasticsearch/elasticsearch:8.13.0

es-down:
	docker rm -f es

es-reset:
	make es-down
	make es-up


build-es:
	poetry run python -m surgiform.core.ingest.uptodate.fast_medical_rag \
		--directory data/uptodate/general-surgery \
		--workers 8 \
		--search

run-es:
	poetry run python -m surgiform.core.ingest.uptodate.run_es


# es-index-up:
# 	curl -X PUT localhost:9200/cost_effect \
# 		-H "Content-Type: application/json" -d @- <<'JSON'
# 		{
# 		"mappings": {
# 			"properties": {
# 			"text": {
# 				"type":            "text",
# 				"term_vector":     "with_positions_offsets"   // 하이라이트용
# 			}
# 			}
# 		}
# 		}
# 		JSON