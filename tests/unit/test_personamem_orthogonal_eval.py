from __future__ import annotations

import json

import pytest

from tests.evals.personamem_v2.analysis import build_personamem_analysis_markdown
from tests.evals.personamem_v2.orthogonal_eval import (
    build_context_snapshot,
    build_retrieval_snapshot,
    build_storage_snapshot,
    run_generator_ab,
    run_orthogonal_from_config,
    run_rerank_ab,
    run_retrieval_ab,
    validate_orthogonality,
)


def _qa(
    row_index: int,
    *,
    context: str | list[str],
    answer: str = "warm cocoa",
    is_correct: bool | None = None,
) -> dict:
    contexts = context if isinstance(context, list) else [context]
    return {
        "question_id": f"q{row_index}",
        "persona_id": "66",
        "source_split": "benchmark_text",
        "row_index": row_index,
        "question": "What cozy drink does the user like?",
        "standard_answer": answer,
        "supporting_preference": f"The user likes {answer}.",
        "retrieved_contexts": contexts,
        "retrieved_scores": [0.9 for _ in contexts],
        "is_correct": is_correct,
    }


def test_validate_orthogonality_allows_single_changed_retrieval_layer():
    storage_snapshot = build_storage_snapshot(user_id="u1", persona_id="66")
    check = validate_orthogonality(
        {
            "experiment_type": "retrieval_ab",
            "changed_layer": "retrieval",
        },
        baseline_snapshot=storage_snapshot,
    )

    assert check["valid"] is True
    assert check["controlled_layers"] == ["evaluator", "generator", "storage"]
    assert check["experiment_conclusion"] == "inconclusive"


def test_validate_orthogonality_marks_multi_layer_as_diagnostic_only():
    check = validate_orthogonality(
        {
            "experiment_type": "retrieval_ab",
            "changed_layer": ["retrieval", "generator"],
            "controlled_layers": ["storage", "generator", "evaluator"],
        },
        baseline_snapshot=build_storage_snapshot(user_id="u1", persona_id="66"),
    )

    assert check["valid"] is False
    assert check["experiment_conclusion"] == "diagnostic_only"
    assert "changed_layer_must_contain_exactly_one_layer" in check["reasons"]


def test_validate_orthogonality_flags_missing_controlled_snapshot():
    check = validate_orthogonality(
        {
            "experiment_type": "rerank_ab",
            "changed_layer": "rerank",
            "controlled_layers": ["storage", "generator", "evaluator"],
        },
        baseline_snapshot=build_storage_snapshot(user_id="u1", persona_id="66"),
    )

    assert check["valid"] is False
    assert any(reason.startswith("declared_controlled_layers_mismatch") for reason in check["reasons"])
    assert any(reason.startswith("baseline_snapshot_type_mismatch") for reason in check["reasons"])


def test_validate_orthogonality_rejects_forbidden_top_level_keys():
    check = validate_orthogonality(
        {
            "experiment_type": "retrieval_ab",
            "changed_layer": "retrieval",
            "chat_model": "ChangedGenerator",
        },
        baseline_snapshot=build_storage_snapshot(user_id="u1", persona_id="66"),
    )

    assert check["valid"] is False
    assert "forbidden_config_keys:chat_model" in check["reasons"]


def test_snapshot_contracts_keep_manifest_unknowns_as_null():
    storage_snapshot = build_storage_snapshot(user_id="u1", persona_id="66")
    retrieval_snapshot = build_retrieval_snapshot(
        [_qa(1, context="The user likes warm cocoa.")],
        persona_id="66",
    )
    context_snapshot = build_context_snapshot(retrieval_snapshot)

    assert storage_snapshot["run_manifest"]["db_snapshot_id"] is None
    assert storage_snapshot["run_manifest"]["dataset_hash"] is None
    assert storage_snapshot["run_manifest"]["cache_hash"] is None
    assert storage_snapshot["run_manifest"]["temperature"] is None
    assert storage_snapshot["run_manifest"]["result_file_path"] is None
    assert retrieval_snapshot["items"][0]["retrieval_stage"]["answerable_context_hit"] is True
    assert context_snapshot["items"][0]["answer_contexts"] == ["The user likes warm cocoa."]


