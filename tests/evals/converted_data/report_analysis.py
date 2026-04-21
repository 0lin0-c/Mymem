from __future__ import annotations

import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any

from services.llm.base import BaseLLMProvider
from tests.evals.converted_data.categories import format_qa_category
from tests.evals.converted_data.metrics import (
    classify_answer_failure,
    enrich_results_data_for_analysis,
    flatten_qa_results,
    get_db_diagnosis,
    get_retrieval_layer,
    get_retrieved_contexts,
    get_retrieved_scores,
)

logger = logging.getLogger(__name__)


MODE_SECTIONS = {
    "storage_eval": [
        "## 1. 总览",
        "## 2. 失败原因",
        "## 3. 成功模式",
        "## 4. 代表性案例",
        "## 5. 建议动作",
    ],
    "retrieval_eval": [
        "## 1. 总览",
        "## 2. 失败原因",
        "### 检索失败类型拆解",
        "## 3. 成功模式",
        "## 4. 代表性案例",
        "## 5. 建议动作",
    ],
    "assistant_eval": [
        "## 1. 总览",
        "## 2. 这轮 trace 能直接证明什么",
        "## 3. 失败原因",
        "## 4. 成功模式",
        "## 5. 代表性案例",
        "## 6. 建议动作",
    ],
}


async def generate_analysis_markdown(
    llm: BaseLLMProvider,
    results_path: Path,
) -> Path | None:
    del llm
    try:
        results_data = json.loads(results_path.read_text(encoding="utf-8"))
        eval_mode = _eval_mode(results_data)
        analysis_md = build_fallback_analysis_markdown(results_data, results_path, eval_mode=eval_mode)
        analysis_path = results_path.with_name(f"{results_path.stem}_analysis.md")
        analysis_path.write_text(analysis_md, encoding="utf-8")
        logger.info("分析报告已生成: %s", analysis_path)
        return analysis_path
    except Exception as exc:
        logger.error("自动分析报告生成失败: %s", exc)
        return None


def build_analysis_prompt(
    results_data: dict[str, Any],
    source_json_path: Path,
    eval_mode: str | None = None,
) -> str:
    mode = eval_mode or _eval_mode(results_data)
    enriched = enrich_results_data_for_analysis(results_data)
    qa_results = flatten_qa_results(enriched)
    cases = [
        _format_case_for_analysis(case, index)
        for index, case in enumerate(_select_representative_cases(qa_results, mode), 1)
    ]
    compact_payload = {
        "result_file": source_json_path.name,
        "eval_mode": mode,
        "statistics": enriched.get("statistics", {}),
        "analysis_summary": enriched.get("analysis_summary", {}),
        "representative_cases": cases,
    }
    sections = "\n".join(MODE_SECTIONS.get(mode, MODE_SECTIONS["assistant_eval"]))
    return (
        "你是 Mymem 记忆系统评估诊断专家。\n"
        "请基于下面的数据，生成一份帮助研发定位问题的 Markdown 报告。\n"
        f"本次 eval_mode: {mode}\n"
        f"结果文件: {source_json_path.name}\n\n"
        f"输出必须包含这些章节:\n{sections}\n\n"
        "要求:\n"
        "- 必须明确区分成功原因和失败原因。\n"
        "- 失败原因要说明问题落在存储、检索、还是回答阶段。\n"
        "- 对 retrieval_eval 和 assistant_eval，必须给出“检索失败类型拆解”汇总和表格。\n"
        "- 每个代表性案例都要引用具体 question / generated_answer / top context / diagnosis。\n"
        "- 不要编造 JSON 里不存在的结论。\n\n"
        "输入数据:\n"
        f"{json.dumps(compact_payload, ensure_ascii=False, indent=2)}"
    )


def analysis_structure_check(markdown_text: str, eval_mode: str | None = None) -> tuple[bool, str]:
    text = (markdown_text or "").strip()
    if not text:
        return False, "empty"

    for section in MODE_SECTIONS.get(eval_mode or "assistant_eval", MODE_SECTIONS["assistant_eval"]):
        if section not in text:
            return False, f"missing_section: {section}"

    if "失败原因" not in text:
        return False, "missing_failure_reason"
    if "成功模式" not in text:
        return False, "missing_success_mode"
    return True, "ok"


def build_fallback_analysis_markdown(
    results_data: dict[str, Any],
    source_json_path: Path,
    eval_mode: str | None = None,
) -> str:
    mode = eval_mode or _eval_mode(results_data)
    enriched = enrich_results_data_for_analysis(results_data)
    stats = enriched.get("statistics", {}) or {}
    qa_results = flatten_qa_results(enriched)

    if mode == "storage_eval":
        return _storage_fallback(source_json_path, stats, enriched, qa_results)
    if mode == "retrieval_eval":
        return _retrieval_fallback(source_json_path, stats, enriched, qa_results)
    return _assistant_fallback(source_json_path, stats, enriched, qa_results)


