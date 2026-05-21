from __future__ import annotations

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from tests.evals.common import build_run_manifest, finalize_run_manifest, stable_payload_hash, utc_now_iso
from tests.evals.personamem_v2.answer_bearing_rerank import rerank_answer_bearing_contexts
from tests.evals.personamem_v2.analysis import analyze_personamem_evidence
from tests.evals.personamem_v2.reporting import (
    build_paired_comparison,
    build_personamem_statistics_from_qa_results,
    determine_experiment_conclusion,
)
from tests.evals.personamem_v2.report_contract import mark_report_contract


OUTPUT_DIR = Path("test_results") / "personamem_v2_orthogonal"
EXPERIMENT_TYPES = {
    "writer_ab",
    "retrieval_ab",
    "rerank_ab",
    "generator_ab",
    "e2e_diagnostic",
}
LAYER_BY_EXPERIMENT = {
    "writer_ab": "writer",
    "retrieval_ab": "retrieval",
    "rerank_ab": "rerank",
    "generator_ab": "generator",
    "e2e_diagnostic": "e2e",
}
REQUIRED_CONTROLLED_LAYERS = {
    "writer_ab": {"retrieval", "generator", "evaluator"},
    "retrieval_ab": {"storage", "generator", "evaluator"},
    "rerank_ab": {"storage", "retrieval_candidates", "generator", "evaluator"},
    "generator_ab": {"storage", "answer_context", "evaluator"},
}
REQUIRED_REPLAY_SNAPSHOT = {
    "retrieval_ab": "storage_snapshot",
    "rerank_ab": "retrieval_snapshot",
    "generator_ab": "context_snapshot",
}
ALLOWED_TOP_LEVEL_KEYS = {
    "writer_ab": {
        "allow_diagnostic",
        "baseline_variant",
        "candidate_variant",
        "changed_layer",
        "changed_layers",
        "controlled_layers",
        "experiment_type",
        "orthogonal_mode",
        "persona_id",
        "writer_config",
        "writer_model",
    },
    "retrieval_ab": {
        "allow_diagnostic",
        "baseline_variant",
        "candidate_variant",
        "changed_layer",
        "changed_layers",
        "controlled_layers",
        "experiment_type",
        "orthogonal_mode",
        "persona_id",
        "query_route_config",
        "retrieval_config",
        "scoring_config",
        "top_k",
    },
    "rerank_ab": {
        "allow_diagnostic",
        "baseline_variant",
        "candidate_variant",
        "changed_layer",
        "changed_layers",
        "controlled_layers",
        "experiment_type",
        "orthogonal_mode",
        "persona_id",
        "rerank_config",
    },
    "generator_ab": {
        "allow_diagnostic",
        "baseline_variant",
        "candidate_variant",
        "changed_layer",
        "changed_layers",
        "controlled_layers",
        "experiment_type",
        "generator_config",
        "chat_model",
        "orthogonal_mode",
        "persona_id",
    },
    "e2e_diagnostic": set(),
}


