"""
tests/test_compaction.py

🎯 Compaction 미들웨어 검증 (ToolResultSwapMiddleware + HarnessSummarizationMiddleware)
[오프라인 — 가짜 모델, 항상 실행]
1. 큰 도구 결과 swap: 미리보기·파일 저장, 작은 결과·file_read·비텍스트 결과는 그대로, 재실행 시 같은 파일
2. 요약: trigger 미만이면 그대로, 초과하면 [요약 + 최근 메시지]로 교체, 요약 메시지는 사용자 턴이 아님
3. 요약 LLM에 오래된 메시지(첫 요청)까지 전달됨 (trim_tokens_to_summarize=None)
4. 요약 실패 시 에러가 올라오고 대화를 가짜 요약으로 덮지 않음
5. transcript_store에 kind=compaction 이벤트 기록
6. create_agent E2E: swap → file_read로 부분 조회(재swap 없음) → 요약 → AI/Tool 쌍 무결성 → 요약 토큰 스트림 제외
[라이브 — --live 옵션, gemini-3.8-flash]
7. 실제 모델로 swap된 파일 부분 조회 + 요약 후에도 이전 턴 사실을 기억하는지

실행 방법:
  python tests/test_compaction.py          # 오프라인만
  python tests/test_compaction.py --live   # 라이브 포함
"""

import asyncio
import os
import shutil
import sys
import tempfile

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.chdir(project_root)

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, ToolMessage
from langchain_core.tools import tool

from app.middleware.compaction import (
    HarnessSummarizationMiddleware,
    ToolResultSwapMiddleware,
    create_compaction_middleware,
)
from app.middleware.compaction.tool_result_swap import PERSISTED_OUTPUT_TAG
from app.utils.message_markers import is_compaction_summary, is_user_turn_start, user_turn_starts


class ToolCallingFake(GenericFakeChatModel):
    """정해진 AIMessage를 순서대로 돌려주는 가짜 모델 (create_agent가 bind_tools를 호출하므로 추가)."""

    def bind_tools(self, tools, **kwargs):
        return self


class RecordingFake(GenericFakeChatModel):
    """받은 프롬프트를 기록하는 요약용 가짜 모델."""
    prompts: list = []

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.prompts.append("\n".join(str(m.content) for m in messages))
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


class FailingFake(GenericFakeChatModel):
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        raise RuntimeError("summary backend down")


class FakeTranscript:
    def __init__(self):
        self.calls = []

    def record_compaction(self, **kwargs):
        self.calls.append(kwargs)


class FakeRuntime:
    def __init__(self, session_id):
        self.context = type("Ctx", (), {"session_id": session_id, "user_id": "u1"})()
        self.config = {}


BIG_TEXT = "\n".join(f"row {i:05d} | value={i * 7}" for i in range(2000))   # 약 50,000자


def tc(name, args, call_id):
    return {"name": name, "args": args, "id": call_id, "type": "tool_call"}


def history(n_turns, chars=600):
    msgs = [HumanMessage("FIRST_REQUEST: build the quarterly report", id="h0"),
            AIMessage("ack " + "a" * chars, id="a0")]
    for t in range(1, n_turns):
        msgs += [
            HumanMessage(f"turn {t} question " + "q" * chars, id=f"h{t}"),
            AIMessage("", tool_calls=[tc("grep_search", {"pattern": "x"}, f"c{t}")], id=f"ai{t}"),
            ToolMessage("r" * chars, tool_call_id=f"c{t}", name="grep_search", id=f"t{t}"),
            AIMessage(f"answer {t} " + "b" * chars, id=f"a{t}"),
        ]
    return msgs


def check(cond, label):
    if not cond:
        raise AssertionError(label)
    print(f"  ✅ {label}")


