from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.evals.common import build_run_manifest, default_scoring_config_payload
from tests.evals.converted_data.metrics import calculate_metrics
from tests.evals.personamem_v2.analysis import build_personamem_analysis_markdown
from tests.evals.personamem_v2.models import PersonaMemReport
from tests.evals.personamem_v2.reporting import add_personamem_statistics, _report_to_dict


CANDIDATE_HARNESS = "personamem_v2_candidate_view_structured_projection"


def build_candidate_results_data(
    report: PersonaMemReport,
    *,
    eval_mode: str,
    test_info: dict[str, Any] | None = None,
    run_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    all_results = list(report.results)
    info = test_info or {}
    data = {
        "test_info": {
            "dataset": "bowen-upenn/PersonaMem-v2",
            "harness": CANDIDATE_HARNESS,
            "eval_mode": eval_mode,
            **info,
        },
        "statistics": calculate_metrics(all_results, eval_mode=eval_mode),
        "samples": [_report_to_dict(report)],
        "run_manifest": run_manifest
        or build_run_manifest(
            harness=CANDIDATE_HARNESS,
            eval_mode=eval_mode,
            dataset="bowen-upenn/PersonaMem-v2",
            split=info.get("split"),
            persona_id=str(report.character),
            question_count=len(all_results),
            import_only=info.get("import_only"),
            retrieval_only=info.get("retrieval_only"),
            reset_memory=info.get("reset_memory"),
            chat_model=report.chat_model or info.get("chat_model"),
            evaluator_model=report.evaluator_model or info.get("evaluator_model"),
            evaluator_isolated=report.evaluator_isolated,
            top_k=info.get("top_k"),
            scoring_config=info.get("scoring_config") or default_scoring_config_payload(),
            rerank_config=info.get("rerank_config"),
        ),
    }
    return add_personamem_statistics(data)


def save_candidate_results_json(
    report: PersonaMemReport,
    output_path: Path,
    *,
    eval_mode: str,
    test_info: dict[str, Any] | None = None,
    run_manifest: dict[str, Any] | None = None,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = build_candidate_results_data(
        report,
        eval_mode=eval_mode,
        test_info=test_info,
        run_manifest=run_manifest,
    )
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def save_candidate_analysis_markdown(
    results_data: dict[str, Any],
    results_path: Path,
) -> Path:
    analysis_path = results_path.with_name(f"{results_path.stem}_analysis.md")
    analysis_path.write_text(
        build_personamem_analysis_markdown(results_data, results_path.name),
        encoding="utf-8",
    )
    return analysis_path


def save_candidate_detailed_report(
    report: PersonaMemReport,
    output_path: Path,
    *,
    eval_mode: str,
    test_info: dict[str, Any] | None = None,
    run_manifest: dict[str, Any] | None = None,
) -> tuple[Path, Path]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = build_candidate_results_data(
        report,
        eval_mode=eval_mode,
        test_info=test_info,
        run_manifest=run_manifest,
    )
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    analysis_path = save_candidate_analysis_markdown(data, output_path)
    return output_path, analysis_path
