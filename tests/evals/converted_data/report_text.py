from __future__ import annotations

from typing import Any

from tests.evals.converted_data.categories import format_qa_category
from tests.evals.converted_data.metrics import calculate_metrics


def generate_console_report(report: Any, eval_mode: str | None = None) -> str:
    metrics = calculate_metrics(report.results, eval_mode=eval_mode)
    mode = eval_mode or _infer_mode(report)

    if mode == "storage_eval":
        return _storage_console_report(report, metrics)
    if mode == "retrieval_eval":
        return _retrieval_console_report(report, metrics)
    return _assistant_console_report(report, metrics)


def generate_overall_console_report(metrics: dict[str, Any], eval_mode: str | None = None) -> str:
    mode = eval_mode or "assistant_eval"
    lines = ["=" * 70, "总体测试报告", "=" * 70]
    lines.append(f"总测试问题数: {metrics.get('total_questions', 0)}")

    if mode == "storage_eval":
        lines.append(
            f"Storage coverage: {metrics.get('storage_coverage_rate', 0):.1f}% "
            f"({metrics.get('storage_hit_count', 0)}/{metrics.get('total_questions', 0)})"
        )
    elif mode == "retrieval_eval":
        lines.append(
            f"Recall@K: {metrics.get('recall_at_k', 0):.1f}% "
            f"({metrics.get('retrieval_hit_count', 0)}/{metrics.get('total_questions', 0)})"
        )
        lines.append(
            f"Top1/Top3/Top5: {metrics.get('top1_hit_rate', 0):.1f}% / "
            f"{metrics.get('top3_hit_rate', 0):.1f}% / {metrics.get('top5_hit_rate', 0):.1f}%"
        )
    else:
        lines.append(
            f"Answer accuracy: {metrics.get('answer_accuracy', metrics.get('accuracy', 0)):.1f}% "
            f"({metrics.get('correct_count', 0)}/{metrics.get('evaluated_questions', 0)})"
        )
        lines.append(f"Adjusted accuracy: {metrics.get('adjusted_accuracy_excluding_empty_standard', 0):.1f}%")
        lines.append(f"Retrieval support rate: {metrics.get('retrieval_support_rate', 0):.1f}%")
        if metrics.get("answer_support_counts"):
            support_text = ", ".join(
                f"{name}={count}" for name, count in sorted(metrics["answer_support_counts"].items())
            )
            lines.append(f"Answer support types: {support_text}")

    if metrics.get("layer_distribution"):
        lines.extend(["", "--- 检索层级分布 ---"])
        for layer, info in sorted(metrics["layer_distribution"].items()):
            hit_rate = info.get("recall_at_k", info.get("accuracy", 0))
            lines.append(f"  {layer}: {info.get('count', 0)}题, rate {hit_rate:.1f}%")

    return "\n".join(lines)


def _infer_mode(report: Any) -> str:
    for result in getattr(report, "results", []):
        if getattr(result, "eval_mode", None):
            return result.eval_mode
    return "assistant_eval"


def _header(report: Any, title: str) -> list[str]:
    return [
        "=" * 70,
        f"{title} - Sample {report.sample_index} ({report.character})",
        "=" * 70,
        f"用户 ID: {report.user_id}",
        f"导入会话数: {report.total_sessions}",
        f"创建记忆数: {report.total_memories}",
        f"测试问题数: {report.total_questions}",
        "",
    ]


def _storage_console_report(report: Any, metrics: dict[str, Any]) -> str:
    lines = _header(report, "Storage Evaluation Report")
    lines.extend([
        "--- 存储指标 ---",
        f"Storage coverage: {metrics['storage_coverage_rate']:.1f}% ({metrics['storage_hit_count']}/{metrics['total_questions']})",
        "",
        "--- 详细结果（前10） ---",
    ])
    for idx, result in enumerate(report.results[:10], 1):
        lines.append(f"[{idx}] Q: {result.question}")
        lines.append(f"    storage_hit: {result.storage_hit}  category: {format_qa_category(result.category)}")
        if result.db_diagnosis:
            lines.append(f"    diagnosis: {result.db_diagnosis.get('diagnosis_type')}")
    return "\n".join(lines)


def _retrieval_console_report(report: Any, metrics: dict[str, Any]) -> str:
    lines = _header(report, "Retrieval Evaluation Report")
    lines.extend([
        "--- 检索指标 ---",
        f"Recall@K: {metrics['recall_at_k']:.1f}% ({metrics['retrieval_hit_count']}/{metrics['total_questions']})",
        f"Top1/Top3/Top5: {metrics['top1_hit_rate']:.1f}% / {metrics['top3_hit_rate']:.1f}% / {metrics['top5_hit_rate']:.1f}%",
        f"Mean first evidence rank: {metrics['mean_first_evidence_rank']:.2f}",
        f"平均检索分数: {metrics['avg_retrieval_score']:.3f}",
        "",
        "--- 检索层级分布 ---",
    ])
    for layer, info in sorted(metrics["layer_distribution"].items()):
        lines.append(f"  {layer}: {info['count']}题 recall {info['recall_at_k']:.1f}%")
    lines.extend(["", "--- 详细结果（前10） ---"])
    for idx, result in enumerate(report.results[:10], 1):
        lines.append(f"[{idx}] Q: {result.question}")
        lines.append(
            f"    retrieval_hit: {result.retrieval_hit}  rank: {result.rank_position}  layer: {result.retrieval_layer.resolved_layer}"
        )
        if result.retrieved_contexts:
            lines.append(f"    top1: {result.retrieved_contexts[0][:100]}")
    return "\n".join(lines)


def _assistant_console_report(report: Any, metrics: dict[str, Any]) -> str:
    lines = _header(report, "Assistant Evaluation Report")
    lines.extend([
        "--- 回答指标 ---",
        f"Answer accuracy: {metrics['answer_accuracy']:.1f}% ({metrics['correct_count']}/{metrics['evaluated_questions']})",
        f"Adjusted accuracy: {metrics['adjusted_accuracy_excluding_empty_standard']:.1f}%",
        f"Retrieval support rate: {metrics['retrieval_support_rate']:.1f}% ({metrics['retrieval_hit_count']}/{metrics['total_questions']})",
        "Answer support types: " + ", ".join(
            f"{name}={count}" for name, count in sorted(metrics.get("answer_support_counts", {}).items())
        ),
        "",
        "--- 详细结果（前10） ---",
    ])
    for idx, result in enumerate(report.results[:10], 1):
        correct_mark = "✓" if result.is_correct is True else ("✗" if result.is_correct is False else "?")
        lines.append(f"[{idx}] Q: {result.question}")
        lines.append(f"    标准答案: {result.expected_answer}")
        lines.append(f"    LLM回答: {(result.llm_answer or 'N/A')[:100]}")
        lines.append(
            f"    正确: {correct_mark}  retrieval_hit: {result.retrieval_hit}  层级: {result.retrieval_layer.resolved_layer}  category: {format_qa_category(result.category)}"
        )
    return "\n".join(lines)
