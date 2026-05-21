from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tests.evals.common import build_run_manifest, finalize_run_manifest, stable_file_hash, stable_payload_hash
from tests.evals.personamem_v2.report_contract import mark_report_contract, validate_personamem_report_contract
from tests.evals.personamem_v2.reporting import build_paired_comparison


FOCUS_MODELS = ["GLM-5.1", "DeepSeek-V4-Pro", "Qwen3.5-Plus", "GLM-5-Turbo"]


def build_official_persona66_summary(
    result_paths: list[Path],
    *,
    output_dir: Path,
    baseline_model: str = "GLM-5.1",
    require_focus_models: bool = False,
) -> dict[str, Any]:
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in result_paths]
    model_reports = [_model_report(report, path) for report, path in zip(reports, result_paths, strict=True)]
    _validate_official_model_reports(model_reports, require_focus_models=require_focus_models)
    by_model = {item["chat_model"]: item for item in model_reports}
    baseline = by_model.get(baseline_model) or (model_reports[0] if model_reports else None)
    pairwise = []
    if baseline:
        baseline_rows = _qa_results(baseline["raw_report"])
        for item in model_reports:
            if item["chat_model"] == baseline["chat_model"]:
                continue
            pairwise.append(
                {
                    "baseline_model": baseline["chat_model"],
                    "candidate_model": item["chat_model"],
                    "changed_variables": [
                        "writer",
                        "retrieval_classifier",
                        "retrieval",
                        "generator",
                    ],
                    "formal_ab_eligible": False,
                    "diagnostic_reason": (
                        "single-model official reruns provide evidence-first metrics, "
                        "but cross-model pairwise comparison still changes multiple layers"
                    ),
                    "paired_comparison": build_paired_comparison(baseline_rows, _qa_results(item["raw_report"])),
                }
            )
            paired = pairwise[-1]["paired_comparison"]
            if paired.get("shared_questions") != min(len(baseline_rows), len(_qa_results(item["raw_report"]))):
                raise ValueError(
                    "Official summary pairwise comparison did not cover all shared questions: "
                    f"{baseline['chat_model']} vs {item['chat_model']}"
                )

    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "test_info": {
            "harness": "personamem_v2_official_persona66_summary",
            "persona_id": "66",
            "focus_models": FOCUS_MODELS,
            "baseline_model": baseline["chat_model"] if baseline else None,
            "formal_ab_eligible": False,
            "diagnostic_reason": (
                "This summary aggregates independent official evidence-first reruns. "
                "Use orthogonal replay reports for layer-isolated A/B decisions."
            ),
        },
        "models": [
            {key: value for key, value in item.items() if key != "raw_report"}
            for item in model_reports
        ],
        "pairwise_comparisons": pairwise,
    }
    payload["run_manifest"] = build_run_manifest(
        harness="personamem_v2_official_persona66_summary",
        eval_mode="assistant_eval",
        dataset="bowen-upenn/PersonaMem-v2",
        split="benchmark_text",
        persona_id="66",
        question_count=sum(item["question_count"] for item in model_reports),
        import_only=False,
        retrieval_only=True,
        reset_memory=False,
        chat_model="per_model_official_rerun",
        evaluator_model=_common_evaluator(model_reports),
        evaluator_isolated=True,
        top_k=_common_top_k(model_reports),
        scoring_config=None,
        rerank_config=None,
        db_snapshot_id=stable_payload_hash([item["db_snapshot_id"] for item in model_reports]),
        dataset_hash=stable_payload_hash([item["dataset_hash"] for item in model_reports]),
        cache_hash=stable_payload_hash([stable_file_hash(path) for path in result_paths]),
        temperature=_common_temperature(model_reports),
        extra={
            "result_files": [str(path) for path in result_paths],
            "source_result_hashes": {str(path): stable_file_hash(path) for path in result_paths},
        },
    )
    output_path = output_dir / "personamem_v2_persona66_official_summary.json"
    finalize_run_manifest(payload["run_manifest"], result_file_path=output_path)
    mark_report_contract(payload)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path = output_path.with_suffix(".md")
    markdown_path.write_text(render_official_summary_markdown(payload), encoding="utf-8")
    payload["json_path"] = str(output_path)
    payload["markdown_path"] = str(markdown_path)
    return payload


def render_official_summary_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# PersonaMem-v2 Persona66 Official Evidence-First Rerun",
        "",
        "## Scope",
        f"- Harness: `{payload.get('test_info', {}).get('harness')}`",
        f"- Formal A/B eligible: `{payload.get('test_info', {}).get('formal_ab_eligible')}`",
        f"- Diagnostic reason: {payload.get('test_info', {}).get('diagnostic_reason')}",
        "",
        "## Model Metrics",
        "| model | questions | answerable@k | anchor@k | wrong-neighbor | not-retrieved | accuracy | result |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for item in payload.get("models", []):
        primary = item.get("primary_metrics") or {}
        lines.append(
            "| "
            f"{item.get('chat_model')} | "
            f"{item.get('question_count')} | "
            f"{_pct(primary.get('answerable_context_hit_at_k'))} | "
            f"{_pct(primary.get('target_answer_anchor_hit_at_k'))} | "
            f"{_pct(primary.get('wrong_neighbor_substitution_rate'))} | "
            f"{_pct(primary.get('target_evidence_not_retrieved_rate'))} | "
            f"{_pct(primary.get('accuracy'))} | "
            f"`{item.get('result_file_path')}` |"
        )
    lines.extend(["", "## Pairwise Diagnostics"])
    for item in payload.get("pairwise_comparisons", []):
        paired = item.get("paired_comparison") or {}
        lines.append(
            "- "
            f"`{item.get('candidate_model')}` vs `{item.get('baseline_model')}`: "
            f"answer win/loss={paired.get('gain')}/{paired.get('regression')}, "
            f"evidence win/loss={paired.get('evidence_gain')}/{paired.get('evidence_regression')}, "
            f"formal_ab_eligible=`{item.get('formal_ab_eligible')}`"
        )
    return "\n".join(lines) + "\n"


