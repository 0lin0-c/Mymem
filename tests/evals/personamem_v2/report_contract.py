from __future__ import annotations

from pathlib import Path
from typing import Any


REQUIRED_EVIDENCE_PRIMARY_METRICS = {
    "answerable_context_hit_at_k",
    "target_preference_hit_at_k",
    "target_answer_anchor_hit_at_k",
    "wrong_neighbor_substitution_rate",
    "target_evidence_not_retrieved_rate",
    "accuracy",
}

REQUIRED_RUN_MANIFEST_FIELDS = {
    "git_sha",
    "db_snapshot_id",
    "dataset_hash",
    "result_file_path",
    "chat_model",
    "embedding_model",
    "evaluator_model",
    "temperature",
    "top_k",
    "scoring_config",
    "rerank_config",
    "cache_hash",
    "started_at",
    "finished_at",
    "duration_seconds",
    "result_schema_version",
}

REQUIRED_NONEMPTY_RUN_MANIFEST_FIELDS = {
    "db_snapshot_id",
    "dataset_hash",
    "result_file_path",
    "chat_model",
    "embedding_model",
    "evaluator_model",
    "temperature",
    "top_k",
    "cache_hash",
    "started_at",
    "finished_at",
    "result_schema_version",
}

REQUIRED_EVAL_BUCKETS = {
    "exact_fact",
    "broad_advice",
    "negative_constraint",
    "sensitive_info",
    "third_person_narrative",
    "quoted_artifact",
    "forget_request",
    "time_date_question",
}

OFFICIAL_RESULT_EXTENSIONS = {".json", ".md"}
DIAGNOSTIC_ARTIFACT_EXTENSIONS = {".log", ".pid", ".txt", ".out", ".err"}


def validate_personamem_report_contract(
    report: dict[str, Any],
    *,
    require_formal_ab: bool = False,
    require_all_buckets: bool = False,
) -> dict[str, Any]:
    """Validate the evidence-first report shape used for PersonaMem decisions.

    This is a structural gate, not a quality score. It prevents reports that only
    expose final accuracy from being treated as formal A/B evidence.
    """
    issues: list[str] = []
    manifest = report.get("run_manifest")
    if not isinstance(manifest, dict):
        issues.append("missing_run_manifest")
        manifest = {}
    else:
        _require_fields(
            manifest,
            REQUIRED_RUN_MANIFEST_FIELDS,
            issues,
            prefix="run_manifest",
        )
        _require_nonempty_fields(
            manifest,
            REQUIRED_NONEMPTY_RUN_MANIFEST_FIELDS,
            issues,
            prefix="run_manifest",
        )
        if manifest.get("duration_seconds") is None:
            issues.append("run_manifest.duration_seconds_missing")
        elif float(manifest.get("duration_seconds") or 0) <= 0:
            issues.append("run_manifest.duration_seconds_not_positive")

    statistics = report.get("statistics") or {}
    evidence = statistics.get("personamem_evidence") or report.get("personamem_evidence") or {}
    primary = (
        evidence.get("evidence_first_summary", {})
        .get("primary_metrics", {})
    )
    if not isinstance(primary, dict):
        primary = {}
    _require_fields(
        primary,
        REQUIRED_EVIDENCE_PRIMARY_METRICS,
        issues,
        prefix="primary_metrics",
    )

    if not _has_stage_payloads(report):
        issues.append("missing_row_level_retrieval_and_answer_stage_payloads")

    bucket_report = statistics.get("bucket_report") or report.get("bucket_report") or {}
    if not isinstance(bucket_report, dict):
        issues.append("bucket_report_not_object")
        bucket_report = {}
    if require_all_buckets:
        missing = sorted(REQUIRED_EVAL_BUCKETS - set(bucket_report))
        if missing:
            issues.append(f"bucket_report_missing:{','.join(missing)}")

    if require_formal_ab or _declares_formal_ab(report):
        _validate_formal_ab_payload(report, issues)

    return {
        "valid": not issues,
        "issues": issues,
        "formal_ab_eligible": not issues if require_formal_ab else _declares_formal_ab(report) and not issues,
        "required_primary_metrics": sorted(REQUIRED_EVIDENCE_PRIMARY_METRICS),
        "required_run_manifest_fields": sorted(REQUIRED_RUN_MANIFEST_FIELDS),
        "required_nonempty_run_manifest_fields": sorted(REQUIRED_NONEMPTY_RUN_MANIFEST_FIELDS),
    }


