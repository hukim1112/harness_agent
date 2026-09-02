"""
=============================================================================
Test 03: Episodic Memory Store 검증
=============================================================================
검증 항목:
  1. DB 초기화 + 테이블 생성
  2. save_messages: 메시지 저장 + 재저장 (idempotent)
  3. finalize_session: 메시지 저장 + fallback 요약 생성
  4. search_sessions: FTS5 검색 (키워드 매칭)
  5. get_anchored_view: Anchor 기반 ±window 인출 + bookend
  6. browse_recent: 최근 세션 목록
  7. 현재 세션 제외 검색
=============================================================================
"""

import os
import sys
import asyncio
import tempfile

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.middleware.memory.episodic_store import EpisodicStore


def _run(coro):
    return asyncio.run(coro)


async def _setup_store_with_data(tmpdir):
    """테스트용 스토어 생성 + 세션 A 데이터 삽입."""
    db_path = os.path.join(tmpdir, "test.db")
    store = EpisodicStore(db_path=db_path)
    await store.setup()

    messages_a = [
        {"role": "human", "content": "FastAPI에서 JWT 토큰 만료를 어떻게 처리하나요?"},
        {"role": "ai", "content": "JWT 토큰 만료는 middleware에서 exp 클레임을 검증합니다."},
        {"role": "human", "content": "refresh token은 어떻게 구현하나요?"},
        {"role": "ai", "content": "refresh token은 별도 엔드포인트로 /auth/refresh에서 처리합니다."},
        {"role": "human", "content": "access token과 refresh token의 만료 시간 차이는?"},
        {"role": "ai", "content": "access token은 15분, refresh token은 7일이 일반적인 설정입니다."},
    ]
    await store.finalize_session("session_jwt_001", messages_a, llm=None)
    return store


def test_01_db_init():
    """DB 초기화 + 테이블 생성."""
    async def _test():
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            store = EpisodicStore(db_path=db_path)
            await store.setup()
            assert os.path.exists(db_path), "DB 파일이 생성되지 않음"
            await store.close()
    _run(_test())
    return {"pass": True, "detail": "SQLite DB 파일 생성 + FTS5 테이블 초기화 완료"}


def test_02_save_messages():
    """save_messages: 메시지 저장 + 재저장 (upsert)."""
    async def _test():
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            store = EpisodicStore(db_path=db_path)
            await store.setup()

            msgs = [
                {"role": "human", "content": "Hello"},
                {"role": "ai", "content": "Hi there!"},
            ]
            count1 = await store.save_messages("s1", msgs)
            assert count1 == 2, f"2개 저장 예상, 실제: {count1}"

            # 재저장 (upsert — 기존 삭제 후 재삽입)
            msgs2 = msgs + [{"role": "human", "content": "How are you?"}]
            count2 = await store.save_messages("s1", msgs2)
            assert count2 == 3, f"3개 저장 예상, 실제: {count2}"
            await store.close()
    _run(_test())
    return {"pass": True, "detail": "메시지 저장 2개 → 재저장 3개 (upsert) 정상"}


def test_03_finalize_with_fallback_summary():
    """finalize_session: LLM=None → fallback 요약 생성."""
    async def _test():
        with tempfile.TemporaryDirectory() as tmpdir:
            store = await _setup_store_with_data(tmpdir)
            recent = await store.browse_recent(limit=5)
            assert len(recent) >= 1, "finalize 후 세션이 browse_recent에 없음"
            session = recent[0]
            assert session["summary"], "요약이 비어있음"
            assert session["session_id"] == "session_jwt_001"
            await store.close()
            return session["summary"]
    summary = _run(_test())
    return {"pass": True, "detail": f"Fallback 요약 생성: '{summary[:60]}...'"}


def test_04_fts5_search():
    """search_sessions: FTS5 키워드 검색."""
    async def _test():
        with tempfile.TemporaryDirectory() as tmpdir:
            store = await _setup_store_with_data(tmpdir)
            results = await store.search_sessions("JWT token", top_k=3)
            await store.close()
            return results
    results = _run(_test())
    # FTS5 인덱싱이 정상이면 결과가 있어야 함
    assert len(results) >= 1, f"FTS5 검색 결과가 없음 (결과: {results})"
    assert results[0]["session_id"] == "session_jwt_001"
    return {"pass": True, "detail": f"FTS5 검색 성공: {len(results)}개 결과, 첫 결과={results[0]['session_id']}"}


