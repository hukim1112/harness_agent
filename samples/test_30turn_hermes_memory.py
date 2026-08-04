"""
===============================================================================
[Test Script] Hermes 4-Layer Memory Formation Test (5 Scenarios, 30+ Turns)
-------------------------------------------------------------------------------
Reference Sources & Grounding Traceability:
- Hermes Agent Source: c:/Users/hyoun/Desktop/github/Agent_reference/hermes-agent/hermes_state.py
- Slide Reference: h:/내 드라이브/work_memory/contexts/강의/slides/10_하네스_프로덕션_에이전트/v1.2/03_context_engineering.html
===============================================================================
"""

import sys
import os
import json
import time
from typing import List, Dict, Any, Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from harness.context.hermes_memory import build_hermes_memory_pipeline, HermesMemoryDatabase


# =============================================================================
# Generate 5 Distinct Business Scenarios with 30+ Conversation Turns Each
# =============================================================================
def generate_30turn_scenario_data(scenario_id: int) -> List[Dict[str, str]]:
    turns = []
    
    if scenario_id == 1:
        turns.append({"role": "user", "content": "안녕하세요. 저는 카카오 엔터프라이즈의 인프라 총괄 한석봉 이사입니다."})
        turns.append({"role": "assistant", "content": "반갑습니다, 석봉님! 인프라 전환 프로젝트를 도와드리겠습니다."})
        turns.append({"role": "user", "content": "올해 우리 핵심 미션은 온프레미스 서버 200대를 AWS 및 GCP 멀티 클라우드로 이전하는 것입니다."})
        turns.append({"role": "assistant", "content": "네, 200대 멀티클라우드 이전을 위한 로드맵을 작성하겠습니다."})
        turns.append({"role": "user", "content": "저는 보고서를 받을 때 항상 Markdown 슬라이드 구조와 HSL Tailored 시각화 표를 원합니다."})
        turns.append({"role": "assistant", "content": "알겠습니다. 모든 보고서는 Markdown 슬라이드 및 HSL 표로 정리하겠습니다."})
        for i in range(1, 26):
            turns.append({"role": "user", "content": f"클라우드 마이그레이션 단계 #{i}: 데이터베이스 {i}번 노드 가상화 및 서브넷 설정 검토"})
            turns.append({"role": "assistant", "content": f"단계 #{i} 검토 완료: 정상 동기화되었습니다."})
            
    elif scenario_id == 2:
        turns.append({"role": "user", "content": "저는 재무 감사팀 박영희 팀장입니다. 법인 카드 지출 감사를 수행하고 있습니다."})
        turns.append({"role": "assistant", "content": "안녕하세요, 영희님! 지출 감사 기준에 맞춰 지원하겠습니다."})
        turns.append({"role": "user", "content": "우리 회사의 단일 지출 제한 한도는 $500이며, 주말 사용 건은 무조건 팀장 사전 승인이 필수입니다."})
        turns.append({"role": "assistant", "content": "감사 규칙(한도 $500, 주말 승인 필수)을 등록하였습니다."})
        turns.append({"role": "user", "content": "감사 보고서는 매주 금요일 오후 4시에 JSON 형태와 차트 요약으로 제출해 주세요."})
        turns.append({"role": "assistant", "content": "매주 금요일 16:00 JSON 보고서 제출 일정을 보관합니다."})
        for i in range(1, 26):
            turns.append({"role": "user", "content": f"지출 내역 영수증 #{i}번 검토: 사용자 User_{i}, 금액 ${100 + i*15}, 주말 여부={'True' if i%3==0 else 'False'}"})
            turns.append({"role": "assistant", "content": f"영수증 #{i}번 감사 완료."})

    elif scenario_id == 3:
        turns.append({"role": "user", "content": "저는 수석 아키텍트 최범석입니다. 파이썬 모듈 리팩토링 중입니다."})
        turns.append({"role": "assistant", "content": "안녕하세요, 범석님! 코드 구조 개선 및 Pydantic v2 전환을 지원합니다."})
        turns.append({"role": "user", "content": "우리 팀의 코딩 표준은 Type Hinting 100% 필수이며, Wildcard SELECT * 사용을 엄격히 금지합니다."})
        turns.append({"role": "assistant", "content": "Type Hinting 필수 및 SELECT * 금지 표준을 기록합니다."})
        turns.append({"role": "user", "content": "모든 파이썬 파일의 맨 상단에는 레퍼런스 주석 헤더를 명시해야 합니다."})
        turns.append({"role": "assistant", "content": "파일 상단 레퍼런스 헤더 규정을 저장했습니다."})
        for i in range(1, 26):
            turns.append({"role": "user", "content": f"모듈 #{i}번 코드 리뷰 및 Pydantic v2 스키마 검증 요청: src/harness/module_{i}.py"})
            turns.append({"role": "assistant", "content": f"모듈 #{i}번 검증 완료."})

    elif scenario_id == 4:
        turns.append({"role": "user", "content": "저는 전략기획실 김태호 부사장입니다."})
        turns.append({"role": "assistant", "content": "부사장님, 반갑습니다! 전략 보고 체계를 가동합니다."})
        turns.append({"role": "user", "content": "나는 길고 장황한 텍스트를 싫어한다. 결론을 먼저 말하고 3줄 요약 표로만 보고하라."})
        turns.append({"role": "assistant", "content": "결론 우선 + 3줄 요약 표 보고 규칙을 등록합니다."})
        turns.append({"role": "user", "content": "주요 매출 목표는 2026년까지 1,000억원 달성이다."})
        turns.append({"role": "assistant", "content": "2026년 1,000억원 매출 목표를 보관합니다."})
        for i in range(1, 26):
            turns.append({"role": "user", "content": f"전략 사업부 #{i}번 Q{i%4+1} 실적 점검 요청"})
            turns.append({"role": "assistant", "content": f"사업부 #{i}번 실적 요약 완료."})

    else:
        turns.append({"role": "user", "content": "저는 CISO 이성민 보안이사입니다."})
        turns.append({"role": "assistant", "content": "성민님, 보안 감사 모드를 시작합니다."})
        turns.append({"role": "user", "content": "보안 위협 감지 시 차단율 100%를 목표로 하며 high-risk 명령은 HITL 승인을 거쳐야 한다."})
        turns.append({"role": "assistant", "content": "HITL 승인 게이트 및 High-risk 차단 규칙을 등록합니다."})
        turns.append({"role": "user", "content": "모든 감사 로그는 Structured JSON 형태로 /var/log/audit.json에 영속화하라."})
        turns.append({"role": "assistant", "content": "JSON 감사 로그 경로 저장을 보관합니다."})
        for i in range(1, 26):
            turns.append({"role": "user", "content": f"보안 스캔 노드 #{i}번 트래픽 검사 및 샌드박스 격리 확인"})
            turns.append({"role": "assistant", "content": f"노드 #{i}번 스캔 완료."})

    return turns


