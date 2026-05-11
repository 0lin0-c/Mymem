from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
) -> dict[str, Any]:
    all_results = list(report.results)
    data = {
        "test_info": {
            "dataset": "bowen-upenn/PersonaMem-v2",
            "harness": CANDIDATE_HARNESS,
            "eval_mode": eval_mode,
            **(test_info or {}),
        },
        "statistics": calculate_metrics(all_results, eval_mode=eval_mode),
        "samples": [_report_to_dict(report)],
    }
    return add_personamem_statistics(data)


def save_candidate_results_json(
    report: PersonaMemReport,
    output_path: Path,
    *,
    eval_mode: str,
    test_info: dict[str, Any] | None = None,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = build_candidate_results_data(report, eval_mode=eval_mode, test_info=test_info)
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
) -> tuple[Path, Path]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = build_candidate_results_data(report, eval_mode=eval_mode, test_info=test_info)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    analysis_path = save_candidate_analysis_markdown(data, output_path)
    return output_path, analysis_path
