# .env 파일에서 환경변수 로드
include .env
export

# bash를 기본 쉘로 설정
SHELL := /bin/bash

install:
	poetry install

install-playwright-browser:
	poetry run playwright install chromium

dev:
	poetry run uvicorn surgiform.deploy.server:app \
		--reload \
		--port 8000 \
		--host 0.0.0.0

deploy-ssl:
	# sudo apt update
	# sudo apt install certbot -y
	sudo certbot certonly --standalone -d api.surgi-form.com

deploy:
	@UVICORN_PATH=$$(poetry run which uvicorn) && \
	sudo $$UVICORN_PATH surgiform.deploy.server:app \
	  --host 0.0.0.0 \
	  --port 443 \
	  --ssl-keyfile /etc/letsencrypt/live/api.surgi-form.com/privkey.pem \
	  --ssl-certfile /etc/letsencrypt/live/api.surgi-form.com/fullchain.pem \
	  > >(sudo tee /var/log/surgiform_https.log) 2>&1 &

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
  "system_prompt": "당신은 수술 동의서 전문가입니다. 환자가 이해하기 쉽게 설명해주세요." \
}' | \
	curl -X POST http://localhost:8000/chat/session \
	     -H "Content-Type: application/json" \
	     -d @- | jq '.'

test-chat:
	echo '\
{ \
  "message": "안녕하세요! 수술 동의서에 대해 궁금한 것이 있어요." \
}' | \
	curl -X POST http://localhost:8000/chat \
	     -H "Content-Type: application/json" \
	     -d @-

test-chat-with-session:
	echo '\
{ \
  "message": "이 수술의 위험성에 대해 설명해주세요.", \
  "conversation_id": "$(CHAT_ID)" \
}' | \
	curl -X POST http://localhost:8000/chat \
	     -H "Content-Type: application/json" \
	     -d @-

# 동의서 데이터와 함께 질문하기
test-chat-with-consent-question:
	echo '\
{ \
  "message": "이 수술의 합병증에 대해 설명해주세요.", \
  "conversation_id": "$(CHAT_ID)", \
  "consents": { \
    "prognosis_without_surgery": "담낭결석에 대해 수술을 시행하지 않을 경우, 급성 담낭염, 담관염, 췌장염 등의 심각한 합병증이 발생할 수 있습니다.", \
    "alternative_treatments": "담낭결석 치료를 위한 다른 방법으로는 체외충격파쇄석술(ESWL), 경구 담석용해제 복용, 경피적 담낭배액술 등이 있으나, 이러한 방법들은 효과가 제한적이고 재발률이 높아 근본적인 치료법인 수술적 치료가 가장 효과적인 것으로 알려져 있습니다.", \
    "surgery_purpose_necessity_effect": "복강경 담낭절제술의 목적은 담낭결석으로 인한 염증과 통증을 근본적으로 해결하는 것입니다.", \
    "surgery_method_content": { \
      "overall_description": "복강경 담낭절제술은 배에 작은 구멍을 뚫어 카메라와 수술기구를 넣어 담낭을 제거하는 최소침습 수술입니다.", \
      "estimated_duration": "수술 시간은 일반적으로 1-2시간 정도 소요됩니다.", \
      "method_change_or_addition": "수술 중 상황에 따라 개복수술로 전환될 수 있습니다.", \
      "transfusion_possibility": "일반적으로 출혈이 적어 수혈이 필요한 경우는 드뭅니다.", \
      "surgeon_change_possibility": "응급상황 시 다른 숙련된 외과의사가 수술을 대신할 수 있습니다." \
    }, \
    "possible_complications_sequelae": "복강경 담낭절제술의 합병증으로는 출혈, 감염, 마취 관련 합병증, 신경 손상, 혈관 손상 등이 있을 수 있습니다.", \
    "emergency_measures": "수술 중 또는 수술 후 응급상황 발생 시 즉시 응급처치를 시행하게 됩니다.", \
    "mortality_risk": "복강경 담낭절제술은 안전하지만 매우 드물게 사망 위험이 있을 수 있습니다." \
  }, \
  "references": { \
    "prognosis_without_surgery": ["Acute cholecystitis complications"], \
    "alternative_treatments": ["Non-surgical treatment options"], \
    "surgery_purpose_necessity_effect": ["Laparoscopic cholecystectomy indications"], \
    "surgery_method_content": { \
      "overall_description": ["Laparoscopic cholecystectomy technique"], \
      "estimated_duration": ["Operative time factors"], \
      "method_change_or_addition": ["Conversion to open surgery"], \
      "transfusion_possibility": ["Blood transfusion guidelines"], \
      "surgeon_change_possibility": ["Surgical team management"] \
    }, \
    "possible_complications_sequelae": ["Surgical complications"], \
    "emergency_measures": ["Emergency procedures"], \
    "mortality_risk": ["Mortality statistics"] \
  } \
}' | curl -s -X POST http://localhost:8000/chat -H "Content-Type: application/json" -d @- | jq '.message, .is_content_modified'

# 쉬운 말로 변경 요청 
test-chat-simplify:
	echo '\
{ \
  "message": "이 동의서를 더 쉬운 말로 바꿔주세요.", \
  "conversation_id": "$(CHAT_ID)", \
  "consents": { \
    "prognosis_without_surgery": "담낭결석에 대해 수술을 시행하지 않을 경우, 급성 담낭염, 담관염, 췌장염 등의 심각한 합병증이 발생할 수 있으며, 지속적인 복통과 소화불량으로 일상생활에 큰 지장을 받을 수 있습니다. 또한 시간이 지날수록 담낭벽이 두꺼워지고 유착이 심해져 수술이 더욱 어려워질 수 있습니다.", \
    "alternative_treatments": "담낭결석 치료를 위한 다른 방법으로는 체외충격파쇄석술(ESWL), 경구 담석용해제 복용, 경피적 담낭배액술 등이 있으나, 이러한 방법들은 효과가 제한적이고 재발률이 높아 근본적인 치료법인 수술적 치료가 가장 효과적인 것으로 알려져 있습니다.", \
    "surgery_purpose_necessity_effect": "복강경 담낭절제술의 목적은 담낭결석으로 인한 염증과 통증을 근본적으로 해결하고, 급성 담낭염, 담관염, 췌장염 등의 심각한 합병증을 예방하는 것입니다. 수술을 통해 환자의 삶의 질을 크게 개선하고 정상적인 일상생활로의 복귀를 가능하게 합니다.", \
    "surgery_method_content": { \
      "overall_description": "복강경 담낭절제술은 배에 3-4개의 작은 구멍(5-12mm)을 뚫어 카메라(복강경)와 수술기구를 넣어 담낭을 제거하는 최소침습 수술입니다. 전신마취 하에 이산화탄소 가스를 넣어 복강을 부풀린 후, 담낭동맥과 담낭관을 찾아 안전하게 절단하고 담낭을 완전히 제거합니다.", \
      "estimated_duration": "수술 시간은 환자의 상태와 수술의 복잡성에 따라 다르지만, 일반적으로 1-2시간 정도 소요되며, 수술 전 준비시간과 마취 시간을 포함하면 총 3-4시간 정도 소요될 예정입니다.", \
      "method_change_or_addition": "수술 중 심한 염증, 유착, 출혈, 해부학적 이상 등으로 인해 복강경 수술이 어려울 경우 환자의 안전을 위해 개복수술로 전환할 수 있습니다. 또한 담관손상이나 기타 합병증 발생 시 추가적인 수술 절차가 필요할 수 있습니다.", \
      "transfusion_possibility": "일반적으로 복강경 담낭절제술은 출혈이 적은 수술이므로 수혈이 필요한 경우는 드물지만, 예상치 못한 대량출혈이나 환자의 빈혈 상태에 따라 수혈이 필요할 수 있으며, 이 경우 적절한 혈액제제를 사용하게 됩니다.", \
      "surgeon_change_possibility": "수술 중 응급상황 발생, 주치의의 컨디션 난조, 또는 기타 불가피한 사유로 인해 다른 숙련된 외과의사가 수술을 대신 진행할 수 있으며, 이 경우 수술의 연속성과 안전성을 보장하기 위해 충분한 인수인계가 이루어집니다." \
    }, \
    "possible_complications_sequelae": "복강경 담낭절제술과 관련하여 발생 가능한 합병증으로는 출혈, 감염, 담관손상, 장기손상, 마취 관련 합병증 등이 있습니다. 또한 수술 후 창상 감염, 복강 내 농양 형성, 담즙 누출, 일시적 소화불량 등이 발생할 수 있으며, 드물게는 재수술이 필요한 경우도 있습니다. 대부분의 합병증은 적절한 치료를 통해 회복 가능합니다.", \
    "emergency_measures": "수술 중 또는 수술 후 응급상황(대량출혈, 장기손상, 담즙누출, 감염 등) 발생 시 즉시 응급처치를 시행하고, 필요에 따라 중환자실 입원, 재수술, 인터벤션 시술, 항생제 치료, 수혈 등의 조치를 취하게 됩니다. 24시간 의료진이 대기하여 모든 응급상황에 신속하게 대응할 수 있는 체계를 갖추고 있습니다.", \
    "mortality_risk": "복강경 담낭절제술은 안전한 수술로 알려져 있으나, 모든 수술과 마찬가지로 매우 드물게 사망의 위험이 있을 수 있습니다. 사망 위험도는 환자의 나이, 전신상태, 동반질환, 수술의 복잡성 등을 종합적으로 고려할 때 1% 미만으로 예상되며, 마취 관련 위험도 포함되어 있습니다. 모든 안전조치를 통해 위험을 최소화하고 있습니다." \
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
  } \
}' | \
	curl -X POST http://localhost:8000/chat \
	     -H "Content-Type: application/json" \
	     -d @-

