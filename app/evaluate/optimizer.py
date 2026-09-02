"""
===============================================================================
[Evaluation Engine] Prompt Optimizer & Evaluation Function Module
===============================================================================
Source: app/evaluate/optimizer.py

오프라인 배치 벤치마크 평가 및 힐 클라이밍(Hill Climbing) 기반 프롬프트 자동 최적화 모듈.
LLM-as-a-Judge를 목적 함수(Objective Function)로 활용하여 시스템 프롬프트를 반복 변형(Mutation)하고
성능을 점진적으로 개선합니다.
===============================================================================
"""

from typing import Any, Dict, List, Optional, Tuple
from langchain_core.prompts import ChatPromptTemplate
from app.utils import normalize_content


DEFAULT_PROPOSER_SYSTEM_PROMPT = """당신은 AI 에이전트의 시스템 프롬프트를 분석하고 개선하는 프롬프트 최적화 전문가입니다.

[작업]
아래 '현재 프롬프트'의 약점을 '실패 사례 분석'을 참고하여 파악하고,
실패를 방지하는 방향으로 소폭 개선된 새로운 시스템 프롬프트를 생성하세요.

[엄격한 제약 조건]
1. 현재 프롬프트의 핵심 역할(고객 서비스)은 반드시 유지하세요.
2. 실패 사례의 피드백을 직접 반영하는 구체적 지시사항을 추가하세요.
3. 프롬프트는 최대 5줄 이내로 간결하게 유지하세요.
4. 오직 개선된 프롬프트 텍스트만 출력하세요. 설명, 따옴표, 마크다운 서식 없이 순수 텍스트만 출력."""


def evaluate_system_prompt(
    system_prompt: str,
    dataset: List[Dict[str, Any]],
    model: Any,
    judge_chain: Any,
    judge_parser: Any,
) -> Tuple[float, List[int], List[Dict[str, Any]]]:
    """
    시스템 프롬프트를 받아 전체 데이터셋에 대한 평균 점수와 실패 트레이스를 반환합니다.

    핵심 아이디어: 시스템 프롬프트가 '변수'이고 점수가 '목적 함수'입니다.
    힐 클라이밍은 이 목적 함수를 최대화하는 프롬프트를 탐색합니다.

    Args:
        system_prompt: 평가할 시스템 프롬프트 문자열
        dataset: 벤치마크 평가 케이스 리스트
        model: 답변 생성에 사용할 대상 LLM
        judge_chain: LLM-as-a-Judge 평가 체인
        judge_parser: Judge 출력 JsonOutputParser

    Returns:
        (avg_score, individual_scores, failure_traces)
    """
    response_chain = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "■ 도구 실행 결과:\n{tool_context}\n\n■ 사용자 요청:\n{query}")
    ]) | model

    scores = []
    failures = []

    for case in dataset:
        # (1) 주어진 프롬프트로 에이전트 답변 생성
        response = response_chain.invoke({
            "tool_context": case["tool_context"],
            "query": case["query"]
        })
        final_text = normalize_content(response.content)

        # (2) LLM-as-a-Judge 채점
        try:
            verdict = judge_chain.invoke({
                "user_query": f"{case['query']} [요구사항: {case['requirements']}]",
                "trajectory": f"[Tool Response]: {case['tool_context']}",
                "final_answer": final_text,
                "format_instructions": judge_parser.get_format_instructions()
            })
            score = verdict.get("score", 0)
            approved = verdict.get("is_approved", False)
            feedback = verdict.get("feedback", "") or verdict.get("reason", "")
        except Exception as e:
            score, approved, feedback = 0, False, str(e)

        scores.append(score)
        if not approved:
            failures.append({
                "id": case["id"],
                "query": case["query"],
                "answer": final_text[:150],
                "feedback": feedback[:200]
            })

    avg_score = sum(scores) / len(scores) if scores else 0.0
    return avg_score, scores, failures


