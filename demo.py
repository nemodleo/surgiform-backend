import gradio as gr
import requests
import time
import json
from datetime import date

API_URL = "http://localhost:8000/consent"
HEALTH_URL = "http://localhost:8000/health"
CHAT_SESSION_URL = "http://localhost:8000/chat/session"
CHAT_URL = "http://localhost:8000/chat"
CHAT_SESSIONS_URL = "http://localhost:8000/chat/sessions"
TRANSFORM_URL = "http://localhost:8000/transform"


def test_health():
    """Health check API 테스트"""
    try:
        start_time = time.time()
        response = requests.get(HEALTH_URL, timeout=10)
        end_time = time.time()
        latency = round((end_time - start_time) * 1000, 2)  # milliseconds
        
        response.raise_for_status()
        result = response.json()
        
        status = "✅ 정상" if response.status_code == 200 else f"❌ 오류 (상태코드: {response.status_code})"
        return status, result, f"⏱️ 응답시간: {latency}ms"
        
    except Exception as e:
        return f"❌ 연결 실패: {str(e)}", {}, "❌ 연결 실패"


def create_chat_session(system_prompt):
    """채팅 세션 생성"""
    try:
        start_time = time.time()
        payload = {"system_prompt": system_prompt}
        response = requests.post(CHAT_SESSION_URL, json=payload, timeout=30)
        end_time = time.time()
        latency = round((end_time - start_time) * 1000, 2)
        
        response.raise_for_status()
        result = response.json()
        
        return f"✅ 세션 생성 완료", result, f"⏱️ 응답시간: {latency}ms"
        
    except Exception as e:
        return f"❌ 세션 생성 실패: {str(e)}", {}, "❌ 연결 실패"


def send_chat_message(message):
    """채팅 메시지 전송"""
    try:
        start_time = time.time()
        payload = {"message": message}
        response = requests.post(CHAT_URL, json=payload, timeout=60)
        end_time = time.time()
        latency = round((end_time - start_time) * 1000, 2)
        
        response.raise_for_status()
        result = response.json()
        
        return f"✅ 메시지 전송 완료", result, f"⏱️ 응답시간: {latency}ms"
        
    except Exception as e:
        return f"❌ 메시지 전송 실패: {str(e)}", {}, "❌ 연결 실패"


def get_chat_sessions():
    """채팅 세션 목록 조회"""
    try:
        start_time = time.time()
        response = requests.get(CHAT_SESSIONS_URL, timeout=30)
        end_time = time.time()
        latency = round((end_time - start_time) * 1000, 2)
        
        response.raise_for_status()
        result = response.json()
        
        return f"✅ 세션 목록 조회 완료", result, f"⏱️ 응답시간: {latency}ms"
        
    except Exception as e:
        return f"❌ 세션 목록 조회 실패: {str(e)}", {}, "❌ 연결 실패"


def transform_consent(consent_data, mode):
    """수술동의서 변환/번역"""
    try:
        start_time = time.time()
        
        # JSON 문자열을 파싱
        try:
            consent_json = json.loads(consent_data)
        except json.JSONDecodeError as e:
            return f"❌ JSON 파싱 오류: {str(e)}", {}, "❌ JSON 오류"
        
        # mode 추가
        consent_json["mode"] = mode
        
        response = requests.post(TRANSFORM_URL, json=consent_json, timeout=60)
        end_time = time.time()
        latency = round((end_time - start_time) * 1000, 2)
        
        response.raise_for_status()
        result = response.json()
        
        return f"✅ 변환 완료", result, f"⏱️ 응답시간: {latency}ms"
        
    except Exception as e:
        return f"❌ 변환 실패: {str(e)}", {}, "❌ 연결 실패"