# 요약 요청
test-chat-summary:
	echo '\
{ \
  "message": "이 동의서 내용을 5줄로 요약해주세요.", \
  "conversation_id": "$(CHAT_ID)", \
  "consents": { \
    "prognosis_without_surgery": "담낭결석에 대해 수술을 시행하지 않을 경우, 급성 담낭염, 담관염, 췌장염 등의 심각한 합병증이 발생할 수 있으며, 지속적인 복통과 소화불량으로 일상생활에 큰 지장을 받을 수 있습니다. 또한 시간이 지날수록 담낭벽이 두꺼워지고 유착이 심해져 수술이 더욱 어려워질 수 있습니다.", \
    "alternative_treatments": "담낭결석 치료를 위한 다른 방법으로는 체외충격파쇄석술(ESWL), 경구 담석용해제 복용, 경피적 담낭배액술 등이 있으나, 이러한 방법들은 효과가 제한적이고 재발률이 높아 근본적인 치료법인 수술적 치료가 가장 효과적인 것으로 알려져 있습니다.", \
    "surgery_purpose_necessity_effect": "복강경 담낭절제술의 목적은 담낭결석으로 인한 염증과 통증을 근본적으로 해결하고, 급성 담낭염, 담관염, 췌장염 등의 심각한 합병증을 예방하는 것입니다. 수술을 통해 환자의 삶의 질을 크게 개선하고 정상적인 일상생활로의 복귀를 가능하게 합니다.", \
    "surgery_method_content": { \
      "overall_description": "복강경 담낭절제술은 배에 3-4개의 작은 구멍(5-12mm)을 뚫어 카메라(복강경)와 수술기구를 넣어 담낭을 제거하는 최소침습 수술입니다. 전신마취 하에 이산화탄소 가스를 넣어 복강을 부풀린 후, 담낭동맥과 담낭관을 찾아 안전하게 절단하고 담낭을 완전히 제거합니다.", \
      "estimated_duration": "수술 시간은 환자의 상태와 수술의 복잡성에 따라 다르지만, 일반적으로 1-2시간 정도 소요되며, 수술 전 준비시간과 마취 시간을 포함하면 총 3-4시간 정도 소요될 예정입니다.", \
      "method_change_or_addition": "수술 중 심한 염증, 유착, 출혈, 해부학적 이상 등으로 인해 복강경 수술이 어려울 경우 환자의 안전을 위해 개복수술로 전환할 수 있습니다. 또한 담관손상이나 기타 합병증 발생 시 추가적인 수술 절차가 필요할 수 있습니다.", \
      "transfusion_possibility": "일반적으로 복강경 담낭절제술은 출혈이 적은 수술이므로 수혈이 필요한 경우는 드물지만, 예상치 못한 대량출혈이나 환자의 빈혈 상태에 따라 수혈이 필요할 수 있으며, 이 경우 적절한 혈액제제를 사용하게 됩니다.", \
      "surgeon_change_possibility": "수술 중 응급상황 발생, 주치의의 컨디션 난조, 또는 기타 불가피한 사유로 인해 다른 숙련된 외과의사가 수술을 대신 진행할 수 있으며, 이 경우 수술의 연속성과 안전성을 보장하기 위해 충분한 인수인계가 이루어집니다." \
    }, \
    "possible_complications_sequelae": "복강경 담낭절제술과 관련하여 발생 가능한 합병증으로는 출혈, 감염, 담관손상, 장기손상, 마취 관련 합병증 등이 있습니다. 또한 수술 후 창상 감염, 복강 내 농양 형성, 담즙 누출, 일시적 소화불량 등이 발생할 수 있으며, 드물게는 재수술이 필요한 경우도 있습니다. 대부분의 합병증은 적절한 치료를 통해 회복 가능합니다.", \
    "emergency_measures": "수술 중 또는 수술 후 응급상황(대량출혈, 장기손상, 담즙누출, 감염 등) 발생 시 즉시 응급처치를 시행하고, 필요에 따라 중환자실 입원, 재수술, 인터벤션 시술, 항생제 치료, 수혈 등의 조치를 취하게 됩니다. 24시간 의료진이 대기하여 모든 응급상황에 신속하게 대응할 수 있는 체계를 갖추고 있습니다.", \
    "mortality_risk": "복강경 담낭절제술은 안전한 수술로 알려져 있으나, 모든 수술과 마찬가지로 매우 드물게 사망의 위험이 있을 수 있습니다. 사망 위험도는 환자의 나이, 전신상태, 동반질환, 수술의 복잡성 등을 종합적으로 고려할 때 1% 미만으로 예상되며, 마취 관련 위험도 포함되어 있습니다. 모든 안전조치를 통해 위험을 최소화하고 있습니다." \
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
  } \
}' | \
	curl -X POST http://localhost:8000/chat \
	     -H "Content-Type: application/json" \
	     -d @-