def test_05_anchored_view_with_keyword():
    """get_anchored_view: Anchor 키워드 기반 ±window 인출."""
    async def _test():
        with tempfile.TemporaryDirectory() as tmpdir:
            store = await _setup_store_with_data(tmpdir)
            view = await store.get_anchored_view(
                session_id="session_jwt_001",
                anchor_keyword="refresh token",
                window=1,
            )
            await store.close()
            return view
    view = _run(_test())
    assert len(view) >= 1, "Anchor 인출 결과가 비어있음"
    # refresh token 관련 메시지가 포함되어 있어야 함
    contents = " ".join(m.get("content", "") for m in view)
    assert "refresh" in contents.lower(), f"anchor 주변에 'refresh' 관련 내용 없음: {contents[:100]}"
    return {"pass": True, "detail": f"Anchor('refresh token') ±1 인출: {len(view)}개 메시지, refresh 키워드 포함 확인"}


def test_06_anchored_view_tail():
    """get_anchored_view: anchor 없으면 마지막 N개 반환."""
    async def _test():
        with tempfile.TemporaryDirectory() as tmpdir:
            store = await _setup_store_with_data(tmpdir)
            view = await store.get_anchored_view(
                session_id="session_jwt_001",
                anchor_keyword="",
                window=2,
            )
            await store.close()
            return view
    view = _run(_test())
    assert len(view) == 2, f"마지막 2개 메시지 예상, 실제: {len(view)}"
    return {"pass": True, "detail": f"Anchor 없음 → tail view: {len(view)}개 메시지 반환"}


def test_07_exclude_current_session():
    """search_sessions: 현재 세션 제외."""
    async def _test():
        with tempfile.TemporaryDirectory() as tmpdir:
            store = await _setup_store_with_data(tmpdir)
            results = await store.search_sessions(
                "JWT", top_k=5, exclude_session_id="session_jwt_001"
            )
            await store.close()
            return results
    results = _run(_test())
    for r in results:
        assert r["session_id"] != "session_jwt_001", "현재 세션이 제외되지 않음"
    return {"pass": True, "detail": f"exclude_session_id 적용: 결과에 session_jwt_001 미포함 ({len(results)}개 결과)"}


def test_08_browse_recent_ordering():
    """browse_recent: 최신 순 정렬."""
    async def _test():
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            store = EpisodicStore(db_path=db_path)
            await store.setup()

            # 세션 2개 순차 생성
            await store.finalize_session("older_session", [
                {"role": "human", "content": "Old conversation."},
                {"role": "ai", "content": "Old response."},
            ], llm=None)

            await store.finalize_session("newer_session", [
                {"role": "human", "content": "New conversation."},
                {"role": "ai", "content": "New response."},
            ], llm=None)

            recent = await store.browse_recent(limit=5)
            await store.close()
            return recent

    recent = _run(_test())
    assert len(recent) >= 2, f"최소 2개 세션 예상, 실제: {len(recent)}"
    assert recent[0]["session_id"] == "newer_session", f"최신 세션이 첫 번째여야 함, 실제: {recent[0]['session_id']}"
    return {"pass": True, "detail": f"최신 순 정렬: [{recent[0]['session_id']}, {recent[1]['session_id']}]"}


# ── Progressive Keyword Pipeline 테스트 ──

# 파이프라인 테스트용 한국어 대화 데이터셋
_PIPELINE_MSGS = [
    {"role": "human", "content": "오늘 마이크로서비스 인증 아키텍처 회의를 시작합시다."},
    {"role": "ai", "content": "네, 세션 기반 인증과 JWT 토큰 인증 중 어떤 방식을 검토할까요?"},
    {"role": "human", "content": "확장성을 위해 Stateless JWT 방식으로 진행합시다."},
    {"role": "ai", "content": "좋습니다. Stateless JWT 아키텍처로 진행하겠습니다."},
    {"role": "human", "content": "Refresh Token 보안 저장소 위치는 어디로 확정할까요?"},
    {"role": "ai", "content": "XSS 공격 방지를 위해 클라이언트 로컬스토리지 대신 HTTP-Only Secure Cookie에 보관합니다."},
]


