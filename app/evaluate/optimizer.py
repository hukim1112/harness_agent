"""
===============================================================================
[Evaluation Engine] Prompt Optimizer & Evaluation Function Module
===============================================================================
Source: app/evaluate/optimizer.py

오프라인 배치 벤치마크 평가 및 힐 클라이밍(Hill Climbing) 기반 프롬프트 자동 최적화 모듈.
- Train/Validation 분리 지원 (`val_dataset` 제공 시 Train 실패 트레이스로 변형, Validation 점수로 채택/폐기)
- 길이 페널티(Length Penalty) 목적 함수 지원: `objective = avg_score - length_penalty_alpha * len(prompt)`
- `JudgeVerdict` 구조화 출력(`with_structured_output`) 및 레거시 `judge_chain`+`judge_parser` 양쪽 호환
===============================================================================
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from langchain_core.prompts import ChatPromptTemplate

from app.middleware.evaluator.evaluator import JudgeVerdict
from app.utils import normalize_content


DEFAULT_PROPOSER_SYSTEM_PROMPT = """당신은 AI 에이전트의 시스템 프롬프트를 분석하고 개선하는 프롬프트 최적화 전문가입니다.

[작업]
아래 '현재 프롬프트'의 약점을 '실패 사례 분석'을 참고하여 파악하고,
실패를 방지하는 방향으로 간결하게 개선된 새로운 시스템 프롬프트를 생성하세요.