# 영어 번역 요청
test-chat-translate:
	echo '\
{ \
  "message": "이 동의서를 영어로 번역해주세요.", \
  "conversation_id": "$(CHAT_ID)", \
  "consents": { \
    "prognosis_without_surgery": "담낭결석에 대해 수술을 시행하지 않을 경우, 급성 담낭염, 담관염, 췌장염 등의 심각한 합병증이 발생할 수 있으며, 지속적인 복통과 소화불량으로 일상생활에 큰 지장을 받을 수 있습니다. 또한 시간이 지날수록 담낭벽이 두꺼워지고 유착이 심해져 수술이 더욱 어려워질 수 있습니다.", \
    "alternative_treatments": "담낭결석 치료를 위한 다른 방법으로는 체외충격파쇄석술(ESWL), 경구 담석용해제 복용, 경피적 담낭배액술 등이 있으나, 이러한 방법들은 효과가 제한적이고 재발률이 높아 근본적인 치료법인 수술적 치료가 가장 효과적인 것으로 알려져 있습니다.", \
    "surgery_purpose_necessity_effect": "복강경 담낭절제술의 목적은 담낭결석으로 인한 염증과 통증을 근본적으로 해결하고, 급성 담낭염, 담관염, 췌장염 등의 심각한 합병증을 예방하는 것입니다. 수술을 통해 환자의 삶의 질을 크게 개선하고 정상적인 일상생활로의 복귀를 가능하게 합니다.", \
    "surgery_method_content": { \
      "overall_description": "복강경 담낭절제술은 배에 3-4개의 작은 구멍(5-12mm)을 뚫어 카메라(복강경)와 수술기구를 넣어 담낭을 제거하는 최소침습 수술입니다. 전신마취 하에 이산화탄소 가스를 넣어 복강을 부풀린 후, 담낭동맥과 담낭관을 찾아 안전하게 절단하고 담낭을 완전히 제거합니다.", \
      "estimated_duration": "수술 시간은 환자의 상태와 수술의 복잡성에 따라 다르지만, 일반적으로 1-2시간 정도 소요되며, 수술 전 준비시간과 마취 시간을 포함하면 총 3-4시간 정도 소요될 예정입니다.", \
      "method_change_or_addition": "수술 중 심한 염증, 유착, 출혈, 해부학적 이상 등으로 인해 복강경 수술이 어려울 경우 환자의 안전을 위해 개복수술로 전환할 수 있습니다. 또한 담관손상이나 기타 합병증 발생 시 추가적인 수술 절차가 필요할 수 있습니다.", \
      "transfusion_possibility": "일반적으로 복강경 담낭절제술은 출혈이 적은 수술이므로 수혈이 필요한 경우는 드물지만, 예상치 못한 대량출혈이나 환자의 빈혈 상태에 따라 수혈이 필요할 수 있으며, 이 경우 적절한 혈액제제를 사용하게 됩니다.", \
      "surgeon_change_possibility": "수술 중 응급상황 발생, 주치의의 컨디션 난조, 또는 기타 불가피한 사유로 인해 다른 숙련된 외과의사가 수술을 대신 진행할 수 있으며, 이 경우 수술의 연속성과 안전성을 보장하기 위해 충분한 인수인계가 이루어집니다." \
    }, \
    "possible_complications_sequelae": "복강경 담낭절제술과 관련하여 발생 가능한 합병증으로는 출혈, 감염, 담관손상, 장기손상, 마취 관련 합병증 등이 있습니다. 또한 수술 후 창상 감염, 복강 내 농양 형성, 담즙 누출, 일시적 소화불량 등이 발생할 수 있으며, 드물게는 재수술이 필요한 경우도 있습니다. 대부분의 합병증은 적절한 치료를 통해 회복 가능합니다.", \
    "emergency_measures": "수술 중 또는 수술 후 응급상황(대량출혈, 장기손상, 담즙누출, 감염 등) 발생 시 즉시 응급처치를 시행하고, 필요에 따라 중환자실 입원, 재수술, 인터벤션 시술, 항생제 치료, 수혈 등의 조치를 취하게 됩니다. 24시간 의료진이 대기하여 모든 응급상황에 신속하게 대응할 수 있는 체계를 갖추고 있습니다.", \
    "mortality_risk": "복강경 담낭절제술은 안전한 수술로 알려져 있으나, 모든 수술과 마찬가지로 매우 드물게 사망의 위험이 있을 수 있습니다. 사망 위험도는 환자의 나이, 전신상태, 동반질환, 수술의 복잡성 등을 종합적으로 고려할 때 1% 미만으로 예상되며, 마취 관련 위험도 포함되어 있습니다. 모든 안전조치를 통해 위험을 최소화하고 있습니다." \
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

test-chat-history:
	curl -X GET http://localhost:8000/chat/$(CHAT_ID)/history

test-chat-list:
	curl -X GET http://localhost:8000/chat/sessions

test-chat-delete:
	curl -X DELETE http://localhost:8000/chat/$(CHAT_ID)


