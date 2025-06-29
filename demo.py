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

# 전역 상태: 동의서 결과 저장용
consent_result_state = {"data": None, "timestamp": None}


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
        return status, result, f"⏱️ 응답시간: {latency/1000:.2f}초"
        
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
        
        return f"✅ 세션 생성 완료", result, f"⏱️ 응답시간: {latency/1000:.2f}초"
        
    except Exception as e:
        return f"❌ 세션 생성 실패: {str(e)}", {}, "❌ 연결 실패"


def send_chat_message(message, conversation_id="", use_consent_data=False):
    """채팅 메시지 전송 - 수술 동의서 통합 기능 포함"""
    try:
        start_time = time.time()
        
        # 기본 페이로드
        payload = {"message": message}
        
        # 대화 ID가 있으면 추가
        if conversation_id.strip():
            payload["conversation_id"] = conversation_id.strip()
        
        # 동의서 데이터 사용 옵션이 켜져 있고 저장된 데이터가 있으면 추가
        if use_consent_data and consent_result_state["data"]:
            consent_data = consent_result_state["data"]
            payload["consents"] = consent_data["consents"]
            payload["references"] = consent_data["references"]
        
        response = requests.post(CHAT_URL, json=payload, timeout=60)
        end_time = time.time()
        latency = round((end_time - start_time) * 1000, 2)
        
        response.raise_for_status()
        result = response.json()
        
        # 응답 분석
        status_msg = "✅ 메시지 전송 완료"
        if result.get("is_content_modified", False):
            status_msg += " 🔄 동의서가 변환되었습니다!"
        
        return status_msg, result, f"⏱️ 응답시간: {latency/1000:.2f}초"
        
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
        
        return f"✅ 세션 목록 조회 완료", result, f"⏱️ 응답시간: {latency/1000:.2f}초"
        
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
        
        return f"✅ 변환 완료", result, f"⏱️ 응답시간: {latency/1000:.2f}초"
        
    except Exception as e:
        return f"❌ 변환 실패: {str(e)}", {}, "❌ 연결 실패"


def generate_consent(
    surgery_name, registration_no, patient_name, age, gender, scheduled_date,
    diagnosis, surgical_site_mark, patient_condition,
    name, is_specialist, department,
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
            {"name": name, "is_specialist": is_specialist, "department": department}
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
        
        # 전역 상태에 결과 저장
        global consent_result_state
        consent_result_state["data"] = result
        consent_result_state["timestamp"] = time.time()
        
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
            f"⏱️ API 응답시간: {latency/1000:.2f}초",
            json.dumps(result, ensure_ascii=False, indent=2)  # JSON 결과 추가
        )
    except Exception as e:
        error_msg = f"❌ 오류: {str(e)}"
        return (error_msg, error_msg, error_msg, error_msg, error_msg, error_msg, error_msg, error_msg, error_msg, error_msg, error_msg, {}, error_msg, "{}")


def load_consent_result():
    """저장된 동의서 결과를 로드합니다."""
    global consent_result_state
    if consent_result_state["data"] is None:
        return "❌ 저장된 동의서 결과가 없습니다. 먼저 동의서를 생성해주세요.", "{}"
    
    # 생성 시간 계산
    elapsed = time.time() - consent_result_state["timestamp"]
    time_info = f"⏰ {elapsed/60:.1f}분 전에 생성됨"
    
    json_data = json.dumps(consent_result_state["data"], ensure_ascii=False, indent=2)
    return f"✅ 동의서 결과를 로드했습니다. {time_info}", json_data