def hill_climbing_optimize(
    baseline: str,
    dataset: List[Dict[str, Any]],
    model: Any,
    judge_chain: Any,
    judge_parser: Any,
    proposer_llm: Optional[Any] = None,
    max_iterations: int = 3,
    target_score: float = 100.0,
    proposer_system_prompt: Optional[str] = None,
    verbose: bool = True,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    힐 클라이밍 알고리즘으로 시스템 프롬프트를 반복 최적화합니다.

    각 반복(iteration)에서:
      1. Proposer LLM이 실패 사례를 분석하여 프롬프트 변형(Mutation)을 제안
      2. 변형 프롬프트를 평가 데이터셋으로 배치 평가
      3. 점수 개선 시 채택(Accept), 아닌 경우 폐기(Reject) — Greedy Hill Climbing
      4. 만점(target_score) 도달 시 조기 종료(Early Stopping)하여 불필요한 비용/시간 절감

    Args:
        baseline: 초기 시스템 프롬프트
        dataset: 평가 데이터셋
        model: 대상 에이전트 구동용 LLM
        judge_chain: LLM-as-a-Judge 체인
        judge_parser: Judge 출력 파서
        proposer_llm: 프롬프트 변형 제안용 Meta-Optimizer LLM (None이면 model 재활용)
        max_iterations: 최대 반복 횟수
        target_score: 조기 종료 목표 점수 (기본값: 100.0)
        proposer_system_prompt: 제안기 시스템 프롬프트 (None이면 기본값 사용)
        verbose: 진행 로그 출력 여부

    Returns:
        (best_prompt, optimization_history)
    """
    proposer = proposer_llm or model
    proposer_prompt_template = proposer_system_prompt or DEFAULT_PROPOSER_SYSTEM_PROMPT

    current_prompt = baseline
    current_avg, current_scores, current_failures = evaluate_system_prompt(
        current_prompt, dataset, model, judge_chain, judge_parser
    )

    history = [{
        "iteration": 0,
        "prompt": current_prompt,
        "avg_score": current_avg,
        "scores": current_scores,
        "accepted": True,
        "label": "Baseline"
    }]

    if verbose:
        print("=" * 70)
        print(f"📊 [Iteration 0 — Baseline]")
        print(f'   프롬프트: "{current_prompt}"')
        print(f"   평균 점수: {current_avg:.1f}점 | 개별: {current_scores}")
        print(f"   실패 건수: {len(current_failures)}건")
        print("=" * 70)

    # 초기 베이스라인에서 이미 목표 점수에 도달한 경우
    if current_avg >= target_score:
        if verbose:
            print(f"\n🎯 [Early Stopping] 베이스라인이 이미 목표 점수({target_score}점)를 달성하여 최적화를 조기 종료합니다.")
        return current_prompt, history

    for i in range(1, max_iterations + 1):
        if verbose:
            print(f"\n🔄 [Iteration {i}/{max_iterations}]")

        # (1) 실패 트레이스를 기반으로 Proposer에게 프롬프트 수정 요청
        failure_text = "\n".join([
            f"  - [{f['id']}] 질문: {f['query']}\n"
            f"    답변(일부): {f['answer']}\n"
            f"    Judge 피드백: {f['feedback']}"
            for f in current_failures
        ]) if current_failures else "  (실패 사례 없음 — 모든 케이스 통과)"

        proposer_chain = ChatPromptTemplate.from_messages([
            ("system", proposer_prompt_template),
            ("user",
             f"[현재 프롬프트]:\n{current_prompt}\n\n"
             f"[현재 평균 점수]: {current_avg:.1f}점\n\n"
             f"[실패 사례 분석]:\n{failure_text}")
        ]) | proposer

        proposed_response = proposer_chain.invoke({})
        new_prompt = normalize_content(proposed_response.content).strip()
        new_prompt = new_prompt.strip('"').strip("'").strip("`")

        if verbose:
            truncated = f'{new_prompt[:120]}...' if len(new_prompt) > 120 else new_prompt
            print(f'   💡 제안된 프롬프트: "{truncated}"')

        # (2) 제안된 프롬프트를 평가 하네스로 배치 평가
        new_avg, new_scores, new_failures = evaluate_system_prompt(
            new_prompt, dataset, model, judge_chain, judge_parser
        )

        # (3) 힐 클라이밍 판정: 점수 개선 시에만 채택 (Greedy)
        accepted = new_avg > current_avg

        if accepted:
            improvement = new_avg - current_avg
            if verbose:
                print(f"   ✅ ACCEPTED: {current_avg:.1f} → {new_avg:.1f}점 (▲ +{improvement:.1f}점 개선)")
            current_prompt = new_prompt
            current_avg = new_avg
            current_scores = new_scores
            current_failures = new_failures
        else:
            if verbose:
                print(f"   ❌ REJECTED: 제안 점수 {new_avg:.1f}점 ≤ 현재 {current_avg:.1f}점 (개선 없음, 폐기)")

        if verbose:
            print(f"   개별 점수: {new_scores}")

        history.append({
            "iteration": i,
            "prompt": new_prompt,
            "avg_score": new_avg,
            "scores": new_scores,
            "accepted": accepted,
            "label": f"Iter {i} ({'✅' if accepted else '❌'})"
        })

        # (4) Early Stopping (조기 종료): 만점 또는 목표 점수 달성 시 중단
        if current_avg >= target_score:
            if verbose:
                print(f"\n🎯 [Early Stopping] 목표 점수({target_score}점)에 도달하여 추가 반복을 중단하고 최적화를 조기 종료합니다. (비용/시간 절감)")
            break

    if verbose:
        print("\n" + "=" * 70)
        print("🏆 [힐 클라이밍 완료]")
        print(f'   최종 최적 프롬프트: "{current_prompt}"')
        print(f"   최종 평균 점수: {current_avg:.1f}점")
        print("=" * 70)

    return current_prompt, history