# 통합 채팅 전체 플로우 테스트
test-chat-flow:
	@echo "=== 🏥 수술 동의서 통합 채팅 시스템 테스트 ==="
	@echo ""
	@echo "=== 1단계: 일반 질문 (동의서 데이터 없음) ==="
	@echo '{"message": "복강경 수술에 대해 설명해주세요.", "system_prompt": "당신은 수술 동의서 전문가입니다. 환자가 이해하기 쉽게 설명해주세요."}' | \
	curl -s -X POST http://localhost:8000/chat \
	     -H "Content-Type: application/json" \
	     -d @- | jq '.message, .is_content_modified'
	@echo ""
	@echo "=== 2단계: 동의서 데이터와 함께 질문 ==="
	@echo '{ \
	  "message": "이 수술의 합병증에 대해 설명해주세요.", \
	  "consents": { \
	    "prognosis_without_surgery": "담낭결석에 대해 수술을 시행하지 않을 경우, 급성 담낭염, 담관염, 췌장염 등의 심각한 합병증이 발생할 수 있으며, 지속적인 복통과 소화불량으로 일상생활에 큰 지장을 받을 수 있습니다. 또한 시간이 지날수록 담낭벽이 두꺼워지고 유착이 심해져 수술이 더욱 어려워질 수 있습니다.", \
	    "alternative_treatments": "담낭결석 치료를 위한 다른 방법으로는 체외충격파쇄석술(ESWL), 경구 담석용해제 복용, 경피적 담낭배액술 등이 있으나, 이러한 방법들은 효과가 제한적이고 재발률이 높아 근본적인 치료법인 수술적 치료가 가장 효과적인 것으로 알려져 있습니다.", \
	    "surgery_purpose_necessity_effect": "복강경 담낭절제술의 목적은 담낭결석으로 인한 염증과 통증을 근본적으로 해결하고, 급성 담낭염, 담관염, 췌장염 등의 심각한 합병증을 예방하는 것입니다. 수술을 통해 환자의 삶의 질을 크게 개선하고 정상적인 일상생활로의 복귀를 가능하게 합니다.", \
	    "surgery_method_content": { \
	      "overall_description": "복강경 담낭절제술은 배에 3-4개의 작은 구멍(5-12mm)을 뚫어 카메라(복강경)와 수술기구를 넣어 담낭을 제거하는 최소침습 수술입니다. 전신마취 하에 이산화탄소 가스를 넣어 복강을 부풀린 후, 담낭동맥과 담낭관을 찾아 안전하게 절단하고 담낭을 완전히 제거합니다.", \
	      "estimated_duration": "수술 시간은 환자의 상태와 수술의 복잡성에 따라 다르지만, 일반적으로 1-2시간 정도 소요되며, 수술 전 준비시간과 마취 시간을 포함하면 총 3-4시간 정도 소요될 예정입니다.", \
	      "method_change_or_addition": "수술 중 심한 염증, 유착, 출혈, 해부학적 이상 등으로 인해 복강경 수술이 어려울 경우 환자의 안전을 위해 개복수술로 전환할 수 있습니다. 또한 담관손상이나 기타 합병증 발생 시 추가적인 수술 절차가 필요할 수 있습니다.", \
	      "transfusion_possibility": "일반적으로 복강경 담낭절제술은 출혈이 적은 수술이므로 수혈이 필요한 경우는 드물지만, 예상치 못한 대량출혈이나 환자의 빈혈 상태에 따라 수혈이 필요할 수 있으며, 이 경우 적절한 혈액제제를 사용하게 됩니다.", \
	      "surgeon_change_possibility": "수술 중 응급상황 발생, 주치의의 컨디션 난조, 또는 기타 불가피한 사유로 인해 다른 숙련된 외과의사가 수술을 대신 진행할 수 있으며, 이 경우 수술의 연속성과 안전성을 보장하기 위해 충분한 인수인계가 이루어집니다." \
	    }, \
	    "possible_complications_sequelae": "복강경 담낭절제술과 관련하여 발생 가능한 합병증으로는 출혈, 감염, 담관손상, 장기손상, 마취 관련 합병증 등이 있습니다. 또한 수술 후 창상 감염, 복강 내 농양 형성, 담즙 누출, 일시적 소화불량 등이 발생할 수 있으며, 드물게는 재수술이 필요한 경우도 있습니다. 대부분의 합병증은 적절한 치료를 통해 회복 가능합니다.", \
	    "emergency_measures": "수술 중 또는 수술 후 응급상황(대량출혈, 장기손상, 담즙누출, 감염 등) 발생 시 즉시 응급처치를 시행하고, 필요에 따라 중환자실 입원, 재수술, 인터벤션 시술, 항생제 치료, 수혈 등의 조치를 취하게 됩니다. 24시간 의료진이 대기하여 모든 응급상황에 신속하게 대응할 수 있는 체계를 갖추고 있습니다.", \
	    "mortality_risk": "복강경 담낭절제술은 안전한 수술로 알려져 있으나, 모든 수술과 마찬가지로 매우 드물게 사망의 위험이 있을 수 있습니다. 사망 위험도는 환자의 나이, 전신상태, 동반질환, 수술의 복잡성 등을 종합적으로 고려할 때 1% 미만으로 예상되며, 마취 관련 위험도 포함되어 있습니다. 모든 안전조치를 통해 위험을 최소화하고 있습니다." \
	  }, \
	  "references": { \
	    "prognosis_without_surgery": [{"title": "Acute cholecystitis complications", "url": "https://www.uptodate.com/contents/acute-cholecystitis", "text": "Acute cholecystitis complications"}], \
	    "alternative_treatments": [{"title": "Non-surgical treatment options", "url": "https://www.cochranelibrary.com/gallstones", "text": "Non-surgical treatment options"}], \
	    "surgery_purpose_necessity_effect": [{"title": "Laparoscopic cholecystectomy indications", "url": "https://www.sages.org/cholecystectomy-guidelines", "text": "Laparoscopic cholecystectomy indications"}], \
	    "surgery_method_content": { \
	      "overall_description": [{"title": "Laparoscopic cholecystectomy technique", "url": "https://www.uptodate.com/contents/laparoscopic-cholecystectomy", "text": "Laparoscopic cholecystectomy technique"}], \
	      "estimated_duration": [{"title": "Operative time factors", "url": "https://www.annalsofsurgery.com/operative-time", "text": "Operative time factors"}], \
	      "method_change_or_addition": [{"title": "Conversion to open surgery", "url": "https://www.worldjournalofsurgery.com/conversion", "text": "Conversion to open surgery"}], \
	      "transfusion_possibility": [{"title": "Blood transfusion guidelines", "url": "https://www.transfusion-medicine.com/elective-surgery", "text": "Blood transfusion guidelines"}], \
	      "surgeon_change_possibility": [{"title": "Surgical team management", "url": "https://www.patient-safety.org/team-management", "text": "Surgical team management"}] \
	    }, \
	    "possible_complications_sequelae": [{"title": "Surgical complications", "url": "https://www.surgical-endoscopy.com/complications", "text": "Surgical complications"}], \
	    "emergency_measures": [{"title": "Emergency procedures", "url": "https://www.emergency-surgery.org/protocols", "text": "Emergency procedures"}], \
	    "mortality_risk": [{"title": "Mortality statistics", "url": "https://www.meta-analysis.com/mortality", "text": "Mortality statistics"}] \
	  } \
	}' | curl -s -X POST http://localhost:8000/chat \
	     -H "Content-Type: application/json" \
	     -d @- | jq '.message, .is_content_modified'
	@echo ""
	@echo "=== 3단계: 쉬운 말로 변경 요청 ==="
	@echo '{ \
	  "message": "더 쉬운 말로 바꿔주세요.", \
	  "consents": { \
	    "prognosis_without_surgery": "담낭결석에 대해 수술을 시행하지 않을 경우, 급성 담낭염, 담관염, 췌장염 등의 심각한 합병증이 발생할 수 있으며, 지속적인 복통과 소화불량으로 일상생활에 큰 지장을 받을 수 있습니다. 또한 시간이 지날수록 담낭벽이 두꺼워지고 유착이 심해져 수술이 더욱 어려워질 수 있습니다.", \
	    "alternative_treatments": "담낭결석 치료를 위한 다른 방법으로는 체외충격파쇄석술(ESWL), 경구 담석용해제 복용, 경피적 담낭배액술 등이 있으나, 이러한 방법들은 효과가 제한적이고 재발률이 높아 근본적인 치료법인 수술적 치료가 가장 효과적인 것으로 알려져 있습니다.", \
	    "surgery_purpose_necessity_effect": "복강경 담낭절제술의 목적은 담낭결석으로 인한 염증과 통증을 근본적으로 해결하고, 급성 담낭염, 담관염, 췌장염 등의 심각한 합병증을 예방하는 것입니다. 수술을 통해 환자의 삶의 질을 크게 개선하고 정상적인 일상생활로의 복귀를 가능하게 합니다.", \
	    "surgery_method_content": { \
	      "overall_description": "복강경 담낭절제술은 배에 3-4개의 작은 구멍(5-12mm)을 뚫어 카메라(복강경)와 수술기구를 넣어 담낭을 제거하는 최소침습 수술입니다. 전신마취 하에 이산화탄소 가스를 넣어 복강을 부풀린 후, 담낭동맥과 담낭관을 찾아 안전하게 절단하고 담낭을 완전히 제거합니다.", \
	      "estimated_duration": "수술 시간은 환자의 상태와 수술의 복잡성에 따라 다르지만, 일반적으로 1-2시간 정도 소요되며, 수술 전 준비시간과 마취 시간을 포함하면 총 3-4시간 정도 소요될 예정입니다.", \
	      "method_change_or_addition": "수술 중 심한 염증, 유착, 출혈, 해부학적 이상 등으로 인해 복강경 수술이 어려울 경우 환자의 안전을 위해 개복수술로 전환할 수 있습니다. 또한 담관손상이나 기타 합병증 발생 시 추가적인 수술 절차가 필요할 수 있습니다.", \
	      "transfusion_possibility": "일반적으로 복강경 담낭절제술은 출혈이 적은 수술이므로 수혈이 필요한 경우는 드물지만, 예상치 못한 대량출혈이나 환자의 빈혈 상태에 따라 수혈이 필요할 수 있으며, 이 경우 적절한 혈액제제를 사용하게 됩니다.", \
	      "surgeon_change_possibility": "수술 중 응급상황 발생, 주치의의 컨디션 난조, 또는 기타 불가피한 사유로 인해 다른 숙련된 외과의사가 수술을 대신 진행할 수 있으며, 이 경우 수술의 연속성과 안전성을 보장하기 위해 충분한 인수인계가 이루어집니다." \
	    }, \
	    "possible_complications_sequelae": "복강경 담낭절제술과 관련하여 발생 가능한 합병증으로는 출혈, 감염, 담관손상, 장기손상, 마취 관련 합병증 등이 있습니다. 또한 수술 후 창상 감염, 복강 내 농양 형성, 담즙 누출, 일시적 소화불량 등이 발생할 수 있으며, 드물게는 재수술이 필요한 경우도 있습니다. 대부분의 합병증은 적절한 치료를 통해 회복 가능합니다.", \
	    "emergency_measures": "수술 중 또는 수술 후 응급상황(대량출혈, 장기손상, 담즙누출, 감염 등) 발생 시 즉시 응급처치를 시행하고, 필요에 따라 중환자실 입원, 재수술, 인터벤션 시술, 항생제 치료, 수혈 등의 조치를 취하게 됩니다. 24시간 의료진이 대기하여 모든 응급상황에 신속하게 대응할 수 있는 체계를 갖추고 있습니다.", \
	    "mortality_risk": "복강경 담낭절제술은 안전한 수술로 알려져 있으나, 모든 수술과 마찬가지로 매우 드물게 사망의 위험이 있을 수 있습니다. 사망 위험도는 환자의 나이, 전신상태, 동반질환, 수술의 복잡성 등을 종합적으로 고려할 때 1% 미만으로 예상되며, 마취 관련 위험도 포함되어 있습니다. 모든 안전조치를 통해 위험을 최소화하고 있습니다." \
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
	  } \
	}' | \
	curl -X POST http://localhost:8000/chat \
	     -H "Content-Type: application/json" \
	     -d @-