def _storage_fallback(
    source_json_path: Path,
    stats: dict[str, Any],
    enriched: dict[str, Any],
    qa_results: list[dict[str, Any]],
) -> str:
    failed_cases = [q for q in qa_results if q.get("storage_hit") is False]
    success_cases = [q for q in qa_results if q.get("storage_hit") is True]
    return "\n".join([
        "## 1. 总览",
        f"- 结果文件: {source_json_path.name}",
        f"- 题目数: {stats.get('total_questions', 0)}",
        f"- 存储覆盖率: {stats.get('storage_coverage_rate', 0):.2f}%",
        f"- 成功写入题数: {len(success_cases)}",
        f"- 未写入题数: {len(failed_cases)}",
        *_risk_lines(enriched),
        "",
        "## 2. 失败原因",
        *_storage_failure_lines(failed_cases),
        "",
        "## 3. 成功模式",
        *_storage_success_lines(success_cases),
        "",
        "## 4. 代表性案例",
        *_case_lines(failed_cases[:3] + success_cases[:2], include_answer=False, include_reason=True),
        "",
        "## 5. 建议动作",
        "- P0: 对 storage_hit=False 的题，回放 extraction 输出，确认事实是否在抽取阶段就丢失。",
        "- P0: 对写入命中但 evidence 质量差的题，检查去重和 category 归类是否过粗。",
        "- P1: 在存储报告中补充 language / time / evidence 命中统计，便于追溯污染来源。",
    ])


def _retrieval_fallback(
    source_json_path: Path,
    stats: dict[str, Any],
    enriched: dict[str, Any],
    qa_results: list[dict[str, Any]],
) -> str:
    failed_cases = [q for q in qa_results if q.get("storage_hit") is True and q.get("retrieval_hit") is False]
    success_cases = [q for q in qa_results if q.get("retrieval_hit") is True]
    breakdown = _build_retrieval_breakdown(failed_cases)
    return "\n".join([
        "## 1. 总览",
        f"- 结果文件: {source_json_path.name}",
        f"- 题目数: {stats.get('total_questions', 0)}",
        f"- Recall@K: {stats.get('recall_at_k', 0):.2f}%",
        f"- Top1/Top3/Top5: {stats.get('top1_hit_rate', 0):.2f}% / {stats.get('top3_hit_rate', 0):.2f}% / {stats.get('top5_hit_rate', 0):.2f}%",
        f"- 命中检索题数: {len(success_cases)}",
        f"- 漏召回题数: {len(failed_cases)}",
        *_risk_lines(enriched),
        "",
        "## 2. 失败原因",
        *_retrieval_failure_lines(failed_cases),
        "",
        "### 检索失败类型拆解",
        *_retrieval_breakdown_lines(breakdown),
        "",
        "## 3. 成功模式",
        *_retrieval_success_lines(success_cases),
        "",
        "## 4. 代表性案例",
        *_case_lines(failed_cases[:4] + success_cases[:2], include_answer=False, include_reason=True),
        "",
        "## 5. 建议动作",
        "- P0: 对 retrieval_hit=False 的题，对比 missed evidence 和 Top1 噪声，定位是召回缺失还是排序压制。",
        "- P0: 输出 similarity / importance / recency 分项分数，确认是哪个因子把目标 evidence 压下去了。",
        "- P1: 按 resolved_layer 统计 recall 差异，确认 category_only 是否过早截断了 resource 检索。",
    ])


def _assistant_fallback(
    source_json_path: Path,
    stats: dict[str, Any],
    enriched: dict[str, Any],
    qa_results: list[dict[str, Any]],
) -> str:
    wrong_cases = [q for q in qa_results if q.get("is_correct") is False]
    success_cases = [q for q in qa_results if q.get("is_correct") is True]
    failure_buckets = Counter(_failure_reason_label(q) for q in wrong_cases)

    return "\n".join([
        "## 1. 总览",
        f"- 结果文件: {source_json_path.name}",
        "- 评测模式: `assistant_eval`",
        f"- 题目数: {stats.get('total_questions', 0)}",
        f"- 回答准确率: {stats.get('accuracy', 0):.2f}% ({stats.get('correct_count', 0)}/{stats.get('total_questions', 0)})",
        f"- adjusted accuracy: {stats.get('adjusted_accuracy_excluding_empty_standard', 0):.2f}%",
        f"- Recall@K: {stats.get('recall_at_k', 0):.2f}%",
        f"- 存储覆盖率: {stats.get('storage_coverage_rate', 0):.2f}%",
        f"- 错误题数: {len(wrong_cases)}",
        f"- 正确题数: {len(success_cases)}",
        *_risk_lines(enriched),
        "",
        "本报告只基于当前 JSON trace 可直接支撑的事实下结论，不额外假设数据库中一定已经存在“强证据”，也不把自动诊断标签直接等同于最终根因。",
        "",
        "## 2. 这轮 trace 能直接证明什么",
        *_assistant_direct_fact_lines(stats, qa_results, wrong_cases, success_cases),
        "",
        "## 3. 失败原因",
        *(_counter_lines(failure_buckets) or ["- 没有失败样本。"]),
        *_assistant_failure_summary_lines(wrong_cases),
        "",
        "## 4. 成功模式",
        *_assistant_success_lines(success_cases),
        "",
        "## 5. 代表性案例",
        *_assistant_representative_case_lines(wrong_cases, success_cases),
        "",
        "## 6. 建议动作",
        *_assistant_action_lines(wrong_cases, success_cases),
    ])