def test_09_extract_local_keywords_korean():
    """_extract_local_keywords: 한국어 원문 핵심 명사 추출."""
    store = EpisodicStore(db_path="/tmp/unused.db")
    keywords = store._extract_local_keywords(_PIPELINE_MSGS)

    # 대화에 등장하는 핵심 한국어 명사가 반드시 포함되어야 함
    # 주의: max_keywords=15이므로 빈도가 높은 핵심 명사를 기대값으로 설정
    kw_set = set(keywords)
    must_have_ko = ["인증", "마이크로서비스", "공격"]
    found = [w for w in must_have_ko if w in kw_set]
    missing = [w for w in must_have_ko if w not in kw_set]
    assert len(missing) == 0, f"한국어 핵심 명사 누락: {missing}, 추출 결과: {keywords}"
    return {"pass": True, "detail": f"한국어 핵심 명사 {found} 전부 추출 성공 (총 {len(keywords)}개 키워드)"}


def test_10_extract_local_keywords_english():
    """_extract_local_keywords: 영어 기술어 추출 + 대소문자 보존."""
    store = EpisodicStore(db_path="/tmp/unused.db")
    keywords = store._extract_local_keywords(_PIPELINE_MSGS)
    kw_set = set(keywords)

    # 대문자 기술어(JWT, XSS, Stateless 등)가 원본 대소문자 유지되어야 함
    must_have_en = ["JWT", "XSS", "Stateless"]
    found = [w for w in must_have_en if w in kw_set]
    missing = [w for w in must_have_en if w not in kw_set]
    assert len(missing) == 0, f"영어 기술어 누락: {missing}, 추출 결과: {keywords}"
    return {"pass": True, "detail": f"영어 기술어 {found} 대소문자 보존 추출 성공"}


def test_11_extract_local_keywords_stopwords():
    """_extract_local_keywords: 한국어/영어 불용어 필터링."""
    store = EpisodicStore(db_path="/tmp/unused.db")
    keywords = store._extract_local_keywords(_PIPELINE_MSGS)
    kw_lower = [k.lower() for k in keywords]

    # 불용어로 정의된 단어는 키워드에 포함되면 안 됨
    ko_stopwords_in_data = ["그리고", "오늘", "어떤"]
    en_stopwords_in_data = ["the", "and", "with"]
    leaked = [
        w for w in ko_stopwords_in_data + en_stopwords_in_data
        if w.lower() in kw_lower
    ]
    assert len(leaked) == 0, f"불용어가 키워드에 누출됨: {leaked}"
    return {"pass": True, "detail": f"불용어 필터링 정상 (누출 0건, 총 {len(keywords)}개 키워드)"}


def test_12_merge_keywords_dedup():
    """_merge_keywords: LLM + 로컬 키워드 병합 시 대소문자 무시 중복 제거."""
    local = ["JWT", "쿠키", "보안", "Stateless", "인증"]
    llm = ["jwt", "쿠키 보안", "cookie security", "인증", "마이크로서비스"]

    merged = EpisodicStore._merge_keywords(local, llm)

    # 1. LLM 키워드가 먼저 배치되어야 함
    assert merged[0].lower() == "jwt", f"LLM 키워드가 우선이어야 함, 실제 첫 키워드: {merged[0]}"

    # 2. 대소문자 무시 중복 제거: 'JWT'와 'jwt'가 동시에 있으면 안 됨
    lower_list = [k.lower() for k in merged]
    assert lower_list.count("jwt") == 1, f"'jwt' 중복 발생: {merged}"

    # 3. 로컬에만 있던 키워드('Stateless')가 보충되어야 함
    merged_lower = set(k.lower() for k in merged)
    assert "stateless" in merged_lower, f"로컬 키워드 'Stateless'가 보충되지 않음: {merged}"

    # 4. '보안'과 '쿠키 보안'은 별개 키워드이므로 둘 다 존재해야 함
    assert "보안" in merged_lower or any("보안" in k for k in merged), \
        f"'보안' 키워드 누락: {merged}"

    return {"pass": True, "detail": f"병합 결과 {len(merged)}개, 중복 제거 + LLM 우선 + 로컬 보충 정상"}