# 요약 요청
test-chat-summary:
	echo '\
{ \
  "message": "이 동의서 내용을 5줄로 요약해주세요.", \
  "conversation_id": "$(CHAT_ID)", \
  "consents": { \
    "prognosis_without_surgery": "담낭결석에 대해 수술을 시행하지 않을 경우, 급성 담낭염, 담관염, 췌장염 등의 심각한 합병증이 발생할 수 있으며, 지속적인 복통과 소화불량으로 일상생활에 큰 지장을 받을 수 있습니다. 또한 시간이 지날수록 담낭벽이 두꺼워지고 유착이 심해져 수술이 더욱 어려워질 수 있습니다.", \
    "alternative_treatments": "담낭결석 치료를 위한 다른 방법으로는 체외충격파쇄석술(ESWL), 경구 담석용해제 복용, 경피적 담낭배액술 등이 있으나, 이러한 방법들은 효과가 제한적이고 재발률이 높아 근본적인 치료법인 수술적 치료가 가장 효과적인 것으로 알려져 있습니다.", \
    "surgery_purpose_necessity_effect": "복강경 담낭절제술의 목적은 담낭결석으로 인한 염증과 통증을 근본적으로 해결하고, 급성 담낭염, 담관염, 췌장염 등의 심각한 합병증을 예방하는 것입니다. 수술을 통해 환자의 삶의 질을 크게 개선하고 정상적인 일상생활로의 복귀를 가능하게 합니다.", \
    "surgery_method_content": { \
      "overall_description": "복강경 담낭절제술은 배에 3-4개의 작은 구멍(5-12mm)을 뚫어 카메라(복강경)와 수술기구를 넣어 담낭을 제거하는 최소침습 수술입니다. 전신마취 하에 이산화탄소 가스를 넣어 복강을 부풀린 후, 담낭동맥과 담낭관을 찾아 안전하게 절단하고 담낭을 완전히 제거합니다.", \
      "estimated_duration": "수술 시간은 환자의 상태와 수술의 복잡성에 따라 다르지만, 일반적으로 1-2시간 정도 소요되며, 수술 전 준비시간과 마취 시간을 포함하면 총 3-4시간 정도 소요될 예정입니다.", \
      "method_change_or_addition": "수술 중 심한 염증, 유착, 출혈, 해부학적 이상 등으로 인해 복강경 수술이 어려울 경우 환자의 안전을 위해 개복수술로 전환할 수 있습니다. 또한 담관손상이나 기타 합병증 발생 시 추가적인 수술 절차가 필요할 수 있습니다.", \
      "transfusion_possibility": "일반적으로 복강경 담낭절제술은 출혈이 적은 수술이므로 수혈이 필요한 경우는 드물지만, 예상치 못한 대량출혈이나 환자의 빈혈 상태에 따라 수혈이 필요할 수 있으며, 이 경우 적절한 혈액제제를 사용하게 됩니다.", \
      "surgeon_change_possibility": "수술 중 응급상황 발생, 주치의의 컨디션 난조, 또는 기타 불가피한 사유로 인해 다른 숙련된 외과의사가 수술을 대신 진행할 수 있으며, 이 경우 수술의 연속성과 안전성을 보장하기 위해 충분한 인수인계가 이루어집니다." \
    }, \
    "possible_complications_sequelae": "복강경 담낭절제술과 관련하여 발생 가능한 합병증으로는 출혈, 감염, 담관손상, 장기손상, 마취 관련 합병증 등이 있습니다. 또한 수술 후 창상 감염, 복강 내 농양 형성, 담즙 누출, 일시적 소화불량 등이 발생할 수 있으며, 드물게는 재수술이 필요한 경우도 있습니다. 대부분의 합병증은 적절한 치료를 통해 회복 가능합니다.", \
    "emergency_measures": "수술 중 또는 수술 후 응급상황(대량출혈, 장기손상, 담즙누출, 감염 등) 발생 시 즉시 응급처치를 시행하고, 필요에 따라 중환자실 입원, 재수술, 인터벤션 시술, 항생제 치료, 수혈 등의 조치를 취하게 됩니다. 24시간 의료진이 대기하여 모든 응급상황에 신속하게 대응할 수 있는 체계를 갖추고 있습니다.", \
    "mortality_risk": "복강경 담낭절제술은 안전한 수술로 알려져 있으나, 모든 수술과 마찬가지로 매우 드물게 사망의 위험이 있을 수 있습니다. 사망 위험도는 환자의 나이, 전신상태, 동반질환, 수술의 복잡성 등을 종합적으로 고려할 때 1% 미만으로 예상되며, 마취 관련 위험도 포함되어 있습니다. 모든 안전조치를 통해 위험을 최소화하고 있습니다." \
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
  } \
}' | \
	curl -X POST http://localhost:8000/chat \
	     -H "Content-Type: application/json" \
	     -d @-

# 영어 번역 요청
test-chat-translate:
	echo '\
{ \
  "message": "이 동의서를 영어로 번역해주세요.", \
  "conversation_id": "$(CHAT_ID)", \
  "consents": { \
    "prognosis_without_surgery": "담낭결석에 대해 수술을 시행하지 않을 경우, 급성 담낭염, 담관염, 췌장염 등의 심각한 합병증이 발생할 수 있으며, 지속적인 복통과 소화불량으로 일상생활에 큰 지장을 받을 수 있습니다. 또한 시간이 지날수록 담낭벽이 두꺼워지고 유착이 심해져 수술이 더욱 어려워질 수 있습니다.", \
    "alternative_treatments": "담낭결석 치료를 위한 다른 방법으로는 체외충격파쇄석술(ESWL), 경구 담석용해제 복용, 경피적 담낭배액술 등이 있으나, 이러한 방법들은 효과가 제한적이고 재발률이 높아 근본적인 치료법인 수술적 치료가 가장 효과적인 것으로 알려져 있습니다.", \
    "surgery_purpose_necessity_effect": "복강경 담낭절제술의 목적은 담낭결석으로 인한 염증과 통증을 근본적으로 해결하고, 급성 담낭염, 담관염, 췌장염 등의 심각한 합병증을 예방하는 것입니다. 수술을 통해 환자의 삶의 질을 크게 개선하고 정상적인 일상생활로의 복귀를 가능하게 합니다.", \
    "surgery_method_content": { \
      "overall_description": "복강경 담낭절제술은 배에 3-4개의 작은 구멍(5-12mm)을 뚫어 카메라(복강경)와 수술기구를 넣어 담낭을 제거하는 최소침습 수술입니다. 전신마취 하에 이산화탄소 가스를 넣어 복강을 부풀린 후, 담낭동맥과 담낭관을 찾아 안전하게 절단하고 담낭을 완전히 제거합니다.", \
      "estimated_duration": "수술 시간은 환자의 상태와 수술의 복잡성에 따라 다르지만, 일반적으로 1-2시간 정도 소요되며, 수술 전 준비시간과 마취 시간을 포함하면 총 3-4시간 정도 소요될 예정입니다.", \
      "method_change_or_addition": "수술 중 심한 염증, 유착, 출혈, 해부학적 이상 등으로 인해 복강경 수술이 어려울 경우 환자의 안전을 위해 개복수술로 전환할 수 있습니다. 또한 담관손상이나 기타 합병증 발생 시 추가적인 수술 절차가 필요할 수 있습니다.", \
      "transfusion_possibility": "일반적으로 복강경 담낭절제술은 출혈이 적은 수술이므로 수혈이 필요한 경우는 드물지만, 예상치 못한 대량출혈이나 환자의 빈혈 상태에 따라 수혈이 필요할 수 있으며, 이 경우 적절한 혈액제제를 사용하게 됩니다.", \
      "surgeon_change_possibility": "수술 중 응급상황 발생, 주치의의 컨디션 난조, 또는 기타 불가피한 사유로 인해 다른 숙련된 외과의사가 수술을 대신 진행할 수 있으며, 이 경우 수술의 연속성과 안전성을 보장하기 위해 충분한 인수인계가 이루어집니다." \
    }, \
    "possible_complications_sequelae": "복강경 담낭절제술과 관련하여 발생 가능한 합병증으로는 출혈, 감염, 담관손상, 장기손상, 마취 관련 합병증 등이 있습니다. 또한 수술 후 창상 감염, 복강 내 농양 형성, 담즙 누출, 일시적 소화불량 등이 발생할 수 있으며, 드물게는 재수술이 필요한 경우도 있습니다. 대부분의 합병증은 적절한 치료를 통해 회복 가능합니다.", \
    "emergency_measures": "수술 중 또는 수술 후 응급상황(대량출혈, 장기손상, 담즙누출, 감염 등) 발생 시 즉시 응급처치를 시행하고, 필요에 따라 중환자실 입원, 재수술, 인터벤션 시술, 항생제 치료, 수혈 등의 조치를 취하게 됩니다. 24시간 의료진이 대기하여 모든 응급상황에 신속하게 대응할 수 있는 체계를 갖추고 있습니다.", \
    "mortality_risk": "복강경 담낭절제술은 안전한 수술로 알려져 있으나, 모든 수술과 마찬가지로 매우 드물게 사망의 위험이 있을 수 있습니다. 사망 위험도는 환자의 나이, 전신상태, 동반질환, 수술의 복잡성 등을 종합적으로 고려할 때 1% 미만으로 예상되며, 마취 관련 위험도 포함되어 있습니다. 모든 안전조치를 통해 위험을 최소화하고 있습니다." \
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