# -----------------------------------------------------------------------------
# 1. Tool Result Swap
# -----------------------------------------------------------------------------
def test_swap(tmp):
    print("\n[1] ToolResultSwapMiddleware")
    mw = ToolResultSwapMiddleware(swap_dir=tmp, max_result_chars=10_000)
    big = ToolMessage(BIG_TEXT, tool_call_id="call_big", name="web_fetch", id="m1")
    out = mw.swap_if_large(big)
    check(out.content.startswith(PERSISTED_OUTPUT_TAG), "큰 결과는 <persisted-output> 미리보기로 바뀜")
    check(len(out.content) < 2_600, f"미리보기 크기 제한 ({len(out.content)}자)")
    check(out.id == "m1" and out.tool_call_id == "call_big", "메시지 id·tool_call_id 유지")
    path = os.path.join(os.path.abspath(tmp), "default", "call_big.txt")
    check(path in out.content and open(path, encoding="utf-8").read() == BIG_TEXT, "원문 전체가 파일에 저장되고 경로가 안내됨")
    check(mw.swap_if_large(big).content == out.content, "같은 결과를 다시 처리해도 같은 파일·같은 미리보기")
    check(mw.swap_if_large(out) is out, "이미 swap된 메시지는 건드리지 않음")
    small = ToolMessage("ok", tool_call_id="c2", name="web_fetch")
    check(mw.swap_if_large(small) is small, "작은 결과는 그대로")
    fr = ToolMessage(BIG_TEXT, tool_call_id="c3", name="file_read")
    check(mw.swap_if_large(fr) is fr, "file_read 결과는 swap하지 않음 (재swap 순환 방지)")
    blocks = ToolMessage([{"type": "text", "text": BIG_TEXT}], tool_call_id="c4", name="web_fetch")
    check(mw.swap_if_large(blocks) is blocks, "텍스트가 아닌(블록 리스트) 결과는 그대로")

    from app.utils.workspace import USERS_ROOT_DIR
    ws_mw = ToolResultSwapMiddleware()   # swap_dir 미지정 → 유저·세션 워크스페이스
    runtime = type("RT", (), {"context": type("Ctx", (), {"user_id": "pytest_swap_user", "parent_session_id": ""})()})()
    try:
        out = ws_mw.swap_if_large(ToolMessage(BIG_TEXT, tool_call_id="call_ws", name="web_fetch"), runtime=runtime)
        expected = USERS_ROOT_DIR / "pytest_swap_user" / "sessions" / "default" / "tool-results" / "call_ws.txt"
        check(str(expected) in out.content and expected.exists(),
              "swap_dir 미지정 시 artifacts/users/{user_id}/sessions/{session_id}/tool-results/에 저장")
    finally:
        shutil.rmtree(USERS_ROOT_DIR / "pytest_swap_user", ignore_errors=True)


# -----------------------------------------------------------------------------
# 2~5. Summarization
# -----------------------------------------------------------------------------
def test_summarization():
    print("\n[2] HarnessSummarizationMiddleware — trigger")
    summ_llm = RecordingFake(messages=iter([AIMessage("SUMMARY: user wants quarterly report") for _ in range(5)]))
    store = FakeTranscript()
    mw = HarnessSummarizationMiddleware(summ_llm, trigger=("tokens", 2000), keep=("tokens", 800),
                                        trim_tokens_to_summarize=None, transcript_store=store)

    short = history(2)
    check(mw.before_model({"messages": short}, FakeRuntime("s1")) is None, "trigger 미만이면 아무것도 하지 않음")

    long = history(8)
    update = mw.before_model({"messages": long}, FakeRuntime("s1"))
    check(update is not None, "trigger 초과 시 state 교체")
    new = update["messages"]
    check(isinstance(new[0], RemoveMessage), "첫 항목은 RemoveMessage(REMOVE_ALL_MESSAGES)")
    summary, kept = new[1], new[2:]
    check(is_compaction_summary(summary) and not is_user_turn_start(summary), "요약 메시지는 하네스 산출물 (사용자 턴 아님)")
    check("SUMMARY: user wants quarterly report" in summary.content, "요약 본문 주입")
    check(0 < len(kept) < len(long) - 1, f"최근 메시지만 원문 유지 ({len(long)} → 요약 1 + {len(kept)})")
    check(not isinstance(kept[0], ToolMessage), "남은 구간이 ToolMessage로 시작하지 않음 (AI/Tool 쌍 보존)")
    kept_call_ids = {c["id"] for m in kept if isinstance(m, AIMessage) for c in m.tool_calls}
    check(all(m.tool_call_id in kept_call_ids for m in kept if isinstance(m, ToolMessage)), "남은 ToolMessage는 모두 짝 AIMessage가 있음")
    turns_before = len(user_turn_starts(long))
    check(len(user_turn_starts([summary] + kept)) < turns_before, "요약이 사용자 턴 수를 늘리지 않음")

    print("\n[3] 요약 LLM 입력")
    check("FIRST_REQUEST" in summ_llm.prompts[-1], "가장 오래된 첫 요청까지 요약 LLM에 전달됨")

    custom_llm = RecordingFake(messages=iter([AIMessage("요약") for _ in range(3)]))
    custom_mw = create_compaction_middleware(custom_llm, trigger_tokens=2000, keep_tokens=800,
                                             summary_prompt="CUSTOM_PROMPT 한국어로 요약\n<messages>\n{messages}\n</messages>")[1]
    custom_mw.before_model({"messages": history(8)}, None)
    check(custom_llm.prompts[-1].startswith("CUSTOM_PROMPT") and "FIRST_REQUEST" in custom_llm.prompts[-1],
          "summary_prompt로 요약 지시문 교체 ({messages} 자리에 대화가 들어감)")

    print("\n[5] transcript 기록")
    check(len(store.calls) == 1 and store.calls[0]["session_id"] == "s1", "record_compaction 1회 호출")
    rec = store.calls[0]
    check("h0" in rec["compacted_uids"] and not set(rec["compacted_uids"]) & {m.id for m in kept},
          "compacted_uids = 요약된 메시지 id (남은 메시지 제외)")

    print("\n[4] 요약 실패")
    bad = HarnessSummarizationMiddleware(FailingFake(messages=iter([])), trigger=("tokens", 2000),
                                         keep=("tokens", 800), trim_tokens_to_summarize=None)
    try:
        bad.before_model({"messages": history(8)}, None)
        raise AssertionError("요약 실패 시 예외가 올라와야 함")
    except RuntimeError as e:
        check("summary backend down" in str(e), "재시도 후 에러를 그대로 올림 (가짜 요약으로 대화를 덮지 않음)")