def mark_report_contract(
    report: dict[str, Any],
    *,
    require_formal_ab: bool = False,
    require_all_buckets: bool = False,
) -> dict[str, Any]:
    contract = validate_personamem_report_contract(
        report,
        require_formal_ab=require_formal_ab,
        require_all_buckets=require_all_buckets,
    )
    report["report_contract"] = contract
    if contract["issues"]:
        report["formal_ab_eligible"] = False
        manifest = report.get("run_manifest")
        if isinstance(manifest, dict):
            manifest["formal_ab_eligible"] = False
            manifest["formal_ab_blockers"] = list(contract["issues"])
    return report


def validate_result_artifact_layout(root: str | Path) -> dict[str, Any]:
    """Check that official results are separated from logs and scratch artifacts."""
    root_path = Path(root)
    issues: list[str] = []
    if not root_path.exists():
        return {"valid": False, "issues": ["result_root_missing"], "root": str(root_path)}

    official_dir = root_path / "official"
    legacy_dir = root_path / "legacy"
    diagnostic_dir = root_path / "diagnostic"
    scratch_dir = root_path / "scratch"
    logs_dir = root_path / "logs"
    expected_dirs = {
        "official": official_dir,
        "legacy": legacy_dir,
        "diagnostic": diagnostic_dir,
        "scratch": scratch_dir,
        "logs": logs_dir,
    }
    missing_dirs = [name for name, path in expected_dirs.items() if not path.exists()]
    if missing_dirs:
        issues.append(f"missing_result_subdirs:{','.join(sorted(missing_dirs))}")

    if official_dir.exists():
        for path in official_dir.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in OFFICIAL_RESULT_EXTENSIONS:
                issues.append(f"non_report_artifact_in_official:{path.name}")
            if path.suffix.lower() in DIAGNOSTIC_ARTIFACT_EXTENSIONS:
                issues.append(f"diagnostic_artifact_in_official:{path.name}")
    return {
        "valid": not issues,
        "issues": issues,
        "root": str(root_path),
        "expected_subdirs": sorted(expected_dirs),
    }


def recommended_result_subdir(*, official: bool = False, diagnostic: bool = False, legacy: bool = False) -> str:
    selected = [official, diagnostic, legacy]
    if sum(bool(item) for item in selected) > 1:
        raise ValueError("Only one result class can be selected.")
    if official:
        return "official"
    if diagnostic:
        return "diagnostic"
    if legacy:
        return "legacy"
    return "scratch"


def _require_fields(value: dict[str, Any], required: set[str], issues: list[str], *, prefix: str) -> None:
    for field in sorted(required - set(value)):
        issues.append(f"{prefix}.{field}_missing")


def _require_nonempty_fields(value: dict[str, Any], required: set[str], issues: list[str], *, prefix: str) -> None:
    for field in sorted(required & set(value)):
        current = value.get(field)
        if current is None or current == "":
            issues.append(f"{prefix}.{field}_empty")


def _has_stage_payloads(report: dict[str, Any]) -> bool:
    samples = report.get("samples") or []
    for sample in samples:
        for row in sample.get("qa_results") or []:
            retrieval_stage = row.get("retrieval_stage")
            answer_stage = row.get("answer_stage")
            if isinstance(retrieval_stage, dict) and isinstance(answer_stage, dict):
                return True
    return False


def _declares_formal_ab(report: dict[str, Any]) -> bool:
    if report.get("formal_ab_eligible") is True:
        return True
    manifest = report.get("run_manifest") or {}
    if isinstance(manifest, dict) and manifest.get("formal_ab_eligible") is True:
        return True
    return False


def _validate_formal_ab_payload(report: dict[str, Any], issues: list[str]) -> None:
    paired = report.get("paired_comparison")
    if paired is None and report.get("pairwise_comparisons"):
        paired = report["pairwise_comparisons"][0].get("paired_comparison")
    if not isinstance(paired, dict):
        issues.append("formal_ab_missing_paired_comparison")
        return
    if not paired.get("statistical_confidence"):
        issues.append("formal_ab_missing_statistical_confidence")
    if not paired.get("per_row"):
        issues.append("formal_ab_missing_per_row_win_loss")
    changed_layers = report.get("changed_layer") or report.get("changed_variables")
    if isinstance(changed_layers, str):
        changed_layers = [changed_layers]
    if changed_layers and len({str(item) for item in changed_layers}) != 1:
        issues.append("formal_ab_changes_multiple_layers")
