"""
LLMOps Chat UI (Streamlit)

에이전트 서버(app/server.py)와 통신하여 채팅 인터페이스를 제공합니다.
- AGENT_REGISTRY 기반으로 사이드바에 에이전트 목록 및 세부 역할을 동적으로 렌더링합니다.
- 실시간 SSE 스트리밍을 통해 개별 도구(Tool) 실행 시작/완료 상태 및 LLM 토큰 출력을 완벽히 동화시킵니다.
- 입력을 차단하는 생성 플래그 잠금(Generating Lock Buffer)과 ⏹️ 크롤링 중단 제어를 지원합니다.
- <Render_Image> 태그를 파싱하여 크롤링된 결과 스크린샷 등을 실시간 렌더링합니다.
"""

import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import re
import uuid
from app.client import AgentClient
from app.agents import AGENT_REGISTRY

# --- Page Config ---
st.set_page_config(page_title="LLMOps AI Chat", layout="wide")

# --- Initialize Client ---
@st.cache_resource
def get_client():
    return AgentClient(base_url="http://localhost:8000")

client = get_client()

# --- Agent Options (Registry 기반 자동 생성) ---
agent_options = {a["name"]: a["description"] for a in AGENT_REGISTRY}


# --- Helpers ---
def render_message_content(content):
    """
    텍스트 내의 <Render_Image> 태그를 파싱하여
    텍스트와 이미지를 순서대로 렌더링합니다.
    """
    # 이미지 태그 패턴: <Render_Image>경로</Render_Image>
    pattern = re.compile(r"<Render_Image>(.*?)</Render_Image>")
    
    # 태그를 기준으로 텍스트를 분할 (split하면 텍스트와 경로가 번갈아 나옴)
    parts = pattern.split(content)
    
    for i, part in enumerate(parts):
        # 짝수 인덱스는 일반 텍스트, 홀수 인덱스는 이미지 경로
        if i % 2 == 0:
            if part.strip():
                st.markdown(part)
        else:
            # 이미지 경로
            image_path = part.strip()
            if os.path.exists(image_path):
                st.image(image_path, caption=os.path.basename(image_path))
            else:
                st.error(f"Image not found: {image_path}")


# --- Initialize Session State ---
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

# 응답 생성 중 입력 비활성화를 위한 플래그
if "generating" not in st.session_state:
    st.session_state.generating = False

# 입력 즉시 잠금 후 다음 렌더링 사이클에서 처리하기 위한 버퍼
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None

# 스트리밍 중단 시 부분 응답을 보존하기 위한 버퍼
if "partial_response" not in st.session_state:
    st.session_state.partial_response = None


# --- Sidebar ---
with st.sidebar:
    st.title("🤖 AAWS Scraping Team")
    st.markdown("수집 미션을 수행할 전용 에이전트를 선택하세요.")
    
    # Agent Selector (Registry 기반)
    agent_name = st.radio(
        "Select Agent",
        list(agent_options.keys()),
        format_func=lambda x: f"💼 {x.upper()} — {agent_options[x]}",
        index=0
    )
    
    st.markdown("---")
    st.caption(f"Thread ID: {st.session_state.thread_id}")
    if st.button("New Chat"):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.generating = False
        st.session_state.pending_prompt = None
        st.session_state.partial_response = None
        st.rerun()


# --- Main Chat Interface ---
st.subheader(f"Chat with `{agent_name}`")

# 1. Display Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        # 저장된 메시지는 렌더링 함수를 통해 처리 (이미지 태그 파싱 포함)
        render_message_content(msg["content"])

# 2. 스트리밍 중단 후 부분 응답이 남아있으면 히스토리에 저장
if st.session_state.partial_response is not None:
    partial = st.session_state.partial_response + "\n\n*(크롤링이 사용자에 의해 중단되었습니다)*"
    st.session_state.messages.append({"role": "assistant", "content": partial})
    st.session_state.partial_response = None
    st.session_state.generating = False
    st.rerun()

# 3. 응답 생성 중이면 정지 버튼 표시
if st.session_state.generating and st.session_state.pending_prompt:
    pass  # 아직 처리 전 (아래에서 스트리밍 시작)
elif st.session_state.generating:
    # 스트리밍이 진행 중인데 이 코드에 도달한 경우 = 정지 버튼 클릭으로 rerun됨
    st.session_state.generating = False

