install:
	poetry install

dev:
	poetry run uvicorn surgiform.deploy.server:app \
		--reload \
		--port 8000 \
		--host 0.0.0.0

test:
	poetry run pytest -q

lint:
	poetry run flake8 . \
	&& poetry run mypy .

test1:
	curl -X POST http://localhost:8000/consent/transform \
		-H "Content-Type: application/json" \
		-d '{"consent_text":"원본 텍스트","mode":"simplify"}'

	curl -X POST http://localhost:8000/consent \
		-H "Content-Type: application/json" \
		-d @- <<'EOF'
		{
		"registration_no": "123",
		"patient_name": "김환자",
		"age": 45,
		"gender": "M",
		"scheduled_date": "2025-07-01",
		"diagnosis": "Cholelithiasis",
		"surgical_site_mark": "RUQ",
		"participants": [
			{ "is_lead": true, "is_specialist": true, "department": "GS" }
		],
		"patient_condition": "Stable",
		"special_conditions": {}
		}
		EOF
		{"consent_text":"수술동의서(가제) - 환자: 김환자, 진단명: Cholelithiasis, 예정일: 2025-07-01"}%  

test2:
	curl -X POST http://localhost:8000/consent/transform \
		-H "Content-Type: application/json" \
		-d '{"consent_text":"수술 중 출혈 가능성 및 감염 등의 합병증이 발생할 수 있습니다.","mode":"translate_en"}'