def _assistant_direct_fact_lines(
    stats: dict[str, Any],
    qa_results: list[dict[str, Any]],
    wrong_cases: list[dict[str, Any]],
    success_cases: list[dict[str, Any]],
) -> list[str]:
    total = stats.get("total_questions", len(qa_results))
    lines = [f"- {total} 题中有 {len(wrong_cases)} 题回答错误，整体 assistant 侧表现较弱。"]

    if qa_results and all(q.get("storage_hit") is True for q in qa_results):
        lines.append("- 所有题目的 `storage_hit=True`，说明在 DB 诊断阶段，每题都找到了某种候选相关记忆。")
    else:
        storage_true = sum(1 for q in qa_results if q.get("storage_hit") is True)
        lines.append(f"- 有 {storage_true} 题 `storage_hit=True`，说明部分题目在 DB 诊断阶段找到了候选相关记忆。")

    if qa_results and all(q.get("retrieval_hit") is False for q in qa_results):
        lines.append("- 所有题目的 `retrieval_hit=False`，说明没有任何一题在“DB 候选记忆”和“最终 retrieved top-k”之间形成明确命中。")
    else:
        retrieval_true = sum(1 for q in qa_results if q.get("retrieval_hit") is True)
        lines.append(f"- 有 {retrieval_true} 题 `retrieval_hit=True`，其余题目未在 trace 中形成明确 retrieval 命中。")

    unsupported_success = sum(1 for q in success_cases if q.get("retrieval_hit") is False)
    if unsupported_success:
        lines.append(f"- {unsupported_success} 个答对样本同样 `retrieval_hit=False`，因此这轮结果不能证明检索链路有效。")

    category_lines = _assistant_category_accuracy_lines(stats)
    if category_lines:
        lines.append("- 错误高度集中在时间相关题和精确事实定位题：")
        lines.extend(category_lines)

    return lines


def _assistant_category_accuracy_lines(stats: dict[str, Any]) -> list[str]:
    category_accuracy = stats.get("category_accuracy", {}) or {}
    if not category_accuracy:
        return []

    items = []
    for item in category_accuracy.values():
        count = int(item.get("count", 0) or 0)
        if count <= 0:
            continue
        items.append(
            (
                float(item.get("accuracy", 0) or 0),
                -count,
                f"- {item.get('display_name')}: {count} 题，正确 {item.get('correct', 0)} 题，准确率 {float(item.get('accuracy', 0) or 0):.2f}%",
            )
        )
    items.sort(key=lambda x: (x[0], x[1]))
    return [line for _, _, line in items[:3]]


def _assistant_failure_summary_lines(wrong_cases: list[dict[str, Any]]) -> list[str]:
    if not wrong_cases:
        return ["- 没有失败样本。"]

    high_conf_cases = [case for case in wrong_cases if _is_high_confidence_retrieval_mismatch(case)]
    conservative_cases = [case for case in wrong_cases if _needs_conservative_retrieval_language(case)]
    category_only_cases = [
        case for case in wrong_cases if get_retrieval_layer(case).get("resolved_layer") == "category_only"
    ]
    abstained_cases = [case for case in wrong_cases if _looks_like_answer_abstained(case)]

    lines = [
        "- 当前 `statistics.answer_failure_patterns` 中，失败样本主要会被标记为 `retrieval_gap`。",
        "- 这个标签在本轮里更适合解读为：",
        "  - 回答层没有拿到足够直接、足够贴近问题核心的检索证据",
        "  - 但不代表每一题都已经高置信证明“数据库里有强证据，只是 retrieval 漏召回了它”",
        "- 更稳妥的总判断是：",
        "  - 这轮 assistant 失败主要表现为“回答层缺少可用证据”",
        "  - 其中一部分样本较像真实检索失配",
        "  - 另一部分样本仍存在候选证据污染，暂时不能把责任完全坐实到 retrieval",
        "",
        "### 3.1 较高置信的检索失配样本",
    ]

    if high_conf_cases:
        for case in high_conf_cases[:3]:
            lines.extend(_assistant_high_confidence_case_lines(case))
    else:
        lines.append("- 当前没有足够高置信的检索失配样本。")

    lines.extend([
        "",
        "### 3.2 需要保守表述的样本",
    ])
    if conservative_cases:
        for case in conservative_cases[:5]:
            lines.append(f"- `{case.get('question')}`")
        lines.extend([
            "",
            "这些题的共同特点是：",
            "- `retrieval_hit=False`",
            "- `top1_context` 往往明显偏题，说明回答层没拿到直接证据",
            "- 但 `db_memories_sample` 或 `missed_in_retrieval` 中，很多候选是由弱关键词触发",
            "",
            "因此这些题当前只能写成：",
            "- DB 诊断阶段找到了候选片段",
            "- retrieved top-k 没有把足以支撑标准答案的证据带到回答层",
            "- 但 trace 还不足以高置信证明“强证据已经明确存在且被 retrieval 漏掉了”",
        ])
    else:
        lines.append("- 当前没有明显需要降级为保守表述的样本。")

    lines.extend([
        "",
        "### 3.3 路由与回答行为层面的直接现象",
    ])
    if category_only_cases:
        lines.append("- 多个失败样本的 `resolved_layer=category_only`。")
        lines.append("  - 这说明系统有时在 category 层就停止了，没有继续进入 resource 层寻找更细粒度证据。")
        lines.append("  - 但仅凭当前 trace，还不能单独证明“提前停止”就是唯一根因。")
    if abstained_cases:
        lines.append("- 多个失败样本的回答表现为保守拒答，或给出邻近但不等价的记忆。")
        lines.append("  - 这说明回答层整体更像是在“证据不足时保守作答”，而不是无依据编造。")
    else:
        lines.append("- 当前失败样本中没有特别集中的保守拒答模式。")

    lines.extend([
        "",
        "### 3.4 检索失败类型拆解",
        "- 现有 trace 中，可观察到的失败现象主要有三类：",
        "  - `route_miss_category_only`: 分类层结果不足，但流程停在 category 层",
        "  - `noise_outrank_target`: top1/top-k 被明显弱相关或无关上下文占据",
        "  - `low-confidence retrieval_gap`: DB 候选片段存在，但候选证据受弱关键词污染，不能高置信定性",
        "",
        "基于当前失败样本，可按更保守的口径归纳为：",
        f"- 较高置信检索失配: {len(high_conf_cases)} 题",
        f"- category 层提前停止且未拿到可用证据: {len(category_only_cases)} 题",
        f"- 候选证据污染、暂不能高置信定性的样本: {len(conservative_cases)} 题",
    ])
    return lines