def main():
    print("===============================================================================")
    print("🧠 [Hermes Memory Test] 5 Scenarios x 30+ Turns Memory Formation Benchmark")
    print("===============================================================================\n")

    db = HermesMemoryDatabase(db_path="hermes_memory_30turns.db")
    memory_graph = build_hermes_memory_pipeline()

    for s_id in range(1, 6):
        print(f"🔄 Executing Scenario #{s_id} (30 Conversation Turns)...")
        turns = generate_30turn_scenario_data(s_id)
        
        start = time.time()
        res = memory_graph.invoke({"working_memory_l1": turns})
        dur = round(time.time() - start, 2)
        
        extracted = res.get("extracted_data", {})
        print(f"   [Scenario #{s_id} Completed in {dur}s]")
        print(f"   - L2 Episodic Summary: {extracted.get('episodic_summary')[:80]}...")
        print(f"   - L3 Semantic Facts Count: {len(extracted.get('semantic_facts', []))}")
        print(f"   - L4 Procedural Rules Count: {len(extracted.get('procedural_rules', []))}\n")

    print("===============================================================================")
    print("💾 Querying Persistent Hermes 4-Layer Memory Store in SQLite...")
    print("===============================================================================")
    all_mem = db.query_all_memories()
    print(json.dumps(all_mem, indent=2, ensure_ascii=False))

    print("\n✅ All 5 Scenarios (30+ Turns Each) Memory Formation Benchmark Completed!")


if __name__ == "__main__":
    main()