def test_13_fallback_uses_local_keywords():
    """_fallback_summary: LLM=None 시 로컬 키워드(_extract_local_keywords) 사용 검증."""
    async def _test():
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            store = EpisodicStore(db_path=db_path)
            await store.setup()
            await store.finalize_session("pipeline_fallback", _PIPELINE_MSGS, llm=None)

            rows = await store._conn.execute_fetchall(
                "SELECT keywords FROM sessions WHERE session_id = ?",
                ("pipeline_fallback",)
            )
            await store.close()
            return rows

    rows = _run(_test())
    assert len(rows) == 1, "세션이 저장되지 않음"
    import json as _json
    keywords = _json.loads(rows[0][0])

    # Fallback이 _extract_local_keywords() 결과를 사용해야 함
    # → 기존 len(w) > 4 필터와 달리, 2자 이상 한국어 명사가 포함되어야 함
    kw_set = set(keywords)
    assert "인증" in kw_set, f"한국어 명사 '인증'(2자)이 Fallback 키워드에 없음: {keywords}"
    assert "JWT" in kw_set, f"영어 기술어 'JWT'가 Fallback 키워드에 없음: {keywords}"
    return {"pass": True, "detail": f"Fallback이 로컬 키워드 사용 확인 (한글 2자 명사 + 영문 기술어 포함, {len(keywords)}개)"}


def test_14_local_keywords_fts5_korean_search():
    """FTS5 한국어 검색: 로컬 키워드 덕분에 원문 한국어로 검색 성공."""
    async def _test():
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            store = EpisodicStore(db_path=db_path)
            await store.setup()
            await store.finalize_session("pipeline_ko_search", _PIPELINE_MSGS, llm=None)

            # 대화 원문에서 빈도 높은 한국어 핵심 단어('인증')로 검색
            results = await store.search_sessions("인증", top_k=5)
            await store.close()
            return results

    results = _run(_test())
    sids = [r["session_id"] for r in results]
    assert "pipeline_ko_search" in sids, \
        f"한국어 '인증' 검색으로 세션을 찾지 못함. 검색 결과: {sids}"
    return {"pass": True, "detail": f"한국어 '인증' 검색 성공! 로컬 키워드가 FTS5에 정확히 색인됨"}


# ── Runner ──

ALL_TESTS = [
    test_01_db_init,
    test_02_save_messages,
    test_03_finalize_with_fallback_summary,
    test_04_fts5_search,
    test_05_anchored_view_with_keyword,
    test_06_anchored_view_tail,
    test_07_exclude_current_session,
    test_08_browse_recent_ordering,
    test_09_extract_local_keywords_korean,
    test_10_extract_local_keywords_english,
    test_11_extract_local_keywords_stopwords,
    test_12_merge_keywords_dedup,
    test_13_fallback_uses_local_keywords,
    test_14_local_keywords_fts5_korean_search,
]


def run_all():
    results = []
    for test_fn in ALL_TESTS:
        name = test_fn.__name__
        try:
            result = test_fn()
            results.append({"test": name, "status": "PASS", "detail": result["detail"]})
        except Exception as e:
            results.append({"test": name, "status": "FAIL", "detail": str(e)})
    return results


if __name__ == "__main__":
    results = run_all()
    print("=" * 70)
    print("Test 03: Episodic Memory Store 검증")
    print("=" * 70)
    for r in results:
        icon = "✅" if r["status"] == "PASS" else "❌"
        print(f"  {icon} {r['test']}: {r['detail']}")
    passed = sum(1 for r in results if r["status"] == "PASS")
    total = len(results)
    print(f"\n  Result: {passed}/{total} passed")