test-chat-history:
	curl -X GET http://localhost:8000/chat/$(CHAT_ID)/history

test-chat-list:
	curl -X GET http://localhost:8000/chat/sessions

test-chat-delete:
	curl -X DELETE http://localhost:8000/chat/$(CHAT_ID)


# 통합 채팅 전체 플로우 테스트
test-chat-flow:
	@echo "=== 🏥 수술 동의서 통합 채팅 시스템 테스트 ==="
	@echo ""
	@echo "=== 1단계: 일반 질문 (동의서 데이터 없음) ==="
	@echo '{"message": "복강경 수술에 대해 설명해주세요.", "system_prompt": "당신은 수술 동의서 전문가입니다. 환자가 이해하기 쉽게 설명해주세요."}' | \
	curl -s -X POST http://localhost:8000/chat \
	     -H "Content-Type: application/json" \
	     -d @- | jq '.message, .is_content_modified'
	@echo ""
	@echo "=== 2단계: 동의서 데이터와 함께 질문 ==="
	@echo '{ \
	  "message": "이 수술의 합병증에 대해 설명해주세요.", \
	  "consents": { \
	    "prognosis_without_surgery": "담낭결석에 대해 수술을 시행하지 않을 경우, 급성 담낭염, 담관염, 췌장염 등의 심각한 합병증이 발생할 수 있으며, 지속적인 복통과 소화불량으로 일상생활에 큰 지장을 받을 수 있습니다. 또한 시간이 지날수록 담낭벽이 두꺼워지고 유착이 심해져 수술이 더욱 어려워질 수 있습니다.", \
	    "alternative_treatments": "담낭결석 치료를 위한 다른 방법으로는 체외충격파쇄석술(ESWL), 경구 담석용해제 복용, 경피적 담낭배액술 등이 있으나, 이러한 방법들은 효과가 제한적이고 재발률이 높아 근본적인 치료법인 수술적 치료가 가장 효과적인 것으로 알려져 있습니다.", \
	    "surgery_purpose_necessity_effect": "복강경 담낭절제술의 목적은 담낭결석으로 인한 염증과 통증을 근본적으로 해결하고, 급성 담낭염, 담관염, 췌장염 등의 심각한 합병증을 예방하는 것입니다. 수술을 통해 환자의 삶의 질을 크게 개선하고 정상적인 일상생활로의 복귀를 가능하게 합니다.", \
	    "surgery_method_content": { \
	      "overall_description": "복강경 담낭절제술은 배에 3-4개의 작은 구멍(5-12mm)을 뚫어 카메라(복강경)와 수술기구를 넣어 담낭을 제거하는 최소침습 수술입니다. 전신마취 하에 이산화탄소 가스를 넣어 복강을 부풀린 후, 담낭동맥과 담낭관을 찾아 안전하게 절단하고 담낭을 완전히 제거합니다.", \
	      "estimated_duration": "수술 시간은 환자의 상태와 수술의 복잡성에 따라 다르지만, 일반적으로 1-2시간 정도 소요되며, 수술 전 준비시간과 마취 시간을 포함하면 총 3-4시간 정도 소요될 예정입니다.", \
	      "method_change_or_addition": "수술 중 심한 염증, 유착, 출혈, 해부학적 이상 등으로 인해 복강경 수술이 어려울 경우 환자의 안전을 위해 개복수술로 전환할 수 있습니다. 또한 담관손상이나 기타 합병증 발생 시 추가적인 수술 절차가 필요할 수 있습니다.", \
	      "transfusion_possibility": "일반적으로 복강경 담낭절제술은 출혈이 적은 수술이므로 수혈이 필요한 경우는 드물지만, 예상치 못한 대량출혈이나 환자의 빈혈 상태에 따라 수혈이 필요할 수 있으며, 이 경우 적절한 혈액제제를 사용하게 됩니다.", \
	      "surgeon_change_possibility": "수술 중 응급상황 발생, 주치의의 컨디션 난조, 또는 기타 불가피한 사유로 인해 다른 숙련된 외과의사가 수술을 대신 진행할 수 있으며, 이 경우 수술의 연속성과 안전성을 보장하기 위해 충분한 인수인계가 이루어집니다." \
	    }, \
	    "possible_complications_sequelae": "복강경 담낭절제술과 관련하여 발생 가능한 합병증으로는 출혈, 감염, 담관손상, 장기손상, 마취 관련 합병증 등이 있습니다. 또한 수술 후 창상 감염, 복강 내 농양 형성, 담즙 누출, 일시적 소화불량 등이 발생할 수 있으며, 드물게는 재수술이 필요한 경우도 있습니다. 대부분의 합병증은 적절한 치료를 통해 회복 가능합니다.", \
	    "emergency_measures": "수술 중 또는 수술 후 응급상황(대량출혈, 장기손상, 담즙누출, 감염 등) 발생 시 즉시 응급처치를 시행하고, 필요에 따라 중환자실 입원, 재수술, 인터벤션 시술, 항생제 치료, 수혈 등의 조치를 취하게 됩니다. 24시간 의료진이 대기하여 모든 응급상황에 신속하게 대응할 수 있는 체계를 갖추고 있습니다.", \
	    "mortality_risk": "복강경 담낭절제술은 안전한 수술로 알려져 있으나, 모든 수술과 마찬가지로 매우 드물게 사망의 위험이 있을 수 있습니다. 사망 위험도는 환자의 나이, 전신상태, 동반질환, 수술의 복잡성 등을 종합적으로 고려할 때 1% 미만으로 예상되며, 마취 관련 위험도 포함되어 있습니다. 모든 안전조치를 통해 위험을 최소화하고 있습니다." \
	  }, \
	  "references": { \
	    "prognosis_without_surgery": [{"title": "Acute cholecystitis complications", "url": "https://www.uptodate.com/contents/acute-cholecystitis", "text": "Acute cholecystitis complications"}], \
	    "alternative_treatments": [{"title": "Non-surgical treatment options", "url": "https://www.cochranelibrary.com/gallstones", "text": "Non-surgical treatment options"}], \
	    "surgery_purpose_necessity_effect": [{"title": "Laparoscopic cholecystectomy indications", "url": "https://www.sages.org/cholecystectomy-guidelines", "text": "Laparoscopic cholecystectomy indications"}], \
	    "surgery_method_content": { \
	      "overall_description": [{"title": "Laparoscopic cholecystectomy technique", "url": "https://www.uptodate.com/contents/laparoscopic-cholecystectomy", "text": "Laparoscopic cholecystectomy technique"}], \
	      "estimated_duration": [{"title": "Operative time factors", "url": "https://www.annalsofsurgery.com/operative-time", "text": "Operative time factors"}], \
	      "method_change_or_addition": [{"title": "Conversion to open surgery", "url": "https://www.worldjournalofsurgery.com/conversion", "text": "Conversion to open surgery"}], \
	      "transfusion_possibility": [{"title": "Blood transfusion guidelines", "url": "https://www.transfusion-medicine.com/elective-surgery", "text": "Blood transfusion guidelines"}], \
	      "surgeon_change_possibility": [{"title": "Surgical team management", "url": "https://www.patient-safety.org/team-management", "text": "Surgical team management"}] \
	    }, \
	    "possible_complications_sequelae": [{"title": "Surgical complications", "url": "https://www.surgical-endoscopy.com/complications", "text": "Surgical complications"}], \
	    "emergency_measures": [{"title": "Emergency procedures", "url": "https://www.emergency-surgery.org/protocols", "text": "Emergency procedures"}], \
	    "mortality_risk": [{"title": "Mortality statistics", "url": "https://www.meta-analysis.com/mortality", "text": "Mortality statistics"}] \
	  } \
	}' | curl -s -X POST http://localhost:8000/chat \
	     -H "Content-Type: application/json" \
	     -d @- | jq '.message, .is_content_modified'
	@echo ""
	@echo "=== 3단계: 쉬운 말로 변경 요청 ==="
	@echo '{ \
	  "message": "더 쉬운 말로 바꿔주세요.", \
	  "consents": { \
	    "prognosis_without_surgery": "담낭결석에 대해 수술을 시행하지 않을 경우, 급성 담낭염, 담관염, 췌장염 등의 심각한 합병증이 발생할 수 있으며, 지속적인 복통과 소화불량으로 일상생활에 큰 지장을 받을 수 있습니다. 또한 시간이 지날수록 담낭벽이 두꺼워지고 유착이 심해져 수술이 더욱 어려워질 수 있습니다.", \
	    "alternative_treatments": "담낭결석 치료를 위한 다른 방법으로는 체외충격파쇄석술(ESWL), 경구 담석용해제 복용, 경피적 담낭배액술 등이 있으나, 이러한 방법들은 효과가 제한적이고 재발률이 높아 근본적인 치료법인 수술적 치료가 가장 효과적인 것으로 알려져 있습니다.", \
	    "surgery_purpose_necessity_effect": "복강경 담낭절제술의 목적은 담낭결석으로 인한 염증과 통증을 근본적으로 해결하고, 급성 담낭염, 담관염, 췌장염 등의 심각한 합병증을 예방하는 것입니다. 수술을 통해 환자의 삶의 질을 크게 개선하고 정상적인 일상생활로의 복귀를 가능하게 합니다.", \
	    "surgery_method_content": { \
	      "overall_description": "복강경 담낭절제술은 배에 3-4개의 작은 구멍(5-12mm)을 뚫어 카메라(복강경)와 수술기구를 넣어 담낭을 제거하는 최소침습 수술입니다. 전신마취 하에 이산화탄소 가스를 넣어 복강을 부풀린 후, 담낭동맥과 담낭관을 찾아 안전하게 절단하고 담낭을 완전히 제거합니다.", \
	      "estimated_duration": "수술 시간은 환자의 상태와 수술의 복잡성에 따라 다르지만, 일반적으로 1-2시간 정도 소요되며, 수술 전 준비시간과 마취 시간을 포함하면 총 3-4시간 정도 소요될 예정입니다.", \
	      "method_change_or_addition": "수술 중 심한 염증, 유착, 출혈, 해부학적 이상 등으로 인해 복강경 수술이 어려울 경우 환자의 안전을 위해 개복수술로 전환할 수 있습니다. 또한 담관손상이나 기타 합병증 발생 시 추가적인 수술 절차가 필요할 수 있습니다.", \
	      "transfusion_possibility": "일반적으로 복강경 담낭절제술은 출혈이 적은 수술이므로 수혈이 필요한 경우는 드물지만, 예상치 못한 대량출혈이나 환자의 빈혈 상태에 따라 수혈이 필요할 수 있으며, 이 경우 적절한 혈액제제를 사용하게 됩니다.", \
	      "surgeon_change_possibility": "수술 중 응급상황 발생, 주치의의 컨디션 난조, 또는 기타 불가피한 사유로 인해 다른 숙련된 외과의사가 수술을 대신 진행할 수 있으며, 이 경우 수술의 연속성과 안전성을 보장하기 위해 충분한 인수인계가 이루어집니다." \
	    }, \
	    "possible_complications_sequelae": "복강경 담낭절제술과 관련하여 발생 가능한 합병증으로는 출혈, 감염, 담관손상, 장기손상, 마취 관련 합병증 등이 있습니다. 또한 수술 후 창상 감염, 복강 내 농양 형성, 담즙 누출, 일시적 소화불량 등이 발생할 수 있으며, 드물게는 재수술이 필요한 경우도 있습니다. 대부분의 합병증은 적절한 치료를 통해 회복 가능합니다.", \
	    "emergency_measures": "수술 중 또는 수술 후 응급상황(대량출혈, 장기손상, 담즙누출, 감염 등) 발생 시 즉시 응급처치를 시행하고, 필요에 따라 중환자실 입원, 재수술, 인터벤션 시술, 항생제 치료, 수혈 등의 조치를 취하게 됩니다. 24시간 의료진이 대기하여 모든 응급상황에 신속하게 대응할 수 있는 체계를 갖추고 있습니다.", \
	    "mortality_risk": "복강경 담낭절제술은 안전한 수술로 알려져 있으나, 모든 수술과 마찬가지로 매우 드물게 사망의 위험이 있을 수 있습니다. 사망 위험도는 환자의 나이, 전신상태, 동반질환, 수술의 복잡성 등을 종합적으로 고려할 때 1% 미만으로 예상되며, 마취 관련 위험도 포함되어 있습니다. 모든 안전조치를 통해 위험을 최소화하고 있습니다." \
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
	  } \
	}' | \
	curl -X POST http://localhost:8000/chat \
	     -H "Content-Type: application/json" \
	     -d @-