# 4. Chat Input (응답 생성 중에는 입력 비활성화)
#    Phase 1: 입력을 받으면 pending_prompt에 저장 → 즉시 rerun으로 UI 잠금
if prompt := st.chat_input("메시지 및 수집 요구사항을 입력하세요...", disabled=st.session_state.generating):
    st.session_state.pending_prompt = prompt
    st.session_state.generating = True
    st.rerun()  # 즉시 rerun → chat_input이 disabled=True로 재렌더링됨

# 5. Process Pending Prompt
#    Phase 2: 이전 렌더링에서 저장된 프롬프트를 처리 (이 시점에서 입력은 이미 잠김)
if st.session_state.pending_prompt and st.session_state.generating:
    prompt = st.session_state.pending_prompt
    st.session_state.pending_prompt = None  # 버퍼 비우기
    
    # Add User Message to History
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 6. Agent Response (Streaming)
    with st.chat_message("assistant"):
        # 스트리밍 텍스트 표시 영역 (완료 후 render_message_content로 교체됨)
        message_placeholder = st.empty()
        # "생각 중..." 표시 영역 (도구 완료 → 토큰 도착 사이의 대기 상태 표시)
        thinking_placeholder = st.empty()
        full_response = ""
        
        # 정지 버튼 — 클릭 시 Streamlit이 스크립트를 중단하고 rerun합니다.
        # 부분 응답은 partial_response에 저장되어 다음 렌더링에서 히스토리에 추가됩니다.
        if st.button("⏹ 중단"):
            st.session_state.partial_response = full_response
            st.session_state.generating = False
            st.rerun()
        
        # Streamlit은 스트리밍 중에 이미지를 중간중간 띄우기 까다로우므로
        # 텍스트가 완성된 후에 파싱해서 렌더링하는 방식이 안전합니다.
        
        # A. SSE 스트리밍 수신 루프
        current_tool_status = None  # 현재 실행 중인 도구의 status 위젯 참조
        
        for chunk in client.stream(agent_name, prompt, st.session_state.thread_id):
            if "type" in chunk:
                
                # --- 토큰 수신: LLM이 생성한 텍스트를 실시간으로 표시 ---
                if chunk["type"] == "token":
                    thinking_placeholder.empty()  # "생각 중..." 제거
                    content = chunk.get("content", "")
                    full_response += content
                    # 스트리밍 중단 시 부분 응답 보존을 위해 세션에 저장
                    st.session_state.partial_response = full_response
                    message_placeholder.markdown(full_response + "▌")
                
                # --- 도구 시작: 스피너 + 검색 쿼리 표시 ---
                elif chunk["type"] == "tool_start":
                    thinking_placeholder.empty()  # 이전 "생각 중..." 제거
                    tool_name = chunk["name"]
                    tool_input = chunk.get("input", "")
                    current_tool_status = st.status(
                        f"🔄 **{tool_name}** 도구 사용 중...", expanded=True
                    )
                    current_tool_status.write(f"🔍 입력 및 셀렉터 인자: `{tool_input}`")
                
                # --- 도구 완료: 스피너 → ✅ 체크 전환 + "생각 중..." 표시 ---
                elif chunk["type"] == "tool_end":
                    if current_tool_status:
                        current_tool_status.update(
                            label=f"✅ **{chunk['name']}** 실행 완료", 
                            state="complete", 
                            expanded=False
                        )
                        current_tool_status = None
                    # 도구 완료 후 다음 토큰이 도착하기까지의 대기 상태 표시
                    thinking_placeholder.markdown("다음 동작 구상 중...")
                
                # --- 에러 ---
                elif chunk["type"] == "error":
                    st.error(f"Error: {chunk.get('content')}")
        
        # B. 스트리밍 완료 후 최종 렌더링
        thinking_placeholder.empty()   # 남아있을 수 있는 "생각 중..." 제거
        message_placeholder.empty()    # 스트리밍용 텍스트 제거 (Raw 상태)
        render_message_content(full_response)  # 이미지 태그 파싱 포함 최종 렌더링
        
        # Add Assistant Message to History
        st.session_state.messages.append({"role": "assistant", "content": full_response})
        st.session_state.partial_response = None  # 정상 완료 시 부분 응답 버퍼 클리어
    
    # 응답 생성 완료 — 입력 다시 활성화
    st.session_state.generating = False
    st.rerun()