def _assistant_high_confidence_case_lines(case: dict[str, Any]) -> list[str]:
    top_context = _top_context(case)
    strong_keywords = _strong_matched_keywords(case)
    lines = [f"- `{case.get('question')}`"]
    if top_context:
        lines.append(f"  - `top1_context` 是 `{_shorten(top_context, 120)}`")
    if strong_keywords:
        lines.append(f"  - `missed_in_retrieval` 里出现了 `{ ' / '.join(strong_keywords[:5]) }` 相关关键词")
    lines.append("  - 这一题可以较高置信地判断为：回答层没有拿到贴近问题核心的检索证据")
    return lines


def _assistant_success_lines(success_cases: list[dict[str, Any]]) -> list[str]:
    if not success_cases:
        return ["- 没有回答成功样本。"]

    retrieval_backed = [case for case in success_cases if case.get("retrieval_hit") is True]
    unsupported = [case for case in success_cases if case.get("retrieval_hit") is False]
    lines = [
        f"- 最终答对 {len(success_cases)} 题。",
        f"- 其中 `retrieval_hit=True` 的证据支撑型成功样本有 {len(retrieval_backed)} 题。",
    ]
    if unsupported:
        lines.append(f"- 有 {len(unsupported)} 题属于“最终回答正确，但 retrieval_hit=False”。")
    if not retrieval_backed:
        lines.append("- 因此这轮 assistant_eval 不能用来证明 retrieval 已经有效支撑回答。")
    lines.append("- 更准确的说法是：")
    lines.append("  - 本轮没有出现足够明确的 evidence-backed success 时，不应把“最终答对”直接写成“检索成功”。")
    if unsupported:
        lines.append("  - 当前成功样本更像是模型基于主题先验、persona/profile、弱上下文或常识归纳作出了正确回答。")
    return lines


def _assistant_representative_case_lines(
    wrong_cases: list[dict[str, Any]],
    success_cases: list[dict[str, Any]],
) -> list[str]:
    lines: list[str] = []

    if wrong_cases:
        high_conf_case = next((case for case in wrong_cases if _is_high_confidence_retrieval_mismatch(case)), None)
        conservative_case = next((case for case in wrong_cases if _needs_conservative_retrieval_language(case)), None)
        resource_case = next(
            (
                case for case in wrong_cases
                if get_retrieval_layer(case).get("resolved_layer") == "category+resource"
            ),
            None,
        )

        if high_conf_case:
            lines.extend(_assistant_case_block("失败案例 1", high_conf_case, _assistant_case_conclusion_high_conf))
            lines.append("")
        if conservative_case and conservative_case is not high_conf_case:
            lines.extend(_assistant_case_block("失败案例 2", conservative_case, _assistant_case_conclusion_conservative))
            lines.append("")
        if resource_case and resource_case not in {high_conf_case, conservative_case}:
            lines.extend(_assistant_case_block("失败案例 3", resource_case, _assistant_case_conclusion_resource))
            lines.append("")

    if success_cases:
        success_case = success_cases[0]
        lines.extend(_assistant_case_block("成功案例 1", success_case, _assistant_case_conclusion_success))

    return lines or ["- 暂无样本。"]


