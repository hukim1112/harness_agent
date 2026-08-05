import sys
import os
import re
import uuid
import streamlit as st

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.client import AgentClient
from app.agents import AGENT_REGISTRY

# --- Page Config ---
st.set_page_config(page_title="Harness Agent UI", layout="wide")

# --- Premium Custom CSS Styling (Modern Electric Blue Theme & Glassmorphism) ---
st.markdown("""
<style>
    /* Main background with deep blue-space gradient */
    .stApp {
        background: linear-gradient(135deg, #060b16 0%, #0a1224 50%, #060b16 100%);
        color: #e2e8f0;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Sidebar premium styling */
    section[data-testid="stSidebar"] {
        background-color: #03070f !important;
        border-right: 1px solid #1e3a8a !important;
    }
    
    /* Premium Header and info cards */
    .header-card {
        background: linear-gradient(135deg, rgba(30, 58, 138, 0.25) 0%, rgba(59, 130, 246, 0.1) 100%);
        border: 1px solid rgba(59, 130, 246, 0.3);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 25px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
    }
    
    .header-card h2 {
        color: #3b82f6 !important;
        font-weight: 700;
        margin-top: 0;
    }
    
    .header-card code {
        background: rgba(59, 130, 246, 0.2);
        color: #93c5fd;
        border: 1px solid rgba(59, 130, 246, 0.3);
        padding: 2px 6px;
        border-radius: 4px;
    }
    
    .status-text {
        font-size: 0.9em;
        color: #94a3b8;
    }
    
    /* Premium button stylings */
    div.stButton > button {
        background: linear-gradient(135deg, #1d4ed8 0%, #2563eb 100%) !important;
        color: #ffffff !important;
        border: 1px solid rgba(59, 130, 246, 0.4) !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 12px rgba(29, 78, 216, 0.15) !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    
    div.stButton > button:hover {
        background: linear-gradient(135deg, #2563eb 0%, #3b82f6 100%) !important;
        border-color: #60a5fa !important;
        box-shadow: 0 6px 20px rgba(59, 130, 246, 0.3) !important;
        transform: translateY(-1px) !important;
    }
    
    /* Secondary (Inactive) room list buttons styling */
    div.stButton > button[kind="secondary"] {
        background: rgba(15, 23, 42, 0.6) !important;
        color: #94a3b8 !important;
        border: 1px solid rgba(148, 163, 184, 0.15) !important;
        box-shadow: none !important;
    }
    
    div.stButton > button[kind="secondary"]:hover {
        background: rgba(30, 41, 59, 0.8) !important;
        color: #ffffff !important;
        border-color: rgba(148, 163, 184, 0.4) !important;
    }
</style>
""", unsafe_allow_html=True)

# --- Initialize Client ---
@st.cache_resource
def get_client():
    return AgentClient(base_url="http://localhost:8000")

client = get_client()

# --- Agent Options ---
agent_options = {a["name"]: a["description"] for a in AGENT_REGISTRY}

# --- Helpers ---
def render_message_content(content):
    """
    텍스트 내의 <Render_Image> 태그를 파싱하여
    텍스트와 이미지를 순서대로 렌더링합니다.
    """
    pattern = re.compile(r"<Render_Image>(.*?)</Render_Image>")
    parts = pattern.split(content)
    
    for i, part in enumerate(parts):
        if i % 2 == 0:
            if part.strip():
                st.markdown(part)
        else:
            image_path = part.strip()
            if os.path.exists(image_path):
                st.image(image_path, caption=os.path.basename(image_path))
            else:
                st.error(f"Image not found: {image_path}")

# --- Initialize Session State ---
if "thread_id" not in st.session_state:
    st.session_state.thread_id = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "generating" not in st.session_state:
    st.session_state.generating = False

if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None

if "partial_response" not in st.session_state:
    st.session_state.partial_response = None