[엄격한 제약 조건]
1. 현재 프롬프트의 핵심 역할과 기존 출력 규칙은 반드시 유지하세요.
2. 실패 사례의 피드백을 직접 반영하는 구체적 지시사항을 추가하세요.
3. 불필요한 미사여구 없이 최대 6줄 이내로 간결하게 작성하세요.
4. 오직 개선된 프롬프트 텍스트만 출력하세요. 설명, 따옴표, 마크다운 백틱 없이 순수 텍스트만 출력하세요."""


def _score_case(
    *,
    case: Dict[str, Any],
    final_text: str,
    judge_llm: Optional[Any],
    judge_chain: Optional[Any],
    judge_parser: Optional[Any],
) -> Tuple[int, bool, str]:
    user_query = f"{case['query']} [요구사항: {case.get('requirements', '')}]"
    trajectory = f"[Tool Response]: {case.get('tool_context', '')}"

    if judge_llm is not None and judge_chain is None:
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "당신은 AI 에이전트의 실행 근거와 최종 답변을 공정하게 채점하는 감사관입니다.\n"
                "먼저 `evidence`에 도구 실행 결과와 답변 대조 근거를 적고, `reason`에 판정 사유를 적은 뒤 "
                "`is_approved`, `score`(0~100), `feedback`을 작성하세요.",
            ),
            (
                "user",
                "■ 유저 원래 요청: {user_query}\n"
                "■ 도구 실행 궤적: {trajectory}\n"
                "■ 에이전트 최종 답변: {final_answer}",
            ),
        ])
        formatted_msgs = prompt.format_messages(
            user_query=user_query,
            trajectory=trajectory,
            final_answer=final_text,
        )
        structured = judge_llm.with_structured_output(JudgeVerdict)
        try:
            raw = structured.invoke(formatted_msgs, config={"tags": ["exclude_from_stream"]})
            verdict = JudgeVerdict(**raw) if isinstance(raw, dict) else raw
            return int(verdict.score), bool(verdict.is_approved), str(verdict.feedback or verdict.reason)
        except Exception as e:
            return 0, False, str(e)

    if judge_chain is None:
        raise ValueError("evaluate_system_prompt requires either judge_llm or (judge_chain, judge_parser).")

    try:
        fmt = judge_parser.get_format_instructions() if judge_parser is not None else ""
        verdict = judge_chain.invoke({
            "user_query": user_query,
            "trajectory": trajectory,
            "final_answer": final_text,
            "format_instructions": fmt,
        })
        if isinstance(verdict, dict):
            score = int(verdict.get("score", 0))
            approved = bool(verdict.get("is_approved", False))
            feedback = str(verdict.get("feedback", "") or verdict.get("reason", ""))
            return score, approved, feedback
        return int(verdict.score), bool(verdict.is_approved), str(verdict.feedback or verdict.reason)
    except Exception as e:
        return 0, False, str(e)


def evaluate_system_prompt(
    system_prompt: str,
    dataset: List[Dict[str, Any]],
    model: Any,
    judge_chain: Optional[Any] = None,
    judge_parser: Optional[Any] = None,
    judge_llm: Optional[Any] = None,
) -> Tuple[float, List[int], List[Dict[str, Any]]]:
    """
    시스템 프롬프트를 받아 데이터셋 전체 평균 점수와 실패 트레이스를 반환합니다.

    Returns:
        (avg_score, individual_scores, failure_traces)
    """
    response_prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "■ 도구 실행 결과:\n{tool_context}\n\n■ 사용자 요청:\n{query}"),
    ])

    scores: List[int] = []
    failures: List[Dict[str, Any]] = []

    for case in dataset:
        msgs = response_prompt.format_messages(
            tool_context=case.get("tool_context", ""),
            query=case["query"],
        )
        response = model.invoke(msgs)
        final_text = normalize_content(response.content)

        score, approved, feedback = _score_case(
            case=case,
            final_text=final_text,
            judge_llm=judge_llm,
            judge_chain=judge_chain,
            judge_parser=judge_parser,
        )
        scores.append(score)
        if not approved:
            failures.append({
                "id": case["id"],
                "query": case["query"],
                "answer": final_text[:180],
                "feedback": feedback[:240],
            })

    avg_score = sum(scores) / len(scores) if scores else 0.0
    return avg_score, scores, failures


def _objective_score(avg_score: float, prompt: str, length_penalty_alpha: float) -> float:
    return round(avg_score - length_penalty_alpha * len(prompt), 3)


def hill_climbing_optimize(
    baseline: str,
    dataset: List[Dict[str, Any]],
    model: Any,
    judge_chain: Optional[Any] = None,
    judge_parser: Optional[Any] = None,
    proposer_llm: Optional[Any] = None,
    judge_llm: Optional[Any] = None,
    val_dataset: Optional[List[Dict[str, Any]]] = None,
    length_penalty_alpha: float = 0.0,
    max_iterations: int = 3,
    target_score: float = 100.0,
    proposer_system_prompt: Optional[str] = None,
    verbose: bool = True,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    힐 클라이밍 알고리즘으로 시스템 프롬프트를 반복 최적화합니다.

    - `val_dataset`이 주어지면 `dataset`(Train)의 실패 트레이스로 변형안을 생성하고,
      채택(Accept/Reject) 판정은 반드시 `val_dataset`(Validation) 점수로 수행해 과적합을 방지합니다.
    - `length_penalty_alpha > 0`이면 `목적 함수 = 검증 점수 - alpha * 프롬프트 문자 수`를
      최대화하여 프롬프트 비대화(Prompt Bloating)를 억제합니다.
    """
    proposer = proposer_llm or model
    proposer_prompt_template = proposer_system_prompt or DEFAULT_PROPOSER_SYSTEM_PROMPT
    eval_split = val_dataset if val_dataset is not None else dataset

    current_prompt = baseline
    train_avg, train_scores, current_failures = evaluate_system_prompt(
        current_prompt,
        dataset,
        model,
        judge_chain=judge_chain,
        judge_parser=judge_parser,
        judge_llm=judge_llm,
    )
    if val_dataset is not None:
        val_avg, val_scores, _ = evaluate_system_prompt(
            current_prompt,
            val_dataset,
            model,
            judge_chain=judge_chain,
            judge_parser=judge_parser,
            judge_llm=judge_llm,
        )
    else:
        val_avg, val_scores = train_avg, train_scores

    current_obj = _objective_score(val_avg, current_prompt, length_penalty_alpha)

    history: List[Dict[str, Any]] = [{
        "iteration": 0,
        "prompt": current_prompt,
        "avg_score": val_avg,
        "train_avg_score": train_avg,
        "objective_score": current_obj,
        "prompt_chars": len(current_prompt),
        "scores": val_scores,
        "accepted": True,
        "label": "Baseline",
    }]

    if verbose:
        split_label = "Train/Val 분리" if val_dataset is not None else "단일셋"
        print("=" * 70)
        print(f"📊 [Iteration 0 — Baseline] ({split_label}, len={len(current_prompt)}자)")
        print(f'   프롬프트: "{current_prompt}"')
        print(f"   검증 평균: {val_avg:.1f}점 (목적함수: {current_obj:.2f}) | 개별: {val_scores}")
        print(f"   Train 실패 건수: {len(current_failures)}건")
        print("=" * 70)

    if val_avg >= target_score:
        if verbose:
            print(f"\n🎯 [Early Stopping] 베이스라인이 이미 목표 점수({target_score}점)를 달성했습니다.")
        return current_prompt, history

    for i in range(1, max_iterations + 1):
        if verbose:
            print(f"\n🔄 [Iteration {i}/{max_iterations}]")

        failure_text = "\n".join([
            f"  - [{f['id']}] 질문: {f['query']}\n"
            f"    답변(일부): {f['answer']}\n"
            f"    Judge 피드백: {f['feedback']}"
            for f in current_failures
        ]) if current_failures else "  (실패 사례 없음 — 간결성과 명료성 유지)"

        proposer_prompt = ChatPromptTemplate.from_messages([
            ("system", proposer_prompt_template),
            (
                "user",
                f"[현재 프롬프트]:\n{current_prompt}\n\n"
                f"[현재 검증 점수]: {val_avg:.1f}점\n\n"
                f"[Train 실패 사례 분석]:\n{failure_text}",
            ),
        ])
        proposed_response = proposer.invoke(proposer_prompt.format_messages())
        new_prompt = normalize_content(proposed_response.content).strip()
        new_prompt = new_prompt.strip('"').strip("'").strip("`")

        if verbose:
            truncated = f"{new_prompt[:120]}..." if len(new_prompt) > 120 else new_prompt
            print(f'   💡 제안된 프롬프트 ({len(new_prompt)}자): "{truncated}"')

        new_train_avg, new_train_scores, new_failures = evaluate_system_prompt(
            new_prompt,
            dataset,
            model,
            judge_chain=judge_chain,
            judge_parser=judge_parser,
            judge_llm=judge_llm,
        )
        if val_dataset is not None:
            new_val_avg, new_val_scores, _ = evaluate_system_prompt(
                new_prompt,
                eval_split,
                model,
                judge_chain=judge_chain,
                judge_parser=judge_parser,
                judge_llm=judge_llm,
            )
        else:
            new_val_avg, new_val_scores = new_train_avg, new_train_scores

        new_obj = _objective_score(new_val_avg, new_prompt, length_penalty_alpha)
        accepted = new_obj > current_obj

        if accepted:
            improvement = new_val_avg - val_avg
            if verbose:
                print(f"   ✅ ACCEPTED: 검증 {val_avg:.1f} → {new_val_avg:.1f}점 (▲ {improvement:+.1f}, obj {current_obj:.2f}→{new_obj:.2f})")
            current_prompt = new_prompt
            val_avg = new_val_avg
            val_scores = new_val_scores
            current_obj = new_obj
            current_failures = new_failures
        else:
            if verbose:
                print(f"   ❌ REJECTED: 제안 obj {new_obj:.2f} ≤ 현재 {current_obj:.2f} (개선 없음, 폐기)")

        history.append({
            "iteration": i,
            "prompt": new_prompt,
            "avg_score": new_val_avg,
            "train_avg_score": new_train_avg,
            "objective_score": new_obj,
            "prompt_chars": len(new_prompt),
            "scores": new_val_scores,
            "accepted": accepted,
            "label": f"Iter {i} ({'✅' if accepted else '❌'})",
        })

        if val_avg >= target_score:
            if verbose:
                print(f"\n🎯 [Early Stopping] 목표 점수({target_score}점)에 도달해 최적화를 조기 종료합니다.")
            break

    if verbose:
        print("\n" + "=" * 70)
        print("🏆 [힐 클라이밍 완료]")
        print(f"   최종 최적 프롬프트 ({len(current_prompt)}자):\n   {current_prompt}")
        print(f"   최종 검증 평균 점수: {val_avg:.1f}점 (목적함수: {current_obj:.2f})")
        print("=" * 70)

    return current_prompt, history