# -----------------------------------------------------------------------------
# 6. create_agent E2E (가짜 모델)
# -----------------------------------------------------------------------------
async def test_agent_e2e(tmp):
    print("\n[6] create_agent E2E")
    from langchain.agents import create_agent
    from langgraph.checkpoint.memory import InMemorySaver
    from app.tools.common import file_read

    @tool
    def fetch_report(name: str) -> str:
        """Fetch a large report by name."""
        return BIG_TEXT

    thread = "e2e-thread"
    swap_path = os.path.join(os.path.abspath(tmp), thread, "call_fetch.txt")
    main_llm = ToolCallingFake(messages=iter([
        AIMessage("", tool_calls=[tc("fetch_report", {"name": "q3"}, "call_fetch")]),
        AIMessage("Fetched the report. " + "x" * 400),
        AIMessage("", tool_calls=[tc("file_read", {"file_path": swap_path, "offset": 100, "limit": 5}, "call_read")]),
        AIMessage("Row 99 has value 693. " + "y" * 400),
        AIMessage("FINAL_ANSWER done"),
    ]))
    summ_llm = ToolCallingFake(messages=iter([AIMessage("SUMMARY TOKENS SHOULD NOT STREAM") for _ in range(5)]))
    agent = create_agent(
        model=main_llm,
        tools=[fetch_report, file_read],
        middleware=create_compaction_middleware(main_llm, trigger_tokens=1200, keep_tokens=200,
                                                swap_dir=tmp, summary_llm=summ_llm),
        checkpointer=InMemorySaver(),
    )
    cfg = {"configurable": {"thread_id": thread}}

    await agent.ainvoke({"messages": [HumanMessage("Get the q3 report " + "p" * 1500)]}, cfg)
    msgs = (await agent.aget_state(cfg)).values["messages"]
    fetched = next(m for m in msgs if isinstance(m, ToolMessage) and m.tool_call_id == "call_fetch")
    check(fetched.content.startswith(PERSISTED_OUTPUT_TAG), "state의 ToolMessage가 처음부터 미리보기로 저장됨")
    check(os.path.exists(swap_path), "세션(thread_id)별 폴더에 원문 저장")

    await agent.ainvoke({"messages": [HumanMessage("What is in row 99?")]}, cfg)
    msgs = (await agent.aget_state(cfg)).values["messages"]
    read = next((m for m in msgs if isinstance(m, ToolMessage) and m.tool_call_id == "call_read"), None)
    check(read is not None and "row 00099" in read.content and PERSISTED_OUTPUT_TAG not in read.content,
          "file_read로 swap 파일 부분 조회 (재swap 없음)")
    check(any(is_compaction_summary(m) for m in msgs), "누적 토큰이 trigger를 넘어 요약 발생")

    streamed, hidden = [], []
    # 이 턴 입력만으로 trigger(1200토큰 ≈ 4,800자)를 넘겨 스트리밍 중에 요약이 일어나게 합니다.
    async for ev in agent.astream_events({"messages": [HumanMessage("Wrap up. " + "w" * 6000)]}, cfg, version="v2"):
        if ev["event"] == "on_chat_model_stream":
            bucket = hidden if "exclude_from_stream" in ev.get("tags", []) else streamed
            bucket.append(str(ev["data"]["chunk"].content))
    text, hidden_text = "".join(streamed), "".join(hidden)
    check("SUMMARY TOKENS" in hidden_text, "요약 호출의 스트림 이벤트에 exclude_from_stream 태그가 붙음")
    check("FINAL_ANSWER" in text and "SUMMARY TOKENS" not in text, "서버 필터 기준으로 요약 토큰은 스트림에서 제외")

    msgs = (await agent.aget_state(cfg)).values["messages"]
    call_ids = {c["id"] for m in msgs if isinstance(m, AIMessage) for c in m.tool_calls}
    check(all(m.tool_call_id in call_ids for m in msgs if isinstance(m, ToolMessage)), "최종 state에 짝 잃은 ToolMessage 없음")
    check(sum(is_compaction_summary(m) for m in msgs) == 1, "요약 메시지는 항상 1개 (이전 요약은 새 요약에 흡수)")