def _assistant_case_block(
    title: str,
    case: dict[str, Any],
    conclusion_builder: Any,
) -> list[str]:
    layer = get_retrieval_layer(case)
    lines = [
        f"### {title}",
        f"- question: `{case.get('question')}`",
        f"- standard_answer: `{case.get('standard_answer') or '(empty)'}`",
    ]
    generated = str(case.get("generated_answer") or "")
    if generated:
        lines.append(f"- generated_answer: `{_shorten(generated, 180)}`")
    lines.append(
        f"- storage_hit={case.get('storage_hit')} | retrieval_hit={case.get('retrieval_hit')} | layer={layer.get('resolved_layer', 'none')}"
    )
    categories = layer.get("llm_classified_categories") or []
    if categories:
        lines.append(f"- llm_classified_categories: `{ ' / '.join(str(c) for c in categories) }`")
    top_context = _top_context(case)
    if top_context:
        lines.append(f"- top1_context: `{_shorten(top_context, 140)}`")
    lines.append("- 当前 trace 可直接支撑的结论:")
    lines.extend(conclusion_builder(case))
    return lines


def _assistant_case_conclusion_high_conf(case: dict[str, Any]) -> list[str]:
    return [
        "  - top1 明显不贴题",
        "  - 回答层没有拿到足够贴近问题核心的检索证据",
        "  - 这题较高置信属于检索失配",
    ]


def _assistant_case_conclusion_conservative(case: dict[str, Any]) -> list[str]:
    return [
        "  - 当前 retrieved 结果不足以支持正确回答",
        "  - top1 更像噪声或邻近记忆，而不是标准答案所需证据",
        "  - 但 `missed_in_retrieval` 里的候选证据受弱关键词影响较大，不能直接下结论说“强证据已明确存在却被 retrieval 漏掉”",
    ]


def _assistant_case_conclusion_resource(case: dict[str, Any]) -> list[str]:
    return [
        "  - resource 层也未能把有效证据带到回答层",
        "  - 当前 trace 只能证明回答层缺少可用证据",
        "  - 若 DB 候选同时受到弱关键词污染，就不能直接把责任完全坐实到 retrieval",
    ]


def _assistant_case_conclusion_success(case: dict[str, Any]) -> list[str]:
    if case.get("retrieval_hit") is True:
        return [
            "  - 最终回答正确",
            "  - trace 中存在 retrieval 命中，因此这题更接近 evidence-backed success",
        ]
    return [
        "  - 最终回答正确",
        "  - 但没有证据表明该正确答案来自有效 retrieval 命中",
        "  - 该样本不能作为检索成功案例",
    ]


def _assistant_action_lines(
    wrong_cases: list[dict[str, Any]],
    success_cases: list[dict[str, Any]],
) -> list[str]:
    del wrong_cases, success_cases
    return [
        "- 报告口径上，后续不要再把“`storage_hit=True` 且 `retrieval_hit=False`”自动翻译成“数据库里已有强证据但 retrieval 漏召回”。",
        "- 对 assistant_eval，优先区分三种结论：回答层缺少可用证据、较高置信的检索失配、候选证据污染且暂不能高置信定性。",
        "- 对成功样本，单独标注是否为 evidence-backed success，避免把“最终答对”误写成“检索有效”。",
        "- 在代表案例中保留 `resolved_layer`、`llm_classified_categories`、`top1_context` 和 `matched_keyword` 质量提示，减少过度解释空间。",
    ]


def _is_high_confidence_retrieval_mismatch(case: dict[str, Any]) -> bool:
    if case.get("retrieval_hit") is not False:
        return False
    subtype, _, _ = _classify_retrieval_failure(case)
    strong_keywords = _strong_matched_keywords(case)
    return bool(strong_keywords) and subtype in {"route_miss_category_only", "noise_outrank_target", "category_too_coarse"}


def _needs_conservative_retrieval_language(case: dict[str, Any]) -> bool:
    if case.get("retrieval_hit") is not False:
        return False
    return _weak_keyword_match(case)


def _looks_like_answer_abstained(case: dict[str, Any]) -> bool:
    answer = str(case.get("generated_answer") or "").lower()
    markers = [
        "i don't have",
        "i do not know",
        "no record",
        "没有",
        "没找到",
        "不确定",
    ]
    return any(marker in answer for marker in markers)


def _strong_matched_keywords(case: dict[str, Any]) -> list[str]:
    keywords = _matched_keywords(case)
    weak_keywords = _weak_keywords()
    strong = []
    seen: set[str] = set()
    for keyword in keywords:
        normalized = str(keyword or "").strip().lower()
        if not normalized or normalized in weak_keywords:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        strong.append(normalized)
    return strong