def generate_consent(
    surgery_name, registration_no, patient_name, age, gender, scheduled_date,
    diagnosis, surgical_site_mark, patient_condition,
    is_lead, is_specialist, department,
    past_history, diabetes, smoking, hypertension, allergy, cardiovascular,
    respiratory, coagulation, medications, renal, drug_abuse, other_conditions,
    mortality_risk, morbidity_risk
):
    payload = {
        "surgery_name": surgery_name,
        "registration_no": registration_no,
        "patient_name": patient_name,
        "age": int(age),
        "gender": gender,
        "scheduled_date": scheduled_date,
        "diagnosis": diagnosis,
        "surgical_site_mark": surgical_site_mark,
        "participants": [
            {"is_lead": is_lead, "is_specialist": is_specialist, "department": department}
        ],
        "patient_condition": patient_condition,
        "special_conditions": {
            "past_history": past_history,
            "diabetes": diabetes,
            "smoking": smoking,
            "hypertension": hypertension,
            "allergy": allergy,
            "cardiovascular": cardiovascular,
            "respiratory": respiratory,
            "coagulation": coagulation,
            "medications": medications,
            "renal": renal,
            "drug_abuse": drug_abuse,
            "other": other_conditions if other_conditions.strip() else None
        },
        "possum_score": {
            "mortality_risk": float(mortality_risk),
            "morbidity_risk": float(morbidity_risk)
        }
    }

    try:
        start_time = time.time()
        response = requests.post(API_URL, json=payload, timeout=60)
        end_time = time.time()
        latency = round((end_time - start_time) * 1000, 2)  # milliseconds
        
        response.raise_for_status()
        result = response.json()
        
        consents = result["consents"]
        surgery_method = consents["surgery_method_content"]
        
        return (
            consents["prognosis_without_surgery"],
            consents["alternative_treatments"], 
            consents["surgery_purpose_necessity_effect"],
            surgery_method["overall_description"],
            surgery_method["estimated_duration"],
            surgery_method["method_change_or_addition"],
            surgery_method["transfusion_possibility"],
            surgery_method["surgeon_change_possibility"],
            consents["possible_complications_sequelae"],
            consents["emergency_measures"],
            consents["mortality_risk"],
            result["references"],
            f"⏱️ API 응답시간: {latency}ms"
        )
    except Exception as e:
        error_msg = f"❌ 오류: {str(e)}"
        return (error_msg, error_msg, error_msg, error_msg, error_msg, error_msg, error_msg, error_msg, error_msg, error_msg, error_msg, {}, error_msg)


# 수술동의서 생성 탭
consent_interface = gr.Interface(
    fn=generate_consent,
    inputs=[
        # 기본 정보
        gr.Textbox(label="수술명 (영문)", value="Cholelithiasis"),
        gr.Textbox(label="등록번호", value="2024001"),
        gr.Textbox(label="환자명", value="홍길동"),
        gr.Number(label="나이", value=45),
        gr.Radio(label="성별", choices=["M", "F"], value="M"),
        gr.Textbox(label="수술 예정일 (YYYY-MM-DD)", value=str(date.today())),
        gr.Textbox(label="진단명", value="Cholelithiasis"),
        gr.Textbox(label="수술 부위 표시", value="RUQ"),
        gr.Textbox(label="현재 환자 상태 요약", value="Stable"),
        
        # 참여자 정보
        gr.Checkbox(label="주치의 여부", value=True),
        gr.Checkbox(label="전문의 여부", value=True),
        gr.Textbox(label="진료과", value="GS"),
        
        # 특수 조건들
        gr.Checkbox(label="과거 병력", value=False),
        gr.Checkbox(label="당뇨", value=False),
        gr.Checkbox(label="흡연", value=False),
        gr.Checkbox(label="고혈압", value=False),
        gr.Checkbox(label="알레르기", value=False),
        gr.Checkbox(label="심혈관 질환", value=False),
        gr.Checkbox(label="호흡기 질환", value=False),
        gr.Checkbox(label="응고 장애", value=False),
        gr.Checkbox(label="복용 약물", value=False),
        gr.Checkbox(label="신장 질환", value=False),
        gr.Checkbox(label="약물 남용", value=False),
        gr.Textbox(label="기타 특수 조건", value=""),
        
        # POSSUM Score
        gr.Number(label="사망 위험도 (%)", value=0.22),
        gr.Number(label="이환 위험도 (%)", value=5.47),
    ],
    outputs=[
        gr.Textbox(label="예정된 수술을 하지 않을 경우의 예후"),
        gr.Textbox(label="예정된 수술 이외의 시행 가능한 다른 방법"),
        gr.Textbox(label="수술의 목적/필요성/효과"),
        gr.Textbox(label="수술 과정 전반에 대한 설명"),
        gr.Textbox(label="수술 추정 소요시간"),
        gr.Textbox(label="수술 방법 변경 및 수술 추가 가능성"),
        gr.Textbox(label="수혈 가능성"),
        gr.Textbox(label="집도의 변경 가능성"),
        gr.Textbox(label="발생 가능한 합병증/후유증/부작용"),
        gr.Textbox(label="문제 발생시 조치사항"),
        gr.Textbox(label="진단/수술 관련 사망 위험성"),
        gr.JSON(label="참고 문헌 (링크)"),
        gr.Textbox(label="API 응답 시간")
    ],
    title="📝 수술동의서 생성",
    description="입력값을 기반으로 LLM이 수술동의서 내용을 생성합니다."
)