# 단계별 통합 채팅 테스트
test-integrated-chat-demo:
	@echo "=== 📋 단계별 통합 채팅 데모 ==="
	@echo ""
	@echo "👤 사용자: 안녕하세요!"
	@echo '{"message": "안녕하세요!"}' | \
	curl -s -X POST http://localhost:8000/chat \
	     -H "Content-Type: application/json" \
	     -d @- | jq -r '.message' | sed 's/^/🤖 AI: /'
	@echo ""
	@echo "👤 사용자: 이 수술의 합병증에 대해 설명해주세요. (동의서 데이터 포함)"
	@echo '{"message": "이 수술의 합병증에 대해 설명해주세요.", "consents": {"prognosis_without_surgery": "담낭결석에 대해 수술을 시행하지 않을 경우, 급성 담낭염, 담관염, 췌장염 등의 심각한 합병증이 발생할 수 있으며, 지속적인 복통과 소화불량으로 일상생활에 큰 지장을 받을 수 있습니다. 또한 시간이 지날수록 담낭벽이 두꺼워지고 유착이 심해져 수술이 더욱 어려워질 수 있습니다.", "alternative_treatments": "담낭결석 치료를 위한 다른 방법으로는 체외충격파쇄석술(ESWL), 경구 담석용해제 복용, 경피적 담낭배액술 등이 있으나, 이러한 방법들은 효과가 제한적이고 재발률이 높아 근본적인 치료법인 수술적 치료가 가장 효과적인 것으로 알려져 있습니다.", "surgery_purpose_necessity_effect": "복강경 담낭절제술의 목적은 담낭결석으로 인한 염증과 통증을 근본적으로 해결하고, 급성 담낭염, 담관염, 췌장염 등의 심각한 합병증을 예방하는 것입니다. 수술을 통해 환자의 삶의 질을 크게 개선하고 정상적인 일상생활로의 복귀를 가능하게 합니다.", "surgery_method_content": {"overall_description": "복강경 담낭절제술은 배에 3-4개의 작은 구멍(5-12mm)을 뚫어 카메라(복강경)와 수술기구를 넣어 담낭을 제거하는 최소침습 수술입니다. 전신마취 하에 이산화탄소 가스를 넣어 복강을 부풀린 후, 담낭동맥과 담낭관을 찾아 안전하게 절단하고 담낭을 완전히 제거합니다.", "estimated_duration": "수술 시간은 환자의 상태와 수술의 복잡성에 따라 다르지만, 일반적으로 1-2시간 정도 소요되며, 수술 전 준비시간과 마취 시간을 포함하면 총 3-4시간 정도 소요될 예정입니다.", "method_change_or_addition": "수술 중 심한 염증, 유착, 출혈, 해부학적 이상 등으로 인해 복강경 수술이 어려울 경우 환자의 안전을 위해 개복수술로 전환할 수 있습니다. 또한 담관손상이나 기타 합병증 발생 시 추가적인 수술 절차가 필요할 수 있습니다.", "transfusion_possibility": "일반적으로 복강경 담낭절제술은 출혈이 적은 수술이므로 수혈이 필요한 경우는 드물지만, 예상치 못한 대량출혈이나 환자의 빈혈 상태에 따라 수혈이 필요할 수 있으며, 이 경우 적절한 혈액제제를 사용하게 됩니다.", "surgeon_change_possibility": "수술 중 응급상황 발생, 주치의의 컨디션 난조, 또는 기타 불가피한 사유로 인해 다른 숙련된 외과의사가 수술을 대신 진행할 수 있으며, 이 경우 수술의 연속성과 안전성을 보장하기 위해 충분한 인수인계가 이루어집니다."}, "possible_complications_sequelae": "복강경 담낭절제술과 관련하여 발생 가능한 합병증으로는 출혈, 감염, 담관손상, 장기손상, 마취 관련 합병증 등이 있습니다. 또한 수술 후 창상 감염, 복강 내 농양 형성, 담즙 누출, 일시적 소화불량 등이 발생할 수 있으며, 드물게는 재수술이 필요한 경우도 있습니다. 대부분의 합병증은 적절한 치료를 통해 회복 가능합니다.", "emergency_measures": "수술 중 또는 수술 후 응급상황(대량출혈, 장기손상, 담즙누출, 감염 등) 발생 시 즉시 응급처치를 시행하고, 필요에 따라 중환자실 입원, 재수술, 인터벤션 시술, 항생제 치료, 수혈 등의 조치를 취하게 됩니다. 24시간 의료진이 대기하여 모든 응급상황에 신속하게 대응할 수 있는 체계를 갖추고 있습니다.", "mortality_risk": "복강경 담낭절제술은 안전한 수술로 알려져 있으나, 모든 수술과 마찬가지로 매우 드물게 사망의 위험이 있을 수 있습니다. 사망 위험도는 환자의 나이, 전신상태, 동반질환, 수술의 복잡성 등을 종합적으로 고려할 때 1% 미만으로 예상되며, 마취 관련 위험도 포함되어 있습니다. 모든 안전조치를 통해 위험을 최소화하고 있습니다."}, "references": {"prognosis_without_surgery": [], "possible_complications_sequelae": [], "mortality_risk": []}}' | \
	curl -s -X POST http://localhost:8000/chat \
	     -H "Content-Type: application/json" \
	     -d @-

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
    "surgery_purpose_necessity_effect": "복강경 담낭절제술의 목적은 담낭결석으로 인한 염증과 통증을 근본적으로 해결하고, 급성 담낭염, 담관염, 췌장염 등의 심각한 합병증을 예방하는 것입니다. 수술을 통해 환자의 삶의 질을 크게 개선하고 정상적인 일상생활로의 복귀를 가능하게 합니다.", \
    "surgery_method_content": { \
      "overall_description": "복강경 담낭절제술은 배에 작은 구멍을 뚫어 카메라와 수술기구를 넣어 담낭을 제거하는 최소침습 수술입니다.", \
      "estimated_duration": "수술 시간은 환자의 상태와 수술의 복잡성에 따라 다르지만, 일반적으로 1-2시간 정도 소요되며, 수술 전 준비시간과 마취 시간을 포함하면 총 3-4시간 정도 소요될 예정입니다.", \
      "method_change_or_addition": "수술 중 심한 염증, 유착, 출혈, 해부학적 이상 등으로 인해 복강경 수술이 어려울 경우 환자의 안전을 위해 개복수술로 전환할 수 있습니다. 또한 담관손상이나 기타 합병증 발생 시 추가적인 수술 절차가 필요할 수 있습니다.", \
      "transfusion_possibility": "일반적으로 복강경 담낭절제술은 출혈이 적은 수술이므로 수혈이 필요한 경우는 드물지만, 예상치 못한 대량출혈이나 환자의 빈혈 상태에 따라 수혈이 필요할 수 있으며, 이 경우 적절한 혈액제제를 사용하게 됩니다.", \
      "surgeon_change_possibility": "수술 중 응급상황 발생, 주치의의 컨디션 난조, 또는 기타 불가피한 사유로 인해 다른 숙련된 외과의사가 수술을 대신 진행할 수 있으며, 이 경우 수술의 연속성과 안전성을 보장하기 위해 충분한 인수인계가 이루어집니다." \
    }, \
    "possible_complications_sequelae": "복강경 담낭절제술과 관련하여 발생 가능한 합병증으로는 출혈, 감염, 담관손상, 장기손상, 마취 관련 합병증 등이 있습니다. 또한 수술 후 창상 감염, 복강 내 농양 형성, 담즙 누출, 일시적 소화불량 등이 발생할 수 있으며, 드물게는 재수술이 필요한 경우도 있습니다. 대부분의 합병증은 적절한 치료를 통해 회복 가능합니다.", \
    "emergency_measures": "수술 중 또는 수술 후 응급상황(대량출혈, 장기손상, 담즙누출, 감염 등) 발생 시 즉시 응급처치를 시행하고, 필요에 따라 중환자실 입원, 재수술, 인터벤션 시술, 항생제 치료, 수혈 등의 조치를 취하게 됩니다. 24시간 의료진이 대기하여 모든 응급상황에 신속하게 대응할 수 있는 체계를 갖추고 있습니다.", \
    "mortality_risk": "복강경 담낭절제술은 안전한 수술로 알려져 있으나, 모든 수술과 마찬가지로 매우 드물게 사망의 위험이 있을 수 있습니다. 사망 위험도는 환자의 나이, 전신상태, 동반질환, 수술의 복잡성 등을 종합적으로 고려할 때 1% 미만으로 예상되며, 마취 관련 위험도 포함되어 있습니다. 모든 안전조치를 통해 위험을 최소화하고 있습니다." \
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