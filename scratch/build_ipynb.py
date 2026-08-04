import json

cells = [
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "# (4) Human in the Loop\n",
            "\n",
            "이 단원에서는 에이전트의 도구 실행 직전 사람의 개입 및 승인 단계를 거치는 **Human-in-the-loop (HITL)** 설계 기법을 배웁니다.\n",
            "\n",
            "공식 문서: [LangChain Human-in-the-Loop 가이드](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)"
        ]
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "import os\n",
            "import sys\n",
            "from dotenv import load_dotenv\n",
            "\n",
            "# 1. 환경 변수 로드 (.env 설정 수혈)\n",
            "load_dotenv(\"../.env\")\n",
            "\n",
            "# 2. 프로젝트 루트 경로 추가 (상위 디렉토리의 app 패키지 임포트 보장)\n",
            "sys.path.append(\"..\")\n",
            "\n",
            "# 3. 파일 쓰기용 샌드박스 디렉토리 선제 생성\n",
            "os.makedirs(\"./sandbox\", exist_ok=True)\n",
            "print(\"✅ 환경 변수 로드, 프로젝트 경로 추가 및 ./sandbox 디렉토리 셋업이 완료되었습니다.\")"
        ]
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "from langchain.agents import create_agent\n",
            "from langchain.agents.middleware import HumanInTheLoopMiddleware\n",
            "from langgraph.checkpoint.memory import InMemorySaver\n",
            "from app.tools import web_search, file_read, file_writer  # 🏭 우리의 챗봇 범용 3대 무기 임포트!\n",
            "\n",
            "# (A) 자체 제작 파일 도구 셋업\n",
            "file_tools = [file_read, file_writer]\n",
            "\n",
            "# (B) 자체 웹 검색 도구 매핑\n",
            "tavily_tool = web_search\n",
            "\n",
            "print(\"Search tool name:\", tavily_tool.name)\n",
            "print(\"File tool names :\", [t.name for t in file_tools])"
        ]
    },
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "### Human-in-the-loop 정책 설정 (강의용)\n",
            "\n",
            "| 설정값 | 인터럽트 | approve | edit | reject |\n",
            "| :--- | :--- | :--- | :--- | :--- |\n",
            "| `False` | ❌ 없음 | 자동 실행 | 자동 실행 | 자동 실행 |\n",
            "| `True` | ✅ 있음 | 가능 | 가능 | 가능 |\n",
            "| `{\"allowed_decisions\": [\"approve\", \"reject\"]}` | ✅ 있음 | 가능 | ❌ 불가 | 가능 |"
        ]
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# -------------------------------------------------\n",
            "# Human-in-the-loop 정책 설정 (자체 제작 도구 타겟)\n",
            "# -------------------------------------------------\n",
            "hitl = HumanInTheLoopMiddleware(\n",
            "    interrupt_on={\n",
            "        # 검색은 사람이 검토 + 수정 가능\n",
            "        tavily_tool.name: True,\n",
            "\n",
            "        # 파일 쓰기는 승인/거절만 가능 (edit 금지)\n",
            "        \"file_writer\": {\n",
            "            \"allowed_decisions\": [\"approve\", \"reject\"]\n",
            "        },\n",
            "\n",
            "        # 파일 읽기는 안전하므로 자동 실행\n",
            "        \"file_read\": False,\n",
            "    },\n",
            "    description_prefix=\"🛑 Tool execution pending human review\",\n",
            ")\n",
            "\n",
            "# Vertex AI 오탐지 방지 및 명확한 OpenAI 기동을 위해 openai:gpt-4o를 지정합니다.\n",
            "agent = create_agent(\n",
            "    model=\"openai:gpt-4o\",\n",
            "    tools=[tavily_tool] + file_tools,\n",
            "    middleware=[hitl],\n",
            "    checkpointer=InMemorySaver(),\n",
            ")\n",
            "print(\"🤖 자체 제작 10종 범용 툴 기반의 HITL 에이전트 컴파일 완료.\")"
        ]
    },
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "### 1단계: 검색 도구 호출 직전 인터럽트(Interrupt) 발생 검증"
        ]
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "config = {\"configurable\": {\"thread_id\": \"hitl_demo_1\"}}\n",
            "\n",
            "result = agent.invoke(\n",
            "    {\n",
            "        \"messages\": [\n",
            "            {\n",
            "                \"role\": \"user\",\n                \"content\": \"트럼프 관세에 대해 최신 업데이트 사항을 찾아봐\"\n            }\n",
            "        ]\n",
            "    },\n",
            "    config=config\n",
            ")\n",
            "\n",
            "# ✅ 여기서 멈추면 __interrupt__가 생깁니다.\n",
            "print(\"HAS_INTERRUPT =\", \"__interrupt__\" in result)"
        ]
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# 사람이 리뷰해야 할 액션(툴 호출 요청) 확인\n",
            "interrupts = result.get(\"__interrupt__\", [])\n",
            "print(\"HAS_INTERRUPT =\", bool(interrupts))\n",
            "\n",
            "if interrupts:\n",
            "    req = interrupts[0].value\n",
            "\n",
            "    print(\"\\n=== ACTION REQUESTS ===\")\n",
            "    for i, ar in enumerate(req.get(\"action_requests\", [])):\n",
            "        tool_name = ar.get(\"name\")\n",
            "        tool_args = ar.get(\"args\", ar.get(\"arguments\"))  # ✅ args 우선, 없으면 arguments\n",
            "        desc = ar.get(\"description\")\n",
            "\n",
            "        print(f\"\\n[#{i}] tool =\", tool_name)\n",
            "        print(\"args =\", tool_args)\n",
            "        print(\"desc =\", desc)\n",
            "\n",
            "    print(\"\\n=== REVIEW CONFIGS ===\")\n",
            "    print(req.get(\"review_configs\"))"
        ]
    },
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "### 2단계: 승인 (APPROVE)\n",
            "\n",
            "사람이 승인 의사결정을 전달하여 에이전트를 재기동(Resume)시킵니다."
        ]
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "from langgraph.types import Command\n",
            "\n",
            "result2 = agent.invoke(\n",
            "    Command(resume={\"decisions\": [{\"type\": \"approve\"}]}),\n",
            "    config=config\n",
            ")\n",
            "\n",
            "# 최종 assistant 메시지 출력\n",
            "msgs = result2.get(\"messages\", [])\n",
            "print(msgs[-1].content if msgs else \"(no messages)\")"
        ]
    },
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "### 3단계: 수정 및 실행 (EDIT)\n",
            "\n",
            "사람이 에이전트가 올린 도구 인자값을 직접 교정해서 실행을 위임합니다."
        ]
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "config = {\"configurable\": {\"thread_id\": \"hitl_demo_2\"}}\n",
            "\n",
            "result3 = agent.invoke(\n",
            "    {\n",
            "        \"messages\": [\n",
            "            {\n",
            "                \"role\": \"user\",\n                \"content\": \"트럼프 관세에 대해 최신 업데이트 사항을 찾아봐\"\n            }\n",
            "        ]\n",
            "    },\n",
            "    config=config\n",
            ")\n",
            "print(\"HAS_INTERRUPT =\", \"__interrupt__\" in result3)"
        ]
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "result4 = agent.invoke(\n",
            "    Command(\n",
            "        resume={\n",
            "            \"decisions\": [\n",
            "                {\n",
            "                    \"type\": \"edit\",\n",
            "                    \"edited_action\": {\n",
            "                        \"name\": \"web_search\",\n                        \"args\": {\n",
            "                            \"query\": \"트럼프 관세 최신 업데이트 일본 반응\"\n",
            "                        },\n",
            "                    },\n",
            "                }\n",
            "            ]\n",
            "        }\n",
            "    ),\n",
            "    config=config\n",
            ")\n",
            "\n",
            "msgs = result4.get(\"messages\", [])\n",
            "print(msgs[-1].content if msgs else \"(no messages)\")"
        ]
    },
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "### 4단계: 거절 (REJECT)\n",
            "\n",
            "파일 쓰기 작업(`file_writer`)을 강제로 거절하여 보안 차단 피드백을 전달합니다."
        ]
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "from langgraph.types import Command\n",
            "\n",
            "config = {\"configurable\": {\"thread_id\": \"hitl_write_reject_demo_1\"}}\n",
            "\n",
            "result = agent.invoke(\n",
            "    {\n",
            "        \"messages\": [\n",
            "            {\n",
            "                \"role\": \"user\",\n                \"content\": (\n",
            "                    \"아래 내용을 './sandbox/memo.txt' 파일로 저장해줘.\\n\\n\"\n",
            "                    \"- HITL은 tool 실행 전에 멈춘다\\n\"\n",
            "                    \"- approve/edit/reject로 사람이 개입한다\\n\"\n",
            "                )\n",
            "            }\n",
            "        ]\n",
            "    },\n",
            "    config=config\n",
            ")\n",
            "\n",
            "print(\"HAS_INTERRUPT =\", \"__interrupt__\" in result)\n",
            "print(result.get(\"__interrupt__\"))"
        ]
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# (교육용) 어떤 tool call이 멈췄는지 보기\n",
            "if \"__interrupt__\" in result:\n",
            "    req = result[\"__interrupt__\"][0].value\n",
            "    ar = req[\"action_requests\"][0]\n",
            "    print(\"\\nTool =\", ar.get(\"name\"))\n",
            "    print(\"Args =\", ar.get(\"args\", ar.get(\"arguments\")))\n",
            "    print(\"Allowed =\", req[\"review_configs\"][0].get(\"allowed_decisions\"))"
        ]
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "result2 = agent.invoke(\n",
            "    Command(\n",
            "        resume={\n",
            "            \"decisions\": [\n",
            "                {\n",
            "                    \"type\": \"reject\",\n",
            "                    \"message\": (\n",
            "                        \"파일 쓰기 작업은 승인되지 않았습니다. (실습 목적상 file_writer 거절)\\n\"\n",
            "                        \"대신, 내용을 채팅으로만 출력하고 저장이 필요하면 사용자에게 승인(approve)을 요청하세요.\"\n",
            "                    )\n",
            "                }\n",
            "            ]\n",
            "        }\n",
            "    ),\n",
            "    config=config\n",
            ")\n",
            "\n",
            "msgs = result2.get(\"messages\", [])\n",
            "print(msgs[-1].content if msgs else \"(no messages)\")"
        ]
    }
]

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "name": "python"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 2
}

with open("notebooks/04_human_in_the_loop.ipynb", "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=2, ensure_ascii=False)
print("[*] Successfully built notebooks/04_human_in_the_loop.ipynb with local file_read/file_writer integration.")
