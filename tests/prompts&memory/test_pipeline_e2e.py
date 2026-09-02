"""
Progressive Keyword Pipeline 실전 검증 스크립트
- LLM을 실제로 호출하여 키워드 추출 품질을 검증합니다.
- 3개 세션을 생성하고, 엣지 케이스 검색 시나리오를 실행합니다.
"""
import os, sys, json, asyncio, tempfile
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from app.middleware.memory.episodic_store import EpisodicStore
from app.utils import init_chat_model

# ── LLM 초기화 ──
cfg_path = os.path.join(os.path.dirname(__file__), "..", "..", "configs", "model.config")
with open(cfg_path, "r", encoding="utf-8") as f:
    model_cfg = json.load(f)
llm = init_chat_model(model=model_cfg.get("model_name", "gemini-3.7-flash"), temperature=0.0)


# ── 테스트 대화 데이터셋 (3개 세션, 각각 다른 엣지 케이스) ──

# 세션 A: 핵심 결론("롤백 전략")이 대화 마지막에만 1회 등장
SESSION_A = [
    {"role": "human", "content": "데이터베이스 마이그레이션 전략을 논의합시다."},
    {"role": "ai", "content": "마이그레이션 시 다운타임을 최소화하려면 Blue-Green 배포가 좋습니다."},
    {"role": "human", "content": "스키마 변경이 실패하면 어떻게 하죠?"},
    {"role": "ai", "content": "Flyway의 undo 마이그레이션으로 즉시 롤백하고, 장애 시 Redis 캐시를 수동 무효화합니다."},
]

# 세션 B: 영어 기술어만 사용된 대화 (한국어 검색으로 찾을 수 있는지?)
SESSION_B = [
    {"role": "human", "content": "Let's discuss the API rate limiting strategy."},
    {"role": "ai", "content": "We should implement a token bucket algorithm with Redis as the backend store."},
    {"role": "human", "content": "What about the burst limit?"},
    {"role": "ai", "content": "Set burst to 100 requests per second with a sliding window counter for precise control."},
]

# 세션 C: 세션 A와 토픽이 겹치지만 결론이 다른 대화
SESSION_C = [
    {"role": "human", "content": "프로덕션 데이터베이스 백업 정책을 정합시다."},
    {"role": "ai", "content": "매일 자정 풀 백업, 4시간 간격으로 증분 백업을 실행합니다."},
    {"role": "human", "content": "백업 보관 기간은?"},
    {"role": "ai", "content": "풀 백업은 30일, 증분 백업은 7일 보관하며 S3 Glacier로 아카이빙합니다."},
]


async def run_test():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_pipeline.db")
        store = EpisodicStore(db_path=db_path)
        await store.setup()

        # ── 세션 저장 (LLM 사용 + LLM 미사용 각각) ──
        print("=" * 80)
        print("📦 [세션 저장 — LLM 사용]")
        print("=" * 80)

        sessions = [
            ("session_migration", SESSION_A, "DB 마이그레이션 (결론: 롤백+Redis 캐시)"),
            ("session_ratelimit", SESSION_B, "API Rate Limiting (영어 전용 대화)"),
            ("session_backup", SESSION_C, "DB 백업 정책 (세션A와 토픽 유사)"),
        ]

        for sid, msgs, desc in sessions:
            await store.finalize_session(sid, msgs, llm=llm)
            row = await store._conn.execute_fetchall(
                "SELECT summary, keywords FROM sessions WHERE session_id = ?", (sid,)
            )
            summary, keywords = row[0]
            kw_list = json.loads(keywords)
            print(f"\n🏷️ [{desc}] — {sid}")
            print(f"   Summary : {summary}")
            print(f"   Keywords: {kw_list}")

        # ── Fallback 비교용 세션 (llm=None) ──
        await store.finalize_session("session_migration_fallback", SESSION_A, llm=None)
        fb_row = await store._conn.execute_fetchall(
            "SELECT summary, keywords FROM sessions WHERE session_id = ?",
            ("session_migration_fallback",)
        )
        fb_summary, fb_keywords = fb_row[0]
        fb_kw_list = json.loads(fb_keywords)
        print(f"\n📁 [Fallback 비교] — session_migration_fallback")
        print(f"   Summary : {fb_summary}")
        print(f"   Keywords: {fb_kw_list}")

        # ── 검색 시나리오 ──
        test_cases = [
            # (검색어, 찾아야 할 세션, 설명)
            ("롤백", ["session_migration"], 
             "대화 마지막에 1회만 등장하는 핵심 결론 단어"),
            ("Redis", ["session_migration", "session_ratelimit"], 
             "두 세션 모두에 Redis가 등장 — 둘 다 찾는지?"),
            ("캐시", ["session_migration"], 
             "'캐시'가 원문에 직접 등장 — 로컬 추출로 찾는지?"),
            ("rate limiting", ["session_ratelimit"], 
             "영어 전용 세션을 영어로 검색"),
            ("백업", ["session_backup"], 
             "유사 토픽(DB) 중 백업 세션만 정확히 구분"),
            ("Glacier", ["session_backup"], 
             "대화 마지막 1회 등장하는 AWS 서비스명"),
            ("Flyway", ["session_migration"],
             "대화 마지막 1회 등장하는 도구명"),
        ]

        print("\n\n" + "=" * 80)
        print("🔍 [검색 시나리오 실행 — 7가지 엣지 케이스]")
        print("=" * 80)

        passed = 0
        failed = 0
        for query, expected_sids, desc in test_cases:
            results = await store.search_sessions(query, top_k=5)
            found_sids = [r["session_id"] for r in results]

            # 기대 세션이 모두 검색 결과에 있는지
            hits = [s for s in expected_sids if s in found_sids]
            misses = [s for s in expected_sids if s not in found_sids]

            if len(misses) == 0:
                print(f"\n  ✅ 검색어: '{query}' — {desc}")
                print(f"     기대: {expected_sids} → 결과: {found_sids}")
                passed += 1
            else:
                print(f"\n  ❌ 검색어: '{query}' — {desc}")
                print(f"     기대: {expected_sids} → 결과: {found_sids}")
                print(f"     누락된 세션: {misses}")
                failed += 1

        print("\n" + "=" * 80)
        total = passed + failed
        if failed == 0:
            print(f"🎉 전체 {total}/{total} 통과! Progressive Keyword Pipeline 실전 검증 완료!")
        else:
            print(f"⚠️ {passed}/{total} 통과, {failed}개 실패")
        print("=" * 80)

        await store.close()


if __name__ == "__main__":
    asyncio.run(run_test())