# Health Check 탭
health_interface = gr.Interface(
    fn=test_health,
    inputs=[],
    outputs=[
        gr.Textbox(label="상태"),
        gr.JSON(label="응답 내용"),
        gr.Textbox(label="응답 시간")
    ],
    title="🔧 Health Check",
    description="API 서버의 상태를 확인합니다. (curl -X GET http://localhost:8000/health와 동일)"
)

# 채팅 탭
with gr.Blocks() as chat_interface:
    gr.Markdown("# 💬 채팅 테스트")
    gr.Markdown("의료 AI와 채팅하고 세션을 관리할 수 있습니다.")
    
    with gr.Row():
        with gr.Column():
            gr.Markdown("### 1. 채팅 세션 생성")
            system_prompt_input = gr.Textbox(
                label="시스템 프롬프트", 
                value="당신은 의료 전문가입니다.",
                lines=3
            )
            session_create_btn = gr.Button("세션 생성")
            
        with gr.Column():
            session_status = gr.Textbox(label="상태")
            session_response = gr.JSON(label="응답")
            session_latency = gr.Textbox(label="응답 시간")
    
    session_create_btn.click(
        fn=create_chat_session,
        inputs=[system_prompt_input],
        outputs=[session_status, session_response, session_latency]
    )
    
    gr.Markdown("---")
    
    with gr.Row():
        with gr.Column():
            gr.Markdown("### 2. 메시지 전송")
            message_input = gr.Textbox(
                label="메시지", 
                value="안녕하세요!",
                lines=3
            )
            message_send_btn = gr.Button("메시지 전송")
            
        with gr.Column():
            message_status = gr.Textbox(label="상태")
            message_response = gr.JSON(label="응답")
            message_latency = gr.Textbox(label="응답 시간")
    
    message_send_btn.click(
        fn=send_chat_message,
        inputs=[message_input],
        outputs=[message_status, message_response, message_latency]
    )
    
    gr.Markdown("---")
    
    with gr.Row():
        with gr.Column():
            gr.Markdown("### 3. 세션 목록 조회")
            sessions_get_btn = gr.Button("세션 목록 조회")
            
        with gr.Column():
            sessions_status = gr.Textbox(label="상태")
            sessions_response = gr.JSON(label="응답")
            sessions_latency = gr.Textbox(label="응답 시간")
    
    sessions_get_btn.click(
        fn=get_chat_sessions,
        inputs=[],
        outputs=[sessions_status, sessions_response, sessions_latency]
    )

# Transform 탭
transform_interface = gr.Interface(
    fn=transform_consent,
    inputs=[
        gr.Textbox(
            label="수술동의서 JSON 데이터",
            value='{"consents": {"prognosis_without_surgery": "수술을 하지 않을 경우의 예후", "alternative_treatments": "다른 치료 방법", "surgery_purpose_necessity_effect": "수술의 목적/필요성/효과", "surgery_method_content": {"overall_description": "수술 과정 설명", "estimated_duration": "2-4시간", "method_change_or_addition": "수술 방법 변경 가능성", "transfusion_possibility": "수혈 가능성", "surgeon_change_possibility": "집도의 변경 가능성"}, "possible_complications_sequelae": "가능한 합병증", "emergency_measures": "응급처치 방법", "mortality_risk": "사망 위험성"}, "references": {"prognosis_without_surgery": [], "alternative_treatments": [], "surgery_purpose_necessity_effect": [], "surgery_method_content": {"overall_description": [], "estimated_duration": [], "method_change_or_addition": [], "transfusion_possibility": [], "surgeon_change_possibility": []}, "possible_complications_sequelae": [], "emergency_measures": [], "mortality_risk": []}}',
            lines=10
        ),
        gr.Radio(
            label="변환 모드",
            choices=["translate_en", "translate_ko", "summarize"],
            value="translate_en"
        )
    ],
    outputs=[
        gr.Textbox(label="상태"),
        gr.JSON(label="변환 결과"),
        gr.Textbox(label="응답 시간")
    ],
    title="🔄 Transform",
    description="수술동의서 데이터를 번역하거나 변환합니다."
)

# 탭 인터페이스 생성
demo = gr.TabbedInterface(
    [consent_interface, health_interface, chat_interface, transform_interface],
    ["📝 수술동의서 생성", "🔧 Health Check", "💬 채팅", "🔄 Transform"],
    title="🏥 Surgiform Backend Demo"
)

if __name__ == "__main__":
    demo.launch()