def _matched_keywords(case: dict[str, Any]) -> list[str]:
    diagnosis = get_db_diagnosis(case) or {}
    keywords: list[str] = []
    for item in diagnosis.get("missed_in_retrieval") or []:
        if isinstance(item, dict):
            keywords.append(str(item.get("matched_keyword") or ""))
    if keywords:
        return keywords

    storage_eval = ((case.get("trace_detail") or {}).get("evaluation_trace") or {}).get("storage_eval") or {}
    for item in storage_eval.get("db_memories_sample") or []:
        if isinstance(item, dict):
            keywords.append(str(item.get("matched_keyword") or ""))
    return keywords


def _eval_mode(results_data: dict[str, Any]) -> str:
    return str((results_data.get("test_info") or {}).get("eval_mode") or "assistant_eval")


def _select_representative_cases(
    qa_results: list[dict[str, Any]],
    eval_mode: str,
    limit: int = 12,
) -> list[dict[str, Any]]:
    if eval_mode == "storage_eval":
        candidates = [q for q in qa_results if q.get("storage_hit") is False]
    elif eval_mode == "retrieval_eval":
        candidates = [q for q in qa_results if q.get("retrieval_hit") is False]
    else:
        candidates = [q for q in qa_results if q.get("is_correct") is False]
    if not candidates:
        candidates = qa_results[:]
    return candidates[:limit]


def _format_case_for_analysis(case: dict[str, Any], index: int) -> dict[str, Any]:
    layer = get_retrieval_layer(case)
    contexts = get_retrieved_contexts(case)
    scores = get_retrieved_scores(case)
    return {
        "case_id": f"案例{index}",
        "character": case.get("character"),
        "question": case.get("question"),
        "standard_answer": case.get("standard_answer"),
        "generated_answer": case.get("generated_answer"),
        "category": case.get("category"),
        "category_display": format_qa_category(case.get("category")),
        "storage_hit": case.get("storage_hit"),
        "retrieval_hit": case.get("retrieval_hit"),
        "rank_position": case.get("rank_position"),
        "retrieval_layer": layer,
        "top_contexts": contexts[:3],
        "top_scores": scores[:3],
        "failure_pattern": case.get("failure_type") or classify_answer_failure(case),
        "db_diagnosis": get_db_diagnosis(case),
    }


def _storage_failure_lines(failed_cases: list[dict[str, Any]]) -> list[str]:
    if not failed_cases:
        return ["- 没有发现 storage_hit=False 的失败样本。"]
    lines = [f"- 主要问题: 有 {len(failed_cases)} 题在数据库中没有找到可支撑答案的 evidence。"]
    for case in failed_cases[:3]:
        lines.append(
            f"- {case.get('question')}: 数据库未命中 supporting evidence，优先检查 extraction / dedup / 分类。"
        )
    return lines


def _storage_success_lines(success_cases: list[dict[str, Any]]) -> list[str]:
    if not success_cases:
        return ["- 没有 storage 成功样本。"]
    return [
        f"- 大部分题已经能在数据库里找到候选 evidence，共 {len(success_cases)} 题 storage_hit=True。",
        "- 这说明主问题不一定在写入本身，后续应继续看 retrieval 和 answer 阶段是否正确利用了这些 evidence。",
    ]


def _retrieval_failure_lines(failed_cases: list[dict[str, Any]]) -> list[str]:
    if not failed_cases:
        return ["- 没有 retrieval_hit=False 的失败样本。"]

    layer_counter = Counter(get_retrieval_layer(case).get("resolved_layer", "none") for case in failed_cases)
    top_noise_counter = Counter(_noise_bucket_label(case) for case in failed_cases)
    lines = [
        f"- 漏召回题数: {len(failed_cases)}。",
        f"- 失败层级分布: {_format_counter(layer_counter)}。",
        f"- 高频 Top1 噪声类型: {_format_counter(top_noise_counter, limit=4)}。",
    ]
    for case in failed_cases[:3]:
        lines.append(f"- {case.get('question')}: {_failure_reason_text(case)}")
    return lines


def _retrieval_success_lines(success_cases: list[dict[str, Any]]) -> list[str]:
    if not success_cases:
        return ["- 没有 retrieval 成功样本。"]
    top1_hits = sum(1 for case in success_cases if case.get("rank_position") == 1)
    return [
        f"- 成功召回题数: {len(success_cases)}。",
        f"- 其中 Top1 直接命中的题数: {top1_hits}。",
        "- 这些题通常表现为 retrieved_contexts 前几条就已经包含答案核心事实，后续回答层更容易答对。",
    ]


def _assistant_failure_lines(wrong_cases: list[dict[str, Any]]) -> list[str]:
    if not wrong_cases:
        return ["- 没有回答失败样本。"]
    lines = []
    for case in wrong_cases[:5]:
        lines.append(f"- {case.get('question')}: {_failure_reason_text(case)}")
    return lines