def load_json_file(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_json_file(data: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    finalize_run_manifest(data["run_manifest"], result_file_path=path)
    mark_report_contract(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def fingerprint_question_set(qa_results: list[dict[str, Any]]) -> str:
    return _fingerprint([_question_identity(item, index) for index, item in enumerate(qa_results)])


def fingerprint_contexts(qa_results: list[dict[str, Any]]) -> str:
    payload = [
        {
            "question": _question_identity(item, index),
            "contexts": list(item.get("retrieved_contexts") or item.get("answer_contexts") or []),
            "scores": list(item.get("retrieved_scores") or item.get("context_scores") or []),
        }
        for index, item in enumerate(qa_results)
    ]
    return _fingerprint(payload)


def fingerprint_retrieval_candidates(qa_results: list[dict[str, Any]]) -> str:
    payload = []
    for index, item in enumerate(qa_results):
        contexts = list(
            item.get("retrieval_candidate_contexts")
            or item.get("retrieved_contexts")
            or item.get("answer_contexts")
            or []
        )
        scores = list(
            item.get("retrieval_candidate_scores")
            or item.get("retrieved_scores")
            or item.get("context_scores")
            or []
        )
        candidates = [
            {
                "context": context,
                "score": scores[candidate_index] if candidate_index < len(scores) else None,
            }
            for candidate_index, context in enumerate(contexts)
        ]
        payload.append(
            {
                "question": _question_identity(item, index),
                "context_count": len(contexts),
                "score_count": len(scores),
                "candidates": sorted(candidates, key=lambda value: _canonical_json(value)),
            }
        )
    return _fingerprint(payload)


def fingerprint_storage_snapshot(snapshot: dict[str, Any]) -> str:
    return _fingerprint(
        {
            "snapshot_type": snapshot.get("snapshot_type"),
            "db_snapshot_id": snapshot.get("db_snapshot_id"),
            "resources": snapshot.get("resources") or [],
            "categories": snapshot.get("categories") or [],
            "writer_model": snapshot.get("writer_model"),
        }
    )


def build_storage_snapshot(
    *,
    user_id: str | None,
    persona_id: str = "66",
    resources: list[dict[str, Any]] | None = None,
    categories: list[dict[str, Any]] | None = None,
    writer_model: str | None = None,
    db_snapshot_id: str | None = None,
    run_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    snapshot_payload = {
        "snapshot_type": "storage_snapshot",
        "user_id": user_id,
        "persona_id": persona_id,
        "resources": list(resources or []),
        "categories": list(categories or []),
        "writer_model": writer_model,
    }
    resolved_db_snapshot_id = db_snapshot_id or f"storage:{stable_payload_hash(snapshot_payload)[:16]}"
    manifest = run_manifest or _orthogonal_manifest(
        harness="personamem_v2_storage_snapshot",
        persona_id=persona_id,
        db_snapshot_id=resolved_db_snapshot_id,
        dataset_hash=stable_payload_hash(snapshot_payload),
        cache_hash=stable_payload_hash(snapshot_payload),
        chat_model=writer_model,
    )
    return {
        "snapshot_type": "storage_snapshot",
        "db_snapshot_id": resolved_db_snapshot_id,
        "user_id": user_id,
        "persona_id": persona_id,
        "resources": snapshot_payload["resources"],
        "categories": snapshot_payload["categories"],
        "writer_model": writer_model,
        "run_manifest": manifest,
    }


def build_retrieval_snapshot(
    qa_results: list[dict[str, Any]],
    *,
    persona_id: str = "66",
    db_snapshot_id: str | None = None,
    run_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    items = [_normalize_retrieval_item(item, index) for index, item in enumerate(qa_results)]
    snapshot_payload = {
        "snapshot_type": "retrieval_snapshot",
        "persona_id": persona_id,
        "items": items,
    }
    resolved_db_snapshot_id = db_snapshot_id or f"retrieval:{stable_payload_hash(snapshot_payload)[:16]}"
    manifest = run_manifest or _orthogonal_manifest(
        harness="personamem_v2_retrieval_snapshot",
        persona_id=persona_id,
        question_count=len(items),
        db_snapshot_id=resolved_db_snapshot_id,
        dataset_hash=stable_payload_hash(snapshot_payload),
        cache_hash=stable_payload_hash(snapshot_payload),
    )
    return {
        "snapshot_type": "retrieval_snapshot",
        "db_snapshot_id": resolved_db_snapshot_id,
        "persona_id": persona_id,
        "items": items,
        "run_manifest": manifest,
    }


def build_context_snapshot(
    retrieval_snapshot: dict[str, Any],
    *,
    run_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    items = []
    for index, item in enumerate(retrieval_snapshot.get("items", [])):
        item_id = _question_id(item, index)
        items.append(
            {
                "question_id": item_id,
                "question": item.get("question"),
                "standard_answer": item.get("standard_answer"),
                "answer_contexts": list(item.get("retrieved_contexts") or []),
                "context_scores": list(item.get("retrieved_scores") or []),
                "source_retrieval_snapshot": retrieval_snapshot.get("run_manifest", {}).get("run_id"),
                "persona_id": item.get("persona_id") or retrieval_snapshot.get("persona_id"),
                "source_split": item.get("source_split"),
                "row_index": item.get("row_index"),
            }
        )
    snapshot_payload = {
        "snapshot_type": "context_snapshot",
        "persona_id": retrieval_snapshot.get("persona_id"),
        "items": items,
    }
    db_snapshot_id = retrieval_snapshot.get("db_snapshot_id") or f"context:{stable_payload_hash(snapshot_payload)[:16]}"
    manifest = run_manifest or _orthogonal_manifest(
        harness="personamem_v2_context_snapshot",
        persona_id=retrieval_snapshot.get("persona_id"),
        question_count=len(items),
        db_snapshot_id=db_snapshot_id,
        dataset_hash=stable_payload_hash(snapshot_payload),
        cache_hash=stable_payload_hash(snapshot_payload),
    )
    return {
        "snapshot_type": "context_snapshot",
        "db_snapshot_id": db_snapshot_id,
        "persona_id": retrieval_snapshot.get("persona_id"),
        "items": items,
        "run_manifest": manifest,
    }


def validate_orthogonality(
    config: dict[str, Any],
    *,
    baseline_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    experiment_type = str(config.get("experiment_type") or config.get("orthogonal_mode") or "")
    changed_layers = _normalize_layers(config.get("changed_layer", config.get("changed_layers")))
    declared_controlled_layers = set(_normalize_layers(config.get("controlled_layers")))
    reasons = []

    if experiment_type not in EXPERIMENT_TYPES:
        reasons.append(f"unknown_experiment_type:{experiment_type}")
    if experiment_type in LAYER_BY_EXPERIMENT and not changed_layers:
        changed_layers = [LAYER_BY_EXPERIMENT[experiment_type]]
    expected_changed_layer = LAYER_BY_EXPERIMENT.get(experiment_type)
    if len(set(changed_layers)) != 1:
        reasons.append("changed_layer_must_contain_exactly_one_layer")
    elif expected_changed_layer and changed_layers[0] != expected_changed_layer:
        reasons.append(f"changed_layer_mismatch:expected={expected_changed_layer}:actual={changed_layers[0]}")

    required = REQUIRED_CONTROLLED_LAYERS.get(experiment_type, set())
    controlled_layers = set(required)
    if declared_controlled_layers and declared_controlled_layers != required:
        missing = sorted(required - declared_controlled_layers)
        extra = sorted(declared_controlled_layers - required)
        details = []
        if missing:
            details.append(f"missing={','.join(missing)}")
        if extra:
            details.append(f"extra={','.join(extra)}")
        reasons.append(f"declared_controlled_layers_mismatch:{';'.join(details)}")

    allowed_keys = ALLOWED_TOP_LEVEL_KEYS.get(experiment_type)
    if allowed_keys is not None and allowed_keys:
        forbidden = sorted(set(config) - allowed_keys)
        if forbidden:
            reasons.append(f"forbidden_config_keys:{','.join(forbidden)}")

    expected_snapshot = REQUIRED_REPLAY_SNAPSHOT.get(experiment_type)
    if expected_snapshot and baseline_snapshot and baseline_snapshot.get("snapshot_type") != expected_snapshot:
        reasons.append(
            f"baseline_snapshot_type_mismatch:expected={expected_snapshot}:actual={baseline_snapshot.get('snapshot_type')}"
        )
    elif expected_snapshot and baseline_snapshot is None:
        reasons.append(f"missing_baseline_snapshot:{expected_snapshot}")

    valid = not reasons
    conclusion = "diagnostic_only" if not valid or len(set(changed_layers)) != 1 else "inconclusive"
    return {
        "valid": valid,
        "experiment_type": experiment_type,
        "changed_layer": changed_layers,
        "controlled_layers": sorted(controlled_layers),
        "required_controlled_layers": sorted(required),
        "reasons": reasons,
        "experiment_conclusion": conclusion,
    }


def run_writer_ab(
    baseline_snapshot: dict[str, Any],
    candidate_config: dict[str, Any],
    *,
    output_dir: Path = OUTPUT_DIR,
    strict: bool = True,
    allow_diagnostic: bool = False,
) -> dict[str, Any]:
    return _run_orthogonal_ab(
        "writer_ab",
        baseline_snapshot,
        candidate_config,
        output_dir=output_dir,
        strict=strict,
        allow_diagnostic=allow_diagnostic,
    )


def run_retrieval_ab(
    baseline_snapshot: dict[str, Any],
    candidate_config: dict[str, Any],
    *,
    output_dir: Path = OUTPUT_DIR,
    strict: bool = True,
    allow_diagnostic: bool = False,
) -> dict[str, Any]:
    return _run_orthogonal_ab(
        "retrieval_ab",
        baseline_snapshot,
        candidate_config,
        output_dir=output_dir,
        strict=strict,
        allow_diagnostic=allow_diagnostic,
    )


def run_rerank_ab(
    baseline_snapshot: dict[str, Any],
    candidate_config: dict[str, Any],
    *,
    output_dir: Path = OUTPUT_DIR,
    strict: bool = True,
    allow_diagnostic: bool = False,
) -> dict[str, Any]:
    return _run_orthogonal_ab(
        "rerank_ab",
        baseline_snapshot,
        candidate_config,
        output_dir=output_dir,
        strict=strict,
        allow_diagnostic=allow_diagnostic,
    )


def run_generator_ab(
    baseline_snapshot: dict[str, Any],
    candidate_config: dict[str, Any],
    *,
    output_dir: Path = OUTPUT_DIR,
    strict: bool = True,
    allow_diagnostic: bool = False,
) -> dict[str, Any]:
    return _run_orthogonal_ab(
        "generator_ab",
        baseline_snapshot,
        candidate_config,
        output_dir=output_dir,
        strict=strict,
        allow_diagnostic=allow_diagnostic,
    )


def run_orthogonal_from_config(
    *,
    mode: str,
    baseline_snapshot: dict[str, Any],
    candidate_config: dict[str, Any],
    output_dir: Path = OUTPUT_DIR,
    strict: bool = True,
    allow_diagnostic: bool | None = None,
) -> dict[str, Any]:
    runners = {
        "writer_ab": run_writer_ab,
        "retrieval_ab": run_retrieval_ab,
        "rerank_ab": run_rerank_ab,
        "generator_ab": run_generator_ab,
        "e2e_diagnostic": lambda snapshot, config, *, output_dir, strict, allow_diagnostic: _run_orthogonal_ab(
            "e2e_diagnostic",
            snapshot,
            config,
            output_dir=output_dir,
            strict=strict,
            allow_diagnostic=allow_diagnostic,
        ),
    }
    if mode not in runners:
        raise ValueError(f"Unsupported orthogonal mode: {mode}")
    resolved_allow_diagnostic = (
        bool(candidate_config.get("allow_diagnostic")) if allow_diagnostic is None else allow_diagnostic
    )
    if mode == "e2e_diagnostic":
        resolved_allow_diagnostic = True
    return runners[mode](
        baseline_snapshot,
        candidate_config,
        output_dir=output_dir,
        strict=strict,
        allow_diagnostic=resolved_allow_diagnostic,
    )


def _run_orthogonal_ab(
    experiment_type: str,
    baseline_snapshot: dict[str, Any],
    candidate_config: dict[str, Any],
    *,
    output_dir: Path,
    strict: bool,
    allow_diagnostic: bool,
) -> dict[str, Any]:
    config = {**candidate_config, "experiment_type": experiment_type}
    orthogonality = validate_orthogonality(config, baseline_snapshot=baseline_snapshot)
    baseline_variant = _variant_payload(
        candidate_config.get("baseline_variant"),
        fallback_snapshot=baseline_snapshot,
        default_name="baseline",
    )
    candidate_variant = _variant_payload(
        candidate_config.get("candidate_variant"),
        fallback_snapshot=None,
        default_name="candidate",
    )
    if experiment_type == "rerank_ab" and "rerank_config" not in candidate_variant:
        candidate_variant["rerank_config"] = candidate_config.get("rerank_config") or {}
    baseline_qa = _variant_qa_results(baseline_variant, baseline_snapshot, experiment_type)
    candidate_qa = _variant_qa_results(candidate_variant, baseline_snapshot, experiment_type)
    if not baseline_qa or not candidate_qa:
        reason = "empty_orthogonal_question_set"
        orthogonality["reasons"].append(reason)
        orthogonality["valid"] = False
        orthogonality["experiment_conclusion"] = "diagnostic_only"
        if strict and not allow_diagnostic:
            raise ValueError(f"Non-orthogonal PersonaMem-v2 experiment: {reason}")
    replay_check = _validate_replay_inputs(
        experiment_type,
        baseline_snapshot=baseline_snapshot,
        baseline_qa=baseline_qa,
        candidate_qa=candidate_qa,
    )
    orthogonality["replay_fingerprints"] = replay_check["fingerprints"]
    if replay_check["reasons"]:
        orthogonality["reasons"].extend(replay_check["reasons"])
        orthogonality["valid"] = False
        orthogonality["experiment_conclusion"] = "diagnostic_only"
    if strict and not allow_diagnostic and not orthogonality["valid"]:
        raise ValueError(
            "Non-orthogonal PersonaMem-v2 experiment: "
            + "; ".join(orthogonality["reasons"])
        )
    paired = build_paired_comparison(baseline_qa, candidate_qa)
    conclusion = (
        "diagnostic_only"
        if not orthogonality["valid"] or experiment_type == "e2e_diagnostic"
        else determine_experiment_conclusion(paired, changed_variables=orthogonality["changed_layer"])
    )
    candidate_stats = build_personamem_statistics_from_qa_results(
        candidate_qa,
        {"accuracy": _accuracy(candidate_qa)},
    )
    baseline_manifest = baseline_snapshot.get("run_manifest") or {}
    dataset_hash = (
        candidate_config.get("dataset_hash")
        or baseline_manifest.get("dataset_hash")
        or replay_check["fingerprints"].get("storage_snapshot")
        or replay_check["fingerprints"]["baseline_question_set"]
    )
    cache_hash = candidate_config.get("cache_hash") or stable_payload_hash(replay_check["fingerprints"])
    run_manifest = _orthogonal_manifest(
        harness="personamem_v2_orthogonal",
        eval_mode=experiment_type,
        persona_id=baseline_snapshot.get("persona_id") or candidate_config.get("persona_id") or "66",
        question_count=len(candidate_qa),
        db_snapshot_id=baseline_snapshot.get("db_snapshot_id"),
        dataset_hash=dataset_hash,
        cache_hash=cache_hash,
        chat_model=candidate_config.get("chat_model"),
        evaluator_model=candidate_config.get("evaluator_model"),
        top_k=candidate_config.get("top_k"),
        rerank_config=candidate_config.get("rerank_config"),
        temperature=candidate_config.get("temperature", 0),
        result_file_path=None,
    )
    report = {
        "experiment_type": experiment_type,
        "changed_layer": orthogonality["changed_layer"],
        "controlled_layers": orthogonality["controlled_layers"],
        "baseline_variant": {k: v for k, v in baseline_variant.items() if k != "qa_results"},
        "candidate_variant": {k: v for k, v in candidate_variant.items() if k != "qa_results"},
        "orthogonality_check": orthogonality,
        "paired_comparison": paired,
        "experiment_conclusion": conclusion,
        "personamem_evidence": candidate_stats["personamem_evidence"],
        "run_manifest": run_manifest,
        "statistics": {
            "total_questions": len(candidate_qa),
            "accuracy": _accuracy(candidate_qa),
            **candidate_stats,
        },
        "samples": [
            {
                "sample_index": 0,
                "character": baseline_snapshot.get("persona_id") or "66",
                "variant": "baseline",
                "qa_results": baseline_qa,
            },
            {
                "sample_index": 1,
                "character": baseline_snapshot.get("persona_id") or "66",
                "variant": "candidate",
                "qa_results": candidate_qa,
            },
        ],
    }
    if conclusion == "diagnostic_only":
        report["run_manifest"]["formal_ab_eligible"] = False
        report["run_manifest"]["diagnostic_reason"] = (
            "non_orthogonal_or_explicit_diagnostic_experiment"
        )
    output_path = output_dir / f"personamem_v2_{experiment_type}_{_timestamp()}.json"
    save_json_file(report, output_path)
    return report


def _variant_payload(
    value: dict[str, Any] | None,
    *,
    fallback_snapshot: dict[str, Any] | None,
    default_name: str,
) -> dict[str, Any]:
    if value:
        payload = dict(value)
    else:
        payload = {"name": default_name}
    payload.setdefault("name", default_name)
    if "qa_results" not in payload and fallback_snapshot is not None:
        payload["snapshot"] = fallback_snapshot
    return payload


def _variant_qa_results(
    variant: dict[str, Any],
    baseline_snapshot: dict[str, Any],
    experiment_type: str,
) -> list[dict[str, Any]]:
    if variant.get("qa_results"):
        if experiment_type == "generator_ab":
            return [
                _qa_from_context_item(item, index, variant)
                for index, item in enumerate(variant["qa_results"])
            ]
        return [_normalize_retrieval_item(item, index) for index, item in enumerate(variant["qa_results"])]
    snapshot = variant.get("snapshot") or baseline_snapshot
    items = snapshot.get("items") or []
    if experiment_type == "rerank_ab" and variant.get("rerank_config", {}).get("type") == "answer_bearing":
        return [_answer_bearing_reranked_item(item, index, variant) for index, item in enumerate(items)]
    if snapshot.get("snapshot_type") == "context_snapshot" or experiment_type == "generator_ab":
        return [_qa_from_context_item(item, index, variant) for index, item in enumerate(items)]
    return [_normalize_retrieval_item(item, index) for index, item in enumerate(items)]


def _answer_bearing_reranked_item(item: dict[str, Any], index: int, variant: dict[str, Any]) -> dict[str, Any]:
    contexts = list(item.get("retrieved_contexts") or item.get("answer_contexts") or [])
    scores = list(item.get("retrieved_scores") or item.get("context_scores") or [])
    config = variant.get("rerank_config") or {}
    reranked_contexts, reranked_scores, trace = rerank_answer_bearing_contexts(
        question=str(item.get("question") or ""),
        contexts=contexts,
        scores=scores,
        top_n=config.get("top_n") or len(contexts),
    )
    payload = dict(item)
    payload["retrieval_candidate_contexts"] = list(item.get("retrieval_candidate_contexts") or contexts)
    payload["retrieval_candidate_scores"] = list(item.get("retrieval_candidate_scores") or scores)
    payload["retrieved_contexts"] = reranked_contexts
    payload["retrieved_scores"] = reranked_scores
    qa = _normalize_retrieval_item(payload, index)
    qa["rerank_trace"] = trace
    qa["rerank_stage"] = qa["retrieval_stage"]
    return qa


def _validate_replay_inputs(
    experiment_type: str,
    *,
    baseline_snapshot: dict[str, Any],
    baseline_qa: list[dict[str, Any]],
    candidate_qa: list[dict[str, Any]],
) -> dict[str, Any]:
    fingerprints = {
        "baseline_question_set": fingerprint_question_set(baseline_qa),
        "candidate_question_set": fingerprint_question_set(candidate_qa),
        "baseline_contexts": fingerprint_contexts(baseline_qa),
        "candidate_contexts": fingerprint_contexts(candidate_qa),
        "baseline_retrieval_candidates": fingerprint_retrieval_candidates(baseline_qa),
        "candidate_retrieval_candidates": fingerprint_retrieval_candidates(candidate_qa),
    }
    if baseline_snapshot.get("snapshot_type") == "storage_snapshot":
        fingerprints["storage_snapshot"] = fingerprint_storage_snapshot(baseline_snapshot)

    reasons = []
    if fingerprints["baseline_question_set"] != fingerprints["candidate_question_set"]:
        reasons.append("question_set_fingerprint_mismatch")
    if experiment_type == "rerank_ab":
        if fingerprints["baseline_retrieval_candidates"] != fingerprints["candidate_retrieval_candidates"]:
            reasons.append("retrieval_candidate_pool_fingerprint_mismatch")
    elif experiment_type == "generator_ab":
        if fingerprints["baseline_contexts"] != fingerprints["candidate_contexts"]:
            reasons.append("answer_context_fingerprint_mismatch")
    return {
        "fingerprints": fingerprints,
        "reasons": reasons,
    }


def _normalize_retrieval_item(item: dict[str, Any], index: int) -> dict[str, Any]:
    qa = _normalize_qa_result(item, index)
    qa["retrieved_contexts"] = list(item.get("retrieved_contexts") or item.get("answer_contexts") or [])
    qa["retrieved_scores"] = list(item.get("retrieved_scores") or item.get("context_scores") or [])
    qa["retrieval_candidate_contexts"] = list(item.get("retrieval_candidate_contexts") or qa["retrieved_contexts"])
    qa["retrieval_candidate_scores"] = list(item.get("retrieval_candidate_scores") or qa["retrieved_scores"])
    qa["retrieval_layer"] = item.get("retrieval_layer") or {}
    qa["retrieval_stage"] = item.get("retrieval_stage") or _evidence_stage(qa, stage="retrieval_top_k")
    qa["answer_stage"] = item.get("answer_stage") or _evidence_stage(qa, stage="answer_context")
    qa.setdefault("is_correct", bool(qa["retrieval_stage"].get("answerable_context_hit")))
    return qa


def _qa_from_context_item(item: dict[str, Any], index: int, variant: dict[str, Any]) -> dict[str, Any]:
    qa = _normalize_qa_result(item, index)
    qa["retrieved_contexts"] = list(item.get("answer_contexts") or item.get("retrieved_contexts") or [])
    qa["retrieved_scores"] = list(item.get("context_scores") or item.get("retrieved_scores") or [])
    qa["retrieval_candidate_contexts"] = list(item.get("retrieval_candidate_contexts") or qa["retrieved_contexts"])
    qa["retrieval_candidate_scores"] = list(item.get("retrieval_candidate_scores") or qa["retrieved_scores"])
    generated = variant.get("generated_answers", {}).get(qa["question_id"])
    if generated is not None:
        qa["generated_answer"] = generated
    if "is_correct_by_question_id" in variant:
        qa["is_correct"] = bool(variant["is_correct_by_question_id"].get(qa["question_id"]))
    qa["retrieval_stage"] = item.get("retrieval_stage") or _evidence_stage(qa, stage="retrieval_top_k")
    qa["answer_stage"] = item.get("answer_stage") or _evidence_stage(
        qa,
        stage="answer_context",
        generated_answer=qa.get("generated_answer"),
        is_correct=qa.get("is_correct"),
    )
    return qa


def _normalize_qa_result(item: dict[str, Any], index: int) -> dict[str, Any]:
    question_id = _question_id(item, index)
    return {
        "question_id": question_id,
        "persona_id": item.get("persona_id") or item.get("character") or "66",
        "source_split": item.get("source_split"),
        "row_index": item.get("row_index", index),
        "question": item.get("question") or "",
        "standard_answer": item.get("standard_answer") or item.get("correct_answer") or "",
        "correct_answer": item.get("standard_answer") or item.get("correct_answer") or "",
        "supporting_preference": item.get("supporting_preference") or item.get("preference") or "",
        "related_conversation_snippet": item.get("related_conversation_snippet") or "",
        "incorrect_answers": list(item.get("incorrect_answers") or []),
        "generated_answer": item.get("generated_answer"),
        "is_correct": item.get("is_correct"),
    }


def _evidence_stage(
    qa: dict[str, Any],
    *,
    stage: str,
    generated_answer: str | None = None,
    is_correct: bool | None = None,
) -> dict[str, Any]:
    return analyze_personamem_evidence(
        question=qa.get("question") or "",
        correct_answer=qa.get("standard_answer") or qa.get("correct_answer") or "",
        supporting_preference=qa.get("supporting_preference") or "",
        related_conversation_snippet=qa.get("related_conversation_snippet") or "",
        incorrect_answers=qa.get("incorrect_answers") or [],
        contexts=qa.get("retrieved_contexts") or [],
        scores=qa.get("retrieved_scores") or [],
        stage=stage,
        loose_rank_position=None,
        retrieval_hit_loose=bool(qa.get("retrieved_contexts")),
        generated_answer=generated_answer,
        is_correct=is_correct,
    )


def _orthogonal_manifest(
    *,
    harness: str,
    eval_mode: str | None = None,
    persona_id: str | None = "66",
    question_count: int | None = None,
    db_snapshot_id: str | None = None,
    dataset_hash: str | None = None,
    cache_hash: str | None = None,
    temperature: float | int | None = 0,
    chat_model: str | None = None,
    evaluator_model: str | None = None,
    top_k: int | None = None,
    rerank_config: dict[str, Any] | None = None,
    result_file_path: str | None = None,
) -> dict[str, Any]:
    return build_run_manifest(
        harness=harness,
        eval_mode=eval_mode,
        dataset="bowen-upenn/PersonaMem-v2",
        split="benchmark_text",
        persona_id=persona_id,
        question_count=question_count,
        retrieval_only=True,
        import_only=False,
        reset_memory=False,
        chat_model=chat_model,
        evaluator_model=evaluator_model,
        evaluator_isolated=evaluator_model is not None,
        top_k=top_k,
        scoring_config=None,
        rerank_config=rerank_config,
        db_snapshot_id=db_snapshot_id,
        dataset_hash=dataset_hash,
        cache_hash=cache_hash,
        temperature=temperature,
        result_file_path=result_file_path,
        started_at=utc_now_iso(),
        extra={
            "formal_ab_eligible": harness == "personamem_v2_orthogonal",
        },
    )


def _normalize_layers(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def _question_id(item: dict[str, Any], index: int) -> str:
    return str(item.get("question_id") or item.get("row_index") or f"q{index}")


def _accuracy(qa_results: list[dict[str, Any]]) -> float:
    evaluated = [item for item in qa_results if item.get("is_correct") is not None]
    if not evaluated:
        return 0.0
    return sum(1 for item in evaluated if item.get("is_correct") is True) / len(evaluated) * 100


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _question_identity(item: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "question_id": _question_id(item, index),
        "persona_id": item.get("persona_id") or item.get("character") or "66",
        "source_split": item.get("source_split"),
        "row_index": item.get("row_index", index),
        "question": item.get("question") or "",
        "standard_answer": item.get("standard_answer") or item.get("correct_answer") or "",
    }


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