def _model_report(report: dict[str, Any], path: Path) -> dict[str, Any]:
    manifest = report.get("run_manifest") or {}
    stats = report.get("statistics") or {}
    evidence = stats.get("personamem_evidence") or {}
    primary = (
        evidence.get("evidence_first_summary", {})
        .get("primary_metrics", {})
    )
    return {
        "chat_model": manifest.get("chat_model") or (report.get("test_info") or {}).get("chat_model"),
        "evaluator_model": manifest.get("evaluator_model"),
        "db_snapshot_id": manifest.get("db_snapshot_id"),
        "dataset_hash": manifest.get("dataset_hash"),
        "cache_hash": manifest.get("cache_hash"),
        "temperature": manifest.get("temperature"),
        "top_k": manifest.get("top_k"),
        "question_count": manifest.get("question_count") or stats.get("total_questions") or len(_qa_results(report)),
        "result_file_path": manifest.get("result_file_path") or str(path),
        "run_manifest": manifest,
        "primary_metrics": primary,
        "bucket_report": stats.get("bucket_report") or {},
        "raw_report": report,
    }


def _validate_official_model_reports(
    model_reports: list[dict[str, Any]],
    *,
    require_focus_models: bool,
) -> None:
    if not model_reports:
        raise ValueError("Official persona66 summary requires at least one result file.")
    seen_models = set()
    for item in model_reports:
        model = item.get("chat_model")
        if not model:
            raise ValueError(f"Official result is missing chat_model: {item.get('result_file_path')}")
        if model in seen_models:
            raise ValueError(f"Duplicate official result for chat_model={model}")
        seen_models.add(model)
        manifest = item.get("run_manifest") or {}
        if manifest.get("persona_id") not in {"66", 66, None}:
            raise ValueError(f"Official persona66 result has wrong persona_id: {manifest.get('persona_id')}")
        if manifest.get("eval_mode") not in {"assistant_eval", None}:
            raise ValueError(f"Official persona66 result has wrong eval_mode: {manifest.get('eval_mode')}")
        qa_count = len(_qa_results(item["raw_report"]))
        if qa_count <= 0:
            raise ValueError(f"Official result has no QA rows: {item.get('result_file_path')}")
        if item.get("question_count") != qa_count:
            raise ValueError(
                "Official result question_count mismatch: "
                f"model={model} manifest={item.get('question_count')} actual={qa_count}"
            )
        contract = validate_personamem_report_contract(item["raw_report"])
        if not contract["valid"]:
            raise ValueError(
                "Official result does not satisfy evidence-first report contract: "
                f"model={model} issues={','.join(contract['issues'])}"
            )
    if require_focus_models:
        missing = sorted(set(FOCUS_MODELS) - seen_models)
        if missing:
            raise ValueError(f"Official summary missing focus models: {','.join(missing)}")


def _qa_results(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        qa
        for sample in report.get("samples", [])
        for qa in sample.get("qa_results", [])
    ]


def _common_evaluator(model_reports: list[dict[str, Any]]) -> str | None:
    values = {item.get("evaluator_model") for item in model_reports if item.get("evaluator_model")}
    return next(iter(values)) if len(values) == 1 else None


def _common_top_k(model_reports: list[dict[str, Any]]) -> int | None:
    values = {item.get("top_k") for item in model_reports if item.get("top_k") is not None}
    return next(iter(values)) if len(values) == 1 else None


def _common_temperature(model_reports: list[dict[str, Any]]) -> float | int | None:
    values = {item.get("temperature") for item in model_reports if item.get("temperature") is not None}
    return next(iter(values)) if len(values) == 1 else None


def _pct(value: Any) -> str:
    return f"{float(value or 0):.2f}%"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize official PersonaMem-v2 persona66 reruns.")
    parser.add_argument("results", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--baseline-model", default="GLM-5.1")
    parser.add_argument(
        "--require-focus-models",
        action="store_true",
        help="Require GLM-5.1, DeepSeek-V4-Pro, Qwen3.5-Plus, and GLM-5-Turbo inputs.",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    payload = build_official_persona66_summary(
        args.results,
        output_dir=args.output_dir,
        baseline_model=args.baseline_model,
        require_focus_models=args.require_focus_models,
    )
    print(payload["json_path"])
    print(payload["markdown_path"])


if __name__ == "__main__":
    main()