def clear_consent_result():
    """저장된 동의서 결과를 삭제합니다."""
    global consent_result_state
    consent_result_state["data"] = None
    consent_result_state["timestamp"] = None
    return "✅ 저장된 동의서 결과를 삭제했습니다.", "{}"


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
        gr.Textbox(label="의료진 성명", value="박현"),
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
        gr.Textbox(label="API 응답 시간"),
        gr.JSON(label="JSON 결과")
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
    gr.Markdown("# 💬 수술 동의서 통합 채팅")
    gr.Markdown("의료 AI와 채팅하고, 동의서에 대한 질문이나 변경 요청을 할 수 있습니다.")
    
    with gr.Row():
        with gr.Column():
            gr.Markdown("### 1. 채팅 세션 생성")
            system_prompt_input = gr.Textbox(
                label="시스템 프롬프트", 
                value="당신은 수술 동의서 전문가입니다. 환자가 이해하기 쉽게 설명해주세요.",
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
            gr.Markdown("### 2. 통합 채팅 메시지")
            
            # 동의서 데이터 상태 표시
            consent_status = gr.Textbox(
                label="동의서 데이터 상태",
                value="❌ 동의서 데이터 없음 (동의서 생성 탭에서 먼저 생성하세요)",
                interactive=False
            )
            
            # 동의서 데이터 새로고침 버튼
            refresh_consent_btn = gr.Button("🔄 동의서 데이터 새로고침", variant="secondary")
            
            conversation_id_input = gr.Textbox(
                label="세션 ID (선택사항)", 
                placeholder="기존 대화를 이어가려면 세션 ID 입력",
                lines=1
            )
            
            use_consent_toggle = gr.Checkbox(
                label="🏥 동의서 데이터 사용 (질문/변경 요청시)",
                value=True,
                info="체크하면 동의서 내용을 바탕으로 답변하거나 변경 요청을 처리합니다"
            )
            
            message_input = gr.Textbox(
                label="메시지", 
                placeholder="예: '이 수술의 위험성을 설명해주세요' 또는 '더 쉬운 말로 바꿔주세요'",
                lines=3
            )
            
            # 예시 메시지 버튼들
            with gr.Row():
                example_btn1 = gr.Button("💬 수술 위험성 질문", size="sm")
                example_btn2 = gr.Button("🔄 쉬운 말로 변경", size="sm")
                example_btn3 = gr.Button("📝 5줄 요약 요청", size="sm")
            
            message_send_btn = gr.Button("메시지 전송", variant="primary")
            
        with gr.Column():
            message_status = gr.Textbox(label="상태")
            message_response = gr.JSON(label="채팅 응답")
            message_latency = gr.Textbox(label="응답 시간")
            
            # 변환된 동의서 표시
            gr.Markdown("### 변환된 동의서 (변경 요청시)")
            modified_consent_display = gr.JSON(label="수정된 동의서", visible=False)
    
    # 동의서 상태 새로고침 함수
    def refresh_consent_status():
        global consent_result_state
        if consent_result_state["data"] is None:
            return "❌ 동의서 데이터 없음 (동의서 생성 탭에서 먼저 생성하세요)"
        else:
            elapsed = time.time() - consent_result_state["timestamp"]
            return f"✅ 동의서 데이터 있음 ({elapsed/60:.1f}분 전 생성)"
    
    # 예시 메시지 설정 함수들
    def set_example_message_1():
        return "이 수술의 위험성과 합병증에 대해 자세히 설명해주세요."
    
    def set_example_message_2():
        return "이 동의서를 더 쉬운 말로 바꿔주세요."
    
    def set_example_message_3():
        return "이 동의서 내용을 5줄로 요약해주세요."
    
    # 채팅 응답 처리 함수
    def handle_chat_response(message, conversation_id, use_consent_data, status, result, latency):
        # 변환된 동의서가 있는지 확인
        if result and result.get("is_content_modified", False):
            return (
                status, result, latency,
                gr.update(value=result.get("updated_consents", {}), visible=True)
            )
        else:
            return (
                status, result, latency,
                gr.update(visible=False)
            )
    
    # 이벤트 핸들러들
    refresh_consent_btn.click(
        fn=refresh_consent_status,
        outputs=[consent_status]
    )
    
    example_btn1.click(
        fn=set_example_message_1,
        outputs=[message_input]
    )
    
    example_btn2.click(
        fn=set_example_message_2,
        outputs=[message_input]
    )
    
    example_btn3.click(
        fn=set_example_message_3,
        outputs=[message_input]
    )
    
    message_send_btn.click(
        fn=send_chat_message,
        inputs=[message_input, conversation_id_input, use_consent_toggle],
        outputs=[message_status, message_response, message_latency]
    ).then(
        fn=handle_chat_response,
        inputs=[message_input, conversation_id_input, use_consent_toggle, message_status, message_response, message_latency],
        outputs=[message_status, message_response, message_latency, modified_consent_display]
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
    
    # 사용법 안내
    gr.Markdown("""
    ### 💡 사용법
    
    **1단계**: 먼저 '📝 수술동의서 생성' 탭에서 동의서를 생성하세요.
    
    **2단계**: 채팅에서 다음과 같이 사용할 수 있습니다:
    - **질문하기**: "이 수술의 위험성은 무엇인가요?"
    - **쉬운 말로 변경**: "더 쉬운 말로 바꿔주세요"
    - **요약 요청**: "5줄로 요약해주세요"
    - **번역 요청**: "영어로 번역해주세요"
    
    **3단계**: 변경 요청 시 '수정된 동의서' 섹션에서 결과를 확인하세요.
    """)

# Transform 탭
with gr.Blocks() as transform_interface:
    gr.Markdown("# 🔄 Transform")
    gr.Markdown("수술동의서 데이터를 번역하거나 변환합니다.")
    
    with gr.Row():
        with gr.Column():
            gr.Markdown("### 1. 동의서 데이터 관리")
            with gr.Row():
                load_btn = gr.Button("📥 저장된 동의서 로드", variant="secondary")
                clear_btn = gr.Button("🗑️ 저장된 데이터 삭제", variant="secondary")
            
            load_status = gr.Textbox(label="로드 상태", interactive=False)
            
            gr.Markdown("### 2. 변환 설정")
            consent_json_input = gr.Textbox(
                label="수술동의서 JSON 데이터",
                value='{"consents": {"prognosis_without_surgery": "수술을 하지 않을 경우의 예후", "alternative_treatments": "다른 치료 방법", "surgery_purpose_necessity_effect": "수술의 목적/필요성/효과", "surgery_method_content": {"overall_description": "수술 과정 설명", "estimated_duration": "2-4시간", "method_change_or_addition": "수술 방법 변경 가능성", "transfusion_possibility": "수혈 가능성", "surgeon_change_possibility": "집도의 변경 가능성"}, "possible_complications_sequelae": "가능한 합병증", "emergency_measures": "응급처치 방법", "mortality_risk": "사망 위험성"}, "references": {"prognosis_without_surgery": [], "alternative_treatments": [], "surgery_purpose_necessity_effect": [], "surgery_method_content": {"overall_description": [], "estimated_duration": [], "method_change_or_addition": [], "transfusion_possibility": [], "surgeon_change_possibility": []}, "possible_complications_sequelae": [], "emergency_measures": [], "mortality_risk": []}}',
                lines=15
            )
            
            mode_input = gr.Radio(
                label="변환 모드",
                choices=["translate_en", "translate_ko", "summarize"],
                value="translate_en"
            )
            
            transform_btn = gr.Button("🔄 변환 실행", variant="primary")
            
        with gr.Column():
            gr.Markdown("### 3. 변환 결과")
            transform_status = gr.Textbox(label="변환 상태")
            transform_result = gr.JSON(label="변환 결과")
            transform_latency = gr.Textbox(label="응답 시간")
    
    # 이벤트 핸들러
    load_btn.click(
        fn=load_consent_result,
        inputs=[],
        outputs=[load_status, consent_json_input]
    )
    
    clear_btn.click(
        fn=clear_consent_result,
        inputs=[],
        outputs=[load_status, consent_json_input]
    )
    
    transform_btn.click(
        fn=transform_consent,
        inputs=[consent_json_input, mode_input],
        outputs=[transform_status, transform_result, transform_latency]
    )

# 탭 인터페이스 생성
demo = gr.TabbedInterface(
    [consent_interface, health_interface, chat_interface, transform_interface],
    ["📝 수술동의서 생성", "🔧 Health Check", "💬 수술 동의서 통합 채팅", "🔄 Transform"],
    title="🏥 Surgiform Backend Demo"
)

if __name__ == "__main__":
    demo.launch()