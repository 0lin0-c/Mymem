from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from core.config import settings
from tests.evals.common.run_manifest import build_run_manifest
from tests.evals.converted_data.report_json import save_results_json as save_converted_results_json
from tests.evals.personamem_v2.analysis import build_personamem_analysis_markdown
from tests.evals.personamem_v2.candidate_view_reporting import build_candidate_results_data
from tests.evals.personamem_v2.models import PersonaMemReport
from tests.evals.personamem_v2 import runner as personamem_runner
from tests.evals.personamem_v2.bm25_eval import build_bm25_run_manifest
from tests.evals.personamem_v2.candidate_view_experiment import save_candidate_experiment_report
from tests.evals.personamem_v2.rerank_eval import build_rerank_run_manifest
from tests.evals.personamem_v2.reporting import (
    build_model_sweep_ranking_key,
    build_paired_comparison,
    build_personamem_statistics_from_qa_results,
    determine_experiment_conclusion,
)
from tests.evals.personamem_v2.runner import (
    _resolve_evaluator_model,
    build_arg_parser,
    save_model_sweep_summary,
)


def test_build_run_manifest_preserves_schema_when_optional_values_missing(monkeypatch):
    monkeypatch.setattr("tests.evals.common.run_manifest._safe_git_sha", lambda: None)
    monkeypatch.setattr("tests.evals.common.run_manifest._command_string", lambda: None)

    manifest = build_run_manifest(
        harness="personamem_v2",
        eval_mode="assistant_eval",
        dataset="bowen-upenn/PersonaMem-v2",
        scoring_config=None,
        rerank_config=None,
    )

    assert manifest["git_sha"] is None
    assert manifest["command"] is None
    assert manifest["chat_model"] is None
    assert manifest["evaluator_model"] is None
    assert manifest["scoring_config"] is None
    assert manifest["rerank_config"] is None
    assert manifest["result_schema_version"]


def test_build_run_manifest_contains_required_p0_fields(monkeypatch):
    monkeypatch.setattr("tests.evals.common.run_manifest._safe_git_sha", lambda: "abc123")
    monkeypatch.setattr("tests.evals.common.run_manifest._command_string", lambda: "pytest -q")

    manifest = build_run_manifest(
        harness="personamem_v2",
        eval_mode="assistant_eval",
        dataset="bowen-upenn/PersonaMem-v2",
        split="benchmark_text",
        persona_id="66",
        question_count=42,
        import_only=False,
        retrieval_only=True,
        reset_memory=False,
        chat_model="Model-A",
        evaluator_model="Judge-1",
        evaluator_isolated=True,
        top_k=10,
        scoring_config={"similarity_power": 2.0},
        rerank_config=None,
    )

    required = {
        "run_id",
        "created_at",
        "git_sha",
        "command",
        "dataset",
        "split",
        "persona_id",
        "sample",
        "question_count",
        "eval_mode",
        "retrieval_only",
        "import_only",
        "reset_memory",
        "chat_model",
        "evaluator_model",
        "embedding_model",
        "top_k",
        "scoring_config",
        "rerank_config",
        "result_schema_version",
    }
    assert required <= set(manifest)
    assert manifest["git_sha"] == "abc123"


def test_default_sweep_evaluator_can_be_fixed_without_marking_explicit_isolation():
    model, isolated = _resolve_evaluator_model(
        active_chat_model="Model-B",
        evaluator_model=None,
        default_evaluator_model="Model-A",
    )

    assert model == "Model-A"
    assert isolated is False


def test_personamem_v2_cli_accepts_pytest_style_evaluator_alias():
    args = build_arg_parser().parse_args(
        ["--personamem-v2-evaluator-model", "Judge-1", "--model-sweep", "Model-A,Model-B"]
    )

    assert args.evaluator_model == "Judge-1"


