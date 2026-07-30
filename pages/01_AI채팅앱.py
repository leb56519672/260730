import streamlit as st
from openai import OpenAI

# 페이지 기본 설정
st.set_page_config(page_title="AI 정보 선생님", page_icon="🤖")
st.title("🥸 AI 정보 선생님")

# 비밀 금고(secrets)에서 API 키를 꺼내 접속 준비
client = OpenAI(
    api_key=st.secrets["SOLAR_API_KEY"],
    base_url="https://api.upstage.ai/v1",
)

# AI의 성격 (시스템 프롬프트)
SYSTEM_PROMPT = (
    "너는 중고등학생에게 설명하는 친절한 정보 선생님이야. "
    "어려운 말은 쉬운 말로 바꿔 주고, 반드시 순수 한국어로만 답해"
)

# 대화 기록이 없으면 처음 한 번만 초기화
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

# 1. [개선] 사이드바: 대화 초기화 버튼 구현
with st.sidebar:
    st.header("⚙️ 대화 설정")
    if st.button("🧹 대화 내용 초기화", use_container_width=True):
        st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        st.rerun()

# 지금까지의 대화를 말풍선으로 그리기 (system 메시지는 제외)
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# 채팅 입력창
user_input = st.chat_input("궁금한 것을 물어보세요!")

if user_input:
    # 보낸 질문을 기록에 저장하고 화면에 표출
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # AI 답 받아오기
    with st.chat_message("assistant"):
        try:
            # 2. [개선] 토큰 한도 초과 방지: system 메시지 + 최근 10개 메시지만 전송
            messages_to_send = [st.session_state.messages[0]] + st.session_state.messages[-10:]

            # 3. [개선] 스피너 적용 & 안전한 스트리밍 제너레이터 함수
            with st.spinner("선생님이 생각을 정리하고 있어요..."):
                stream = client.chat.completions.create(
                    model="solar-open2",
                    messages=messages_to_send,
                    reasoning_effort="none",
                    stream=True,
                )

            # None 값을 걸러내어 안전하게 텍스트만 넘겨주는 제너레이터
            def safe_stream_generator():
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content

            # 실시간으로 화면에 텍스트 표출
            answer = st.write_stream(safe_stream_generator())
            
            # 완성된 답변을 대화 기록에 저장
            st.session_state.messages.append({"role": "assistant", "content": answer})
            
        except Exception:
            st.error("응답을 받지 못했습니다. 잠시 후 다시 질문해 주세요.")