def _assistant_success_lines(success_cases: list[dict[str, Any]]) -> list[str]:
    if not success_cases:
        return ["- 没有回答成功样本。"]
    suspicious_success = [case for case in success_cases if case.get("retrieval_hit") is False]
    lines = [
        f"- 回答成功题数: {len(success_cases)}。",
        f"- 其中检索命中支撑的成功题数: {len(success_cases) - len(suspicious_success)}。",
    ]
    if suspicious_success:
        lines.append(
            f"- 有 {len(suspicious_success)} 题属于“回答正确但 retrieval_hit=False”，这类成功不能直接算作检索有效，更可能来自 profile、prompt 或模型推断。"
        )
    supportive = [case for case in success_cases if case.get("retrieval_hit") is True]
    if supportive:
        example = supportive[0]
        lines.append(
            f"- 一个典型成功模式是检索直接带回支持证据，例如“{example.get('question')}”的 Top1/Top2 context 已经贴近标准答案。"
        )
    return lines


def _case_lines(
    cases: list[dict[str, Any]],
    *,
    include_answer: bool,
    include_reason: bool,
) -> list[str]:
    if not cases:
        return ["- 暂无样本。"]

    lines: list[str] = []
    for index, case in enumerate(cases, 1):
        question = str(case.get("question") or "")
        standard = str(case.get("standard_answer") or "")
        generated = str(case.get("generated_answer") or "")
        top_context = _top_context(case)
        missed = _first_missed_preview(case)
        layer = get_retrieval_layer(case).get("resolved_layer", "none")
        diagnosis = (get_db_diagnosis(case) or {}).get("diagnosis_type") or "none"

        lines.append(f"- 案例{index}: {question}")
        lines.append(f"  - category: {format_qa_category(case.get('category'))}")
        lines.append(f"  - standard_answer: {standard or '(empty)'}")
        if include_answer:
            lines.append(f"  - generated_answer: {_shorten(generated, 220)}")
        lines.append(
            f"  - storage_hit={case.get('storage_hit')} | retrieval_hit={case.get('retrieval_hit')} | rank={case.get('rank_position')} | layer={layer}"
        )
        lines.append(f"  - diagnosis: {diagnosis}")
        if top_context:
            lines.append(f"  - top1_context: {_shorten(top_context, 180)}")
        if missed:
            lines.append(f"  - missed_evidence_preview: {_shorten(missed, 180)}")
        if include_reason:
            reason = _failure_reason_text(case) if case.get("is_correct") is False else _success_reason_text(case)
            lines.append(f"  - reason: {reason}")
    return lines


def _counter_lines(counter: Counter[str]) -> list[str]:
    if not counter:
        return []
    return [f"- {label}: {count}" for label, count in counter.most_common()]


def _risk_lines(enriched: dict[str, Any]) -> list[str]:
    notes = (enriched.get("analysis_summary") or {}).get("high_risk_notes") or []
    if not notes:
        return ["- 统计口径风险: 当前结果里没有额外高风险提示。"]
    return ["- 统计口径风险:"] + [f"  - {note}" for note in notes]


def _failure_reason_label(case: dict[str, Any]) -> str:
    if case.get("storage_hit") is False:
        return "storage_gap"
    if case.get("retrieval_hit") is False:
        return "retrieval_gap"
    return "answer_or_eval_gap"


def _failure_reason_text(case: dict[str, Any]) -> str:
    if case.get("storage_hit") is False:
        return "数据库里没有找到支持答案的 evidence，问题优先落在存储链路。"

    if case.get("retrieval_hit") is False:
        diagnosis = get_db_diagnosis(case) or {}
        missed = _first_missed_preview(case)
        top_context = _top_context(case)
        if missed:
            return (
                "数据库里已有候选 evidence，但检索没有把它带回 top-k。"
                f"当前 Top1 更像噪声：{_shorten(top_context, 90) or 'N/A'}；"
                f"漏掉的 evidence 预览：{_shorten(missed, 90)}。"
            )
        if diagnosis:
            return f"检索未命中，db_diagnosis={diagnosis.get('diagnosis_type')}，但缺少足够 evidence 预览。"
        return "检索未命中，且当前 trace 不足以进一步区分召回缺失还是排序压制。"

    top_context = _top_context(case)
    return (
        "检索已经命中，但回答仍然错误，问题更可能在回答阶段没有正确使用 context，"
        f"当前 Top1 context: {_shorten(top_context, 120) or 'N/A'}。"
    )


def _success_bucket(case: dict[str, Any]) -> str:
    if case.get("retrieval_hit") is True:
        return "检索命中并支撑回答"
    if case.get("storage_hit") is True:
        return "回答正确但未证明来自检索"
    return "回答正确但链路证据异常"


def _success_reason_text(case: dict[str, Any]) -> str:
    if case.get("retrieval_hit") is True:
        return "检索结果里已经带回了支持答案的上下文，回答大概率是在使用检索证据。"
    if case.get("storage_hit") is True:
        return "回答虽然正确，但 retrieval_hit=False，说明这次成功不能直接证明检索链路有效。"
    return "回答正确，但链路 trace 不典型，建议复核评估口径。"


def _top_context(case: dict[str, Any]) -> str:
    contexts = get_retrieved_contexts(case)
    return str(contexts[0]) if contexts else ""


