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

# --- Premium Custom CSS Styling (Glassmorphism, Dark Mode Theme) ---
st.markdown("""
<style>
    /* Main background */
    .stApp {
        background-color: #0e1117;
        color: #ffffff;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #161b22;
        border-right: 1px solid #30363d;
    }
    
    /* Custom header cards */
    .header-card {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 20px;
        backdrop-filter: blur(10px);
    }
    
    /* Status indicators */
    .status-text {
        font-size: 0.85em;
        color: #8b949e;
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
                if st.button(f"{prefix}{s['title']}", key=f"session_{s['session_id']}", use_container_width=True):
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