def test_retrieval_ab_report_uses_evidence_first_and_paired_comparison(tmp_path):
    storage_snapshot = build_storage_snapshot(user_id="u1", persona_id="66")
    report = run_retrieval_ab(
        storage_snapshot,
        {
            "changed_layer": "retrieval",
            "controlled_layers": ["storage", "generator", "evaluator"],
            "baseline_variant": {
                "name": "old_retrieval",
                "qa_results": [_qa(1, context="The user likes tea.", is_correct=False)],
            },
            "candidate_variant": {
                "name": "new_retrieval",
                "qa_results": [_qa(1, context="The user likes warm cocoa.", is_correct=True)],
            },
        },
        output_dir=tmp_path,
    )

    assert report["experiment_type"] == "retrieval_ab"
    assert report["experiment_conclusion"] == "accept"
    assert report["paired_comparison"]["gain"] == 1
    assert report["personamem_evidence"]["evidence_first_summary"]["primary_metrics"][
        "answerable_context_hit_at_k"
    ] == 100


def test_rerank_ab_replays_same_retrieval_candidate_pool(tmp_path):
    retrieval_snapshot = build_retrieval_snapshot(
        [_qa(1, context=["The user likes tea.", "The user likes warm cocoa."], is_correct=False)],
        persona_id="66",
    )
    report = run_rerank_ab(
        retrieval_snapshot,
        {
            "changed_layer": "rerank",
            "controlled_layers": ["storage", "retrieval_candidates", "generator", "evaluator"],
            "baseline_variant": {
                "name": "raw_order",
                "qa_results": [
                    _qa(1, context=["The user likes tea.", "The user likes warm cocoa."], is_correct=False)
                ],
            },
            "candidate_variant": {
                "name": "reranked",
                "qa_results": [
                    _qa(1, context=["The user likes warm cocoa.", "The user likes tea."], is_correct=True)
                ],
            },
        },
        output_dir=tmp_path,
    )

    assert report["orthogonality_check"]["valid"] is True
    assert report["changed_layer"] == ["rerank"]
    assert report["paired_comparison"]["gain"] == 1


def test_rerank_ab_rejects_changed_candidate_pool_by_default(tmp_path):
    retrieval_snapshot = build_retrieval_snapshot(
        [_qa(1, context=["The user likes tea.", "The user likes warm cocoa."], is_correct=False)],
        persona_id="66",
    )

    with pytest.raises(ValueError, match="retrieval_candidate_pool_fingerprint_mismatch"):
        run_rerank_ab(
            retrieval_snapshot,
            {
                "changed_layer": "rerank",
                "controlled_layers": ["storage", "retrieval_candidates", "generator", "evaluator"],
                "candidate_variant": {
                    "name": "reranked",
                    "qa_results": [_qa(1, context="The user likes warm cocoa.", is_correct=True)],
                },
            },
            output_dir=tmp_path,
        )


def test_rerank_ab_can_write_diagnostic_when_explicitly_allowed(tmp_path):
    retrieval_snapshot = build_retrieval_snapshot(
        [_qa(1, context=["The user likes tea.", "The user likes warm cocoa."], is_correct=False)],
        persona_id="66",
    )

    report = run_rerank_ab(
        retrieval_snapshot,
        {
            "changed_layer": "rerank",
            "controlled_layers": ["storage", "retrieval_candidates", "generator", "evaluator"],
            "candidate_variant": {
                "name": "reranked",
                "qa_results": [_qa(1, context="The user likes warm cocoa.", is_correct=True)],
            },
        },
        output_dir=tmp_path,
        allow_diagnostic=True,
    )

    assert report["experiment_conclusion"] == "diagnostic_only"
    assert "retrieval_candidate_pool_fingerprint_mismatch" in report["orthogonality_check"]["reasons"]