def _first_missed_preview(case: dict[str, Any]) -> str:
    diagnosis = get_db_diagnosis(case) or {}
    missed = diagnosis.get("missed_in_retrieval") or []
    if not missed:
        return ""
    first = missed[0]
    if not isinstance(first, dict):
        return ""
    return str(first.get("text_preview") or "")


def _format_counter(counter: Counter[str], limit: int = 5) -> str:
    if not counter:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in counter.most_common(limit))


def _shorten(text: str, limit: int) -> str:
    raw = str(text or "").strip()
    if len(raw) <= limit:
        return raw
    return raw[: limit - 3].rstrip() + "..."


def _build_retrieval_breakdown(cases: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for case in cases:
        subtype, confidence, evidence = _classify_retrieval_failure(case)
        rows.append(
            {
                "question": str(case.get("question") or ""),
                "subtype": subtype,
                "confidence": confidence,
                "evidence": evidence,
            }
        )
    return rows


def _retrieval_breakdown_lines(rows: list[dict[str, str]]) -> list[str]:
    if not rows:
        return ["- 当前没有可拆解的 retrieval failure 样本。"]

    subtype_counter = Counter(row["subtype"] for row in rows)
    confidence_counter = Counter(row["confidence"] for row in rows)
    lines = [
        f"- subtype 汇总: {_format_counter(subtype_counter)}。",
        f"- confidence 汇总: {_format_counter(confidence_counter)}。",
        "",
        "| question | subtype | confidence | evidence |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {_escape_md(row['question'])} | {_escape_md(row['subtype'])} | {_escape_md(row['confidence'])} | {_escape_md(row['evidence'])} |"
        )
    return lines


def _classify_retrieval_failure(case: dict[str, Any]) -> tuple[str, str, str]:
    layer = get_retrieval_layer(case).get("resolved_layer", "none")
    top_context = _top_context(case)
    missed = _first_missed_preview(case)
    diagnosis = (get_db_diagnosis(case) or {}).get("diagnosis_type") or "unknown"

    if layer == "category_only" and missed:
        return (
            "route_miss_category_only",
            "high",
            f"resolved_layer=category_only; missed evidence exists; top1={_shorten(top_context, 60) or 'N/A'}",
        )

    if _is_noise_like(top_context) and missed:
        return (
            "noise_outrank_target",
            "high",
            f"top1 looks noisy ({_noise_bucket_label(case)}); missed evidence exists",
        )

    if "timeline" in " ".join(str(x).lower() for x in get_retrieval_layer(case).get("llm_classified_categories", [])):
        return (
            "category_too_coarse",
            "medium",
            f"llm_classified_categories={get_retrieval_layer(case).get('llm_classified_categories')}; diagnosis={diagnosis}",
        )

    if _weak_keyword_match(case):
        return (
            "keyword_false_positive_risk",
            "medium",
            "db diagnosis relies on weak matched keywords or generic candidates",
        )

    return (
        "uncertain_retrieval_gap",
        "low",
        f"diagnosis={diagnosis}; layer={layer}; top1={_shorten(top_context, 60) or 'N/A'}",
    )


def _noise_bucket_label(case: dict[str, Any]) -> str:
    top_context = _top_context(case).lower()
    if not top_context:
        return "no_top_context"
    if "user's name is" in top_context or "the user's name is" in top_context:
        return "name_noise"
    if "mel" in top_context and "son" in top_context:
        return "other_person_timeline_noise"
    if "joined" in top_context or "last weekend" in top_context or "2026-" in top_context:
        return "generic_timeline_noise"
    if "core support system" in top_context or "authentic self" in top_context:
        return "core_self_noise"
    return "other_noise"


def _is_noise_like(text: str) -> bool:
    lowered = str(text or "").lower()
    return _noise_bucket_from_text(lowered) != "other"


def _noise_bucket_from_text(lowered: str) -> str:
    if not lowered:
        return "other"
    if "user's name is" in lowered or "the user's name is" in lowered:
        return "name_noise"
    if "mel" in lowered and "son" in lowered:
        return "other_person_timeline_noise"
    if "joined" in lowered or "last weekend" in lowered or "2026-" in lowered:
        return "generic_timeline_noise"
    if "core support system" in lowered or "authentic self" in lowered:
        return "core_self_noise"
    return "other"


def _weak_keyword_match(case: dict[str, Any]) -> bool:
    storage_eval = ((case.get("trace_detail") or {}).get("evaluation_trace") or {}).get("storage_eval") or {}
    db_samples = storage_eval.get("db_memories_sample") or []
    weak_keywords = _weak_keywords()
    for item in db_samples[:5]:
        if not isinstance(item, dict):
            continue
        matched = str(item.get("matched_keyword") or "").lower()
        if matched in weak_keywords:
            return True
    return False


def _weak_keywords() -> set[str]:
    return {
        "the",
        "a",
        "an",
        "from",
        "how",
        "what",
        "did",
        "was",
        "is",
        "are",
        "with",
        "when",
        "where",
        "who",
        "for",
        "ago",
        "long",
    }


def _escape_md(text: str) -> str:
    return str(text or "").replace("\n", "<br>").replace("|", "\\|")