# -----------------------------------------------------------------------------
# 7. 라이브
# -----------------------------------------------------------------------------
async def test_live(tmp):
    print("\n[7] 라이브 (gemini-3.8-flash)")
    from dotenv import load_dotenv
    load_dotenv(os.path.join(project_root, ".env"))
    from langchain.agents import create_agent
    from langgraph.checkpoint.memory import InMemorySaver
    from app.tools.common import file_read, grep_search
    from app.utils.langchain_wrapper import init_chat_model

    @tool
    def fetch_report(name: str) -> str:
        """Fetch the full sales report table by name. Returns a very large text table."""
        return BIG_TEXT

    llm = init_chat_model(model="gemini-3.8-flash", temperature=0.0)
    agent = create_agent(
        model=llm,
        tools=[fetch_report, file_read, grep_search],
        system_prompt="You are a data assistant. Use tools to answer. Be brief.",
        middleware=create_compaction_middleware(llm, trigger_tokens=1200, keep_tokens=300, swap_dir=tmp),
        checkpointer=InMemorySaver(),
    )
    cfg = {"configurable": {"thread_id": "live-thread"}}

    r1 = await agent.ainvoke({"messages": [HumanMessage(
        "My project codename is BLUE-HERON. Remember it. Then fetch the 'q3' report and tell me the value in row 01234.")]}, cfg)
    ans1 = r1["messages"][-1].text
    print(f"     answer1: {ans1[:160]!r}")
    tools_used = [m.name for m in r1["messages"] if isinstance(m, ToolMessage)]
    print(f"     tools used: {tools_used}")
    check("8638" in ans1, "swap된 결과에서 file_read/grep_search로 row 01234 값(8638)을 찾음")

    for q in ["Briefly explain what a quarterly report is, in about 150 words.",
              "Now explain what a sales pipeline is, in about 150 words."]:
        await agent.ainvoke({"messages": [HumanMessage(q)]}, cfg)
    msgs = (await agent.aget_state(cfg)).values["messages"]
    check(any(is_compaction_summary(m) for m in msgs), "여러 턴 후 요약 발생")

    r = await agent.ainvoke({"messages": [HumanMessage("What is my project codename and the row 01234 value? Answer from memory, no tools.")]}, cfg)
    ans = r["messages"][-1].text
    print(f"     answer: {ans[:160]!r}")
    check("BLUE-HERON" in ans.upper() and "8638" in ans, "요약 이후에도 첫 턴의 사실을 기억")


async def main():
    tmp = tempfile.mkdtemp(prefix="compaction_test_")
    try:
        test_swap(os.path.join(tmp, "unit"))
        test_summarization()
        await test_agent_e2e(os.path.join(tmp, "e2e"))
        if "--live" in sys.argv:
            await test_live(os.path.join(tmp, "live"))
        print("\n🎉 모든 Compaction 테스트 통과")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