def test_generator_ab_replays_fixed_context_snapshot(tmp_path):
    retrieval_snapshot = build_retrieval_snapshot(
        [_qa(1, context="The user likes warm cocoa.", is_correct=True)],
        persona_id="66",
    )
    context_snapshot = build_context_snapshot(retrieval_snapshot)
    report = run_generator_ab(
        context_snapshot,
        {
            "changed_layer": "generator",
            "controlled_layers": ["storage", "answer_context", "evaluator"],
            "baseline_variant": {
                "name": "generator_a",
                "qa_results": [_qa(1, context="The user likes warm cocoa.", is_correct=False)],
            },
            "candidate_variant": {
                "name": "generator_b",
                "qa_results": [_qa(1, context="The user likes warm cocoa.", is_correct=True)],
            },
        },
        output_dir=tmp_path,
    )

    assert report["experiment_type"] == "generator_ab"
    assert report["paired_comparison"]["gain"] == 1
    assert report["experiment_conclusion"] == "accept"


def test_generator_ab_rejects_changed_answer_context(tmp_path):
    retrieval_snapshot = build_retrieval_snapshot(
        [_qa(1, context="The user likes warm cocoa.", is_correct=True)],
        persona_id="66",
    )
    context_snapshot = build_context_snapshot(retrieval_snapshot)

    with pytest.raises(ValueError, match="answer_context_fingerprint_mismatch"):
        run_generator_ab(
            context_snapshot,
            {
                "changed_layer": "generator",
                "controlled_layers": ["storage", "answer_context", "evaluator"],
                "candidate_variant": {
                    "name": "generator_b",
                    "qa_results": [_qa(1, context="The user likes tea.", is_correct=True)],
                },
            },
            output_dir=tmp_path,
        )


def test_run_orthogonal_from_config_writes_result_file(tmp_path):
    storage_snapshot = build_storage_snapshot(user_id="u1", persona_id="66")
    report = run_orthogonal_from_config(
        mode="retrieval_ab",
        baseline_snapshot=storage_snapshot,
        candidate_config={
            "changed_layer": "retrieval",
            "controlled_layers": ["storage", "generator", "evaluator"],
            "baseline_variant": {"qa_results": [_qa(1, context="tea", is_correct=False)]},
            "candidate_variant": {"qa_results": [_qa(1, context="warm cocoa", is_correct=True)]},
        },
        output_dir=tmp_path,
    )
    written = list(tmp_path.glob("personamem_v2_retrieval_ab_*.json"))

    assert written
    payload = json.loads(written[0].read_text(encoding="utf-8"))
    assert payload["run_manifest"]["result_file_path"] == str(written[0])
    assert report["experiment_conclusion"] == "accept"


def test_old_analysis_markdown_can_read_orthogonal_report(tmp_path):
    storage_snapshot = build_storage_snapshot(user_id="u1", persona_id="66")
    report = run_retrieval_ab(
        storage_snapshot,
        {
            "changed_layer": "retrieval",
            "controlled_layers": ["storage", "generator", "evaluator"],
            "baseline_variant": {"qa_results": [_qa(1, context="tea", is_correct=False)]},
            "candidate_variant": {"qa_results": [_qa(1, context="warm cocoa", is_correct=True)]},
        },
        output_dir=tmp_path,
    )
    markdown = build_personamem_analysis_markdown(report, "orthogonal.json")

    assert "PersonaMem-v2 Analysis" in markdown
    assert "Answerable context hit@k" in markdown


def test_invalid_mode_raises_value_error():
    with pytest.raises(ValueError, match="Unsupported orthogonal mode"):
        run_orthogonal_from_config(
            mode="unknown",
            baseline_snapshot=build_storage_snapshot(user_id="u1"),
            candidate_config={},
        )