# --- Sidebar: Room & Agent Management ---
with st.sidebar:
    st.title("🤖 Harness Agent Lab")
    st.markdown("---")
    
    # 1. Agent Selection
    st.markdown("### 💼 에이전트 선택")
    agent_name = st.selectbox(
        "Select Agent",
        list(agent_options.keys()),
        format_func=lambda x: f"{x.upper()} - {agent_options[x]}",
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    
    # 2. Chat Rooms List
    st.markdown("### 💬 대화방 목록")
    
    # Fetch active sessions for the selected agent
    with st.spinner("🔄 에이전트 및 대화 목록 로드 중..."):
        sessions = client.get_sessions(agent_name=agent_name)
    session_ids = [s["session_id"] for s in sessions]
    
    # If current thread_id is invalid or not selected, select the latest one
    if st.session_state.thread_id not in session_ids:
        if session_ids:
            st.session_state.thread_id = session_ids[0]
            # Load messages
            db_msgs = client.get_messages(session_ids[0])
            st.session_state.messages = [{"role": m["role"], "content": m["content"]} for m in db_msgs]
        else:
            st.session_state.thread_id = None
            st.session_state.messages = []

    # New Chat input / button
    new_title = st.text_input("새 대화 제목", placeholder="대화 제목 입력...", label_visibility="collapsed")
    if st.button("➕ 새 대화방 개설", use_container_width=True):
        new_thread = str(uuid.uuid4())
        title = new_title.strip() if new_title.strip() else f"새 대화 - {len(sessions) + 1}"
        client.create_session(new_thread, agent_name, title)
        st.session_state.thread_id = new_thread
        st.session_state.messages = []
        st.session_state.generating = False
        st.session_state.pending_prompt = None
        st.session_state.partial_response = None
        st.rerun()
        
    st.markdown("---")
    
    # Render Chat Rooms
    if not sessions:
        st.caption("대화방이 없습니다. 새 대화를 만들어 보세요.")
    else:
        for s in sessions:
            col1, col2 = st.columns([5, 1])
            is_active = s["session_id"] == st.session_state.thread_id
            
            # Active room styling prefix
            prefix = "📌 " if is_active else "📄 "
            with col1:
                if st.button(f"{prefix}{s['title']}", key=f"session_{s['session_id']}", use_container_width=True, type="primary" if is_active else "secondary"):
                    st.session_state.thread_id = s["session_id"]
                    db_msgs = client.get_messages(s["session_id"])
                    st.session_state.messages = [{"role": m["role"], "content": m["content"]} for m in db_msgs]
                    st.session_state.generating = False
                    st.session_state.pending_prompt = None
                    st.session_state.partial_response = None
                    st.rerun()
            with col2:
                if st.button("🗑️", key=f"del_{s['session_id']}"):
                    client.delete_session(s["session_id"])
                    if st.session_state.thread_id == s["session_id"]:
                        st.session_state.thread_id = None
                        st.session_state.messages = []
                    st.rerun()
                    
    st.markdown("---")
    st.info("💡 **지연 안내**: 에이전트를 다른 종류로 처음 변경할 때는 라이브러리 임포트 및 LLM 바인딩으로 인해 1~2초간 지연이 발생할 수 있습니다. 정상 작동 중이오니 잠시만 기다려 주세요.")


# --- Main Chat Interface ---
# Top Header Card
st.markdown(f"""
<div class="header-card">
    <h2>Chat with <code>{agent_name.upper()}</code></h2>
    <p class="status-text">사용자와 상호작용하는 프로덕션 에이전트 및 하네스 모니터링 환경입니다.</p>
</div>
""", unsafe_allow_html=True)

# 1. Display Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        render_message_content(msg["content"])

# 2. Handle partial response save (stopped chat)
if st.session_state.partial_response is not None:
    partial = st.session_state.partial_response + "\n\n*(크롤링/실행이 사용자에 의해 중단되었습니다)*"
    st.session_state.messages.append({"role": "assistant", "content": partial})
    st.session_state.partial_response = None
    st.session_state.generating = False
    st.rerun()

# 3. Chat Input
# If thread_id is None, input is disabled unless they create a session, OR we auto-create one.
# Let's auto-create a session if thread_id is None!
input_disabled = st.session_state.generating

if prompt := st.chat_input("메시지를 입력하세요...", disabled=input_disabled):
    if st.session_state.thread_id is None:
        # Auto-create session
        new_thread = str(uuid.uuid4())
        title = prompt[:20] + "..." if len(prompt) > 20 else prompt
        client.create_session(new_thread, agent_name, title)
        st.session_state.thread_id = new_thread
        
    st.session_state.pending_prompt = prompt
    st.session_state.generating = True
    st.rerun()

# 4. Process Pending Prompt
if st.session_state.pending_prompt and st.session_state.generating:
    prompt = st.session_state.pending_prompt
    st.session_state.pending_prompt = None
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Agent Response (Streaming)
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        thinking_placeholder = st.empty()
        full_response = ""
        
        # Stop Button
        if st.button("⏹ 중단"):
            st.session_state.partial_response = full_response
            st.session_state.generating = False
            st.rerun()
            
        current_tool_status = None
        
        for chunk in client.stream(agent_name, prompt, st.session_state.thread_id):
            if "type" in chunk:
                if chunk["type"] == "token":
                    thinking_placeholder.empty()
                    content = chunk.get("content", "")
                    full_response += content
                    st.session_state.partial_response = full_response
                    message_placeholder.markdown(full_response + "▌")
                
                elif chunk["type"] == "tool_start":
                    thinking_placeholder.empty()
                    tool_name = chunk["name"]
                    tool_input = chunk.get("input", "")
                    current_tool_status = st.status(
                        f"🔄 **{tool_name}** 도구 실행 중...", expanded=True
                    )
                    current_tool_status.write(f"🔍 입력 인자: `{tool_input}`")
                
                elif chunk["type"] == "tool_end":
                    if current_tool_status:
                        current_tool_status.update(
                            label=f"✅ **{chunk['name']}** 실행 완료", 
                            state="complete", 
                            expanded=False
                        )
                        current_tool_status = None
                    thinking_placeholder.markdown("다음 동작 구상 중...")
                
                elif chunk["type"] == "error":
                    st.error(f"Error: {chunk.get('content') or chunk.get('error')}")
            elif "error" in chunk:
                st.error(f"Error: {chunk['error']}")
        
        # Final Render
        thinking_placeholder.empty()
        message_placeholder.empty()
        render_message_content(full_response)
        
        st.session_state.messages.append({"role": "assistant", "content": full_response})
        st.session_state.partial_response = None
    
    st.session_state.generating = False
    st.rerun()