@pytest.mark.asyncio
async def test_model_sweep_default_evaluator_is_fixed_to_original_model(monkeypatch, tmp_path):
    calls = []

    async def fake_run_personamem_v2_eval(**kwargs):
        calls.append(kwargs)
        return [
            PersonaMemReport(
                sample_index=0,
                character="66",
                user_id=f"user-{kwargs['chat_model']}",
                total_sessions=0,
                total_memories=0,
                total_questions=0,
                results=[],
                chat_model=kwargs["chat_model"],
                evaluator_model=kwargs["default_evaluator_model"],
                evaluator_isolated=kwargs["evaluator_model"] is not None,
            )
        ]

    monkeypatch.setattr(settings, "chat_model", "Judge-Default")
    monkeypatch.setattr(personamem_runner, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(
        personamem_runner,
        "run_personamem_v2_eval",
        fake_run_personamem_v2_eval,
    )

    payload = await personamem_runner.run_personamem_v2_model_sweep(
        chat_models=["Model-A", "Model-B"],
        retrieval_only=True,
    )

    assert [call["default_evaluator_model"] for call in calls] == ["Judge-Default", "Judge-Default"]
    assert [call["evaluator_model"] for call in calls] == [None, None]
    assert payload["test_info"]["evaluator_model"] == "Judge-Default"
    assert payload["test_info"]["evaluator_isolated"] is False


def test_evidence_first_summary_adds_generation_masking_label():
    qa_results = [
        {
            "retrieval_stage": {
                "retrieval_hit_loose": True,
                "target_preference_hit": False,
                "target_snippet_hit": False,
                "target_answer_anchor_hit": False,
                "answerable_context_hit": False,
                "answer_support_type": "wrong",
                "retrieval_failure_subtype": "target_evidence_not_retrieved",
            },
            "answer_stage": {
                "retrieval_hit_loose": True,
                "target_preference_hit": False,
                "target_snippet_hit": False,
                "target_answer_anchor_hit": False,
                "answerable_context_hit": False,
                "answer_support_type": "unsupported",
                "retrieval_failure_subtype": "target_evidence_not_retrieved",
            },
        }
        for _ in range(4)
    ]

    stats = build_personamem_statistics_from_qa_results(qa_results, {"accuracy": 75.0})
    summary = stats["personamem_evidence"]["evidence_first_summary"]

    assert summary["primary_metrics"]["answerable_context_hit_at_k"] == 0
    assert "generation_masking_retrieval_gap" in summary["diagnostic_labels"]
    assert summary["primary_metrics"]["target_evidence_not_retrieved_rate"] == 100


def test_model_sweep_ranking_prefers_answerable_evidence_over_raw_accuracy():
    lower_accuracy_better_evidence = {
        "personamem_metrics": {
            "personamem_evidence": {
                "evidence_first_summary": {
                    "primary_metrics": {
                        "answerable_context_hit_at_k": 40,
                        "target_preference_hit_at_k": 55,
                        "target_answer_anchor_hit_at_k": 20,
                        "wrong_neighbor_substitution_rate": 10,
                        "target_evidence_not_retrieved_rate": 15,
                        "accuracy": 61,
                    }
                }
            }
        }
    }
    higher_accuracy_weaker_evidence = {
        "personamem_metrics": {
            "personamem_evidence": {
                "evidence_first_summary": {
                    "primary_metrics": {
                        "answerable_context_hit_at_k": 5,
                        "target_preference_hit_at_k": 15,
                        "target_answer_anchor_hit_at_k": 0,
                        "wrong_neighbor_substitution_rate": 45,
                        "target_evidence_not_retrieved_rate": 55,
                        "accuracy": 80,
                    }
                }
            }
        }
    }

    ranked = sorted(
        [higher_accuracy_weaker_evidence, lower_accuracy_better_evidence],
        key=build_model_sweep_ranking_key,
        reverse=True,
    )

    assert ranked[0] is lower_accuracy_better_evidence


def test_paired_comparison_counts_gain_regression_and_stable_cases():
    baseline = [
        _comparison_item("q1", is_correct=False, answerable=False),
        _comparison_item("q2", is_correct=True, answerable=True),
        _comparison_item("q3", is_correct=True, answerable=False),
        _comparison_item("q4", is_correct=False, answerable=False),
    ]
    candidate = [
        _comparison_item("q1", is_correct=True, answerable=True),
        _comparison_item("q2", is_correct=False, answerable=True),
        _comparison_item("q3", is_correct=True, answerable=True),
        _comparison_item("q4", is_correct=False, answerable=False),
    ]

    paired = build_paired_comparison(baseline, candidate)

    assert paired["gain"] == 1
    assert paired["regression"] == 1
    assert paired["stable_success"] == 1
    assert paired["stable_failure"] == 1
    assert paired["retrieval_changed_answer_same"] == 1
    assert paired["retrieval_same_answer_changed"] == 1


def test_multi_variable_experiment_is_marked_diagnostic_only():
    conclusion = determine_experiment_conclusion(
        {"gain": 3, "regression": 0},
        changed_variables=["chat_model", "generator"],
    )

    assert conclusion == "diagnostic_only"


def test_model_sweep_summary_writes_fixed_evaluator_and_pairwise_comparison(tmp_path):
    sweep_results = [
        {
            "chat_model": "Model-A",
            "usernames": ["Model-A-persona66"],
            "user_ids": ["u1"],
            "total_memories": 10,
            "total_questions": 2,
            "metrics": {"accuracy": 70},
            "personamem_metrics": {
                "personamem_evidence": {
                    "evidence_first_summary": {
                        "primary_metrics": {
                            "answerable_context_hit_at_k": 35,
                            "target_preference_hit_at_k": 45,
                            "target_answer_anchor_hit_at_k": 20,
                            "wrong_neighbor_substitution_rate": 5,
                            "target_evidence_not_retrieved_rate": 10,
                            "accuracy": 70,
                        },
                        "diagnostic_labels": [],
                    }
                }
            },
            "comparison_items": [
                _comparison_item("q1", is_correct=True, answerable=True),
                _comparison_item("q2", is_correct=False, answerable=False),
            ],
            "evaluator_model": "Judge-1",
            "evaluator_isolated": True,
        },
        {
            "chat_model": "Model-B",
            "usernames": ["Model-B-persona66"],
            "user_ids": ["u2"],
            "total_memories": 10,
            "total_questions": 2,
            "metrics": {"accuracy": 80},
            "personamem_metrics": {
                "personamem_evidence": {
                    "evidence_first_summary": {
                        "primary_metrics": {
                            "answerable_context_hit_at_k": 5,
                            "target_preference_hit_at_k": 10,
                            "target_answer_anchor_hit_at_k": 0,
                            "wrong_neighbor_substitution_rate": 40,
                            "target_evidence_not_retrieved_rate": 45,
                            "accuracy": 80,
                        },
                        "diagnostic_labels": ["generation_masking_retrieval_gap"],
                    }
                }
            },
            "comparison_items": [
                _comparison_item("q1", is_correct=False, answerable=True),
                _comparison_item("q2", is_correct=True, answerable=False),
            ],
            "evaluator_model": "Judge-1",
            "evaluator_isolated": True,
        },
    ]

    payload = save_model_sweep_summary(
        sweep_results,
        "assistant_eval",
        output_dir=tmp_path,
        split="benchmark_text",
        persona_id="66",
        top_k=10,
        retrieval_only=True,
    )

    assert payload["ranked_models"][0]["chat_model"] == "Model-A"
    assert payload["test_info"]["evaluator_model"] == "Judge-1"
    assert payload["test_info"]["harness"] == "personamem_v2_legacy_model_sweep_diagnostic"
    assert payload["run_manifest"]["evaluator_model"] == "Judge-1"
    assert payload["run_manifest"]["harness"] == "personamem_v2_legacy_model_sweep_diagnostic"
    assert payload["formal_ab_eligible"] is False
    assert payload["pairwise_comparisons"][0]["conclusion"] == "diagnostic_only"
    assert payload["pairwise_comparisons"][0]["formal_ab_eligible"] is False
    assert payload["pairwise_comparisons"][0]["changed_variables"] == [
        "chat_model",
        "writer",
        "retrieval_classifier",
        "generator",
    ]
    assert payload["pairwise_comparisons"][0]["baseline_model"] == "Model-A"
    markdown = Path(payload["markdown_path"]).read_text(encoding="utf-8")
    assert "diagnostic only" in markdown
    assert "formal_ab_eligible: `False`" in markdown
    assert "wrong-neighbor=" in markdown
    assert "not-retrieved=" in markdown


def test_personamem_analysis_markdown_keeps_backward_compatibility_for_old_results():
    markdown = build_personamem_analysis_markdown(
        {
            "statistics": {"accuracy": 50, "personamem_evidence": {"retrieval_stage": {}}},
            "samples": [
                {
                    "character": "66",
                    "qa_results": [
                        {
                            "question": "What snack?",
                            "is_correct": False,
                            "retrieval_stage": {"retrieval_hit_loose": False},
                            "answer_stage": {},
                        }
                    ],
                }
            ],
        },
        "legacy.json",
    )

    assert "PersonaMem-v2 Analysis" in markdown
    assert "legacy.json" in markdown


def test_converted_save_results_json_includes_run_manifest(tmp_path):
    result = SimpleNamespace(
        retrieval_layer=SimpleNamespace(
            resolved_layer="resource_only",
            is_sufficient_at_category=False,
            llm_classified_categories=[],
            category_results_count=0,
            resource_results_count=1,
            low_confidence_fallback=False,
        ),
        retrieved_contexts=["context"],
        retrieved_scores=[0.8],
        db_diagnosis=None,
        evaluation_trace={},
        correctness_explanation="ok",
        evidence=[],
        question="Q?",
        expected_answer="A",
        llm_answer="A",
        is_correct=True,
        storage_hit=True,
        retrieval_hit=True,
        rank_position=1,
        category=1,
        error=None,
    )
    report = SimpleNamespace(
        sample_index=0,
        character="caroline",
        total_memories=1,
        total_questions=1,
        results=[result],
    )

    path = save_converted_results_json([report], tmp_path, eval_mode="assistant_eval")
    payload = path.read_text(encoding="utf-8")

    assert "\"run_manifest\"" in payload


def test_candidate_projection_results_include_run_manifest():
    report = PersonaMemReport(
        sample_index=0,
        character="66_candidate_views",
        user_id="candidate-user",
        total_sessions=0,
        total_memories=0,
        total_questions=0,
        results=[],
        chat_model="Model-A",
        evaluator_model="Judge-1",
        evaluator_isolated=True,
    )

    data = build_candidate_results_data(
        report,
        eval_mode="assistant_eval",
        test_info={"split": "benchmark_text", "top_k": 10},
    )

    assert data["run_manifest"]["persona_id"] == "66_candidate_views"
    assert data["run_manifest"]["evaluator_model"] == "Judge-1"


def test_candidate_projection_comparison_report_includes_run_manifest(tmp_path):
    report = {
        "test_info": {"eval_mode": "storage_eval", "top_k": 10, "persona_id": "66"},
        "run_manifest": build_run_manifest(
            harness="personamem_v2_candidate_view_structured_projection",
            eval_mode="storage_eval",
            dataset="bowen-upenn/PersonaMem-v2",
            persona_id="66",
            scoring_config=None,
            rerank_config=None,
        ),
        "baseline": {"metrics": {}},
        "candidate_structured_projection": {"metrics": {}},
        "delta": {},
        "candidate_projection": {
            "original_turn_count": 0,
            "candidate_count": 0,
            "written_candidate_count": 0,
            "skipped_candidate_count": 0,
            "written_by_type": {},
            "skipped_by_reason": {},
        },
    }

    json_path, _ = save_candidate_experiment_report(report, tmp_path)

    assert "run_manifest" in json_path.read_text(encoding="utf-8")


def test_bm25_and_rerank_manifests_include_rerank_config():
    bm25_args = SimpleNamespace(
        split="benchmark_text",
        persona_id="66",
        retrieve_top_k=30,
        answer_top_k=15,
        bm25_k1=1.2,
        bm25_b=0.75,
        input_retrieval_json=None,
    )
    rerank_args = SimpleNamespace(
        split="benchmark_text",
        persona_id="66",
        retrieve_top_k=30,
        answer_top_k=15,
        rerank_model="GLM-Rerank",
        input_retrieval_json=None,
    )

    bm25_manifest = build_bm25_run_manifest(bm25_args, question_count=42)
    rerank_manifest = build_rerank_run_manifest(rerank_args, question_count=42)

    assert bm25_manifest["rerank_config"]["type"] == "bm25"
    assert bm25_manifest["question_count"] == 42
    assert bm25_manifest["harness"] == "personamem_v2_legacy_bm25_rerank_diagnostic"
    assert bm25_manifest["formal_ab_eligible"] is False
    assert bm25_manifest["experiment_conclusion"] == "diagnostic_only"
    assert rerank_manifest["rerank_config"]["type"] == "glm_rerank"
    assert rerank_manifest["rerank_config"]["rerank_model"] == "GLM-Rerank"
    assert rerank_manifest["harness"] == "personamem_v2_legacy_glm_rerank_diagnostic"
    assert rerank_manifest["formal_ab_eligible"] is False
    assert rerank_manifest["experiment_conclusion"] == "diagnostic_only"


def _comparison_item(question: str, *, is_correct: bool, answerable: bool) -> dict[str, object]:
    return {
        "persona_id": "66",
        "source_split": "benchmark_text",
        "row_index": question,
        "question": question,
        "is_correct": is_correct,
        "retrieval_stage": {"answerable_context_hit": answerable},
    }
