from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.config import settings
from tests.conftest import _assert_real_db_usage_is_safe
from tests.evals.common.run_manifest import build_run_manifest, finalize_run_manifest
from tests.evals.converted_data.report_json import save_results_json as save_converted_results_json
from tests.evals.personamem_v2.analysis import build_personamem_analysis_markdown
from tests.evals.personamem_v2.candidate_view_reporting import build_candidate_results_data
from tests.evals.personamem_v2.models import PersonaMemReport, PersonaMemResult
from tests.evals.personamem_v2 import runner as personamem_runner
from tests.evals.personamem_v2.bm25_eval import build_bm25_run_manifest
from tests.evals.personamem_v2.candidate_view_experiment import save_candidate_experiment_report
from tests.evals.personamem_v2.candidate_view_experiment import build_candidate_paired_comparison
from tests.evals.personamem_v2.official_summary import build_official_persona66_summary
from tests.evals.personamem_v2.bucket_schema import (
    BUCKET_SCHEMA_VERSION,
    bucket_schema_payload,
    classify_with_bucket_schema,
)
from tests.evals.personamem_v2.rerank_eval import build_rerank_run_manifest
from tests.evals.personamem_v2.reporting import (
    build_bucket_report,
    build_model_sweep_ranking_key,
    build_paired_comparison,
    build_personamem_statistics_from_qa_results,
    build_statistical_confidence,
    determine_experiment_conclusion,
)
from tests.evals.personamem_v2.report_contract import (
    recommended_result_subdir,
    validate_personamem_report_contract,
    validate_result_artifact_layout,
)
from tests.evals.personamem_v2.runner import (
    _resolve_evaluator_model,
    build_arg_parser,
    build_db_snapshot_id,
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
        db_snapshot_id="db-snap-1",
        dataset_hash="dataset-hash",
        result_file_path="result.json",
        temperature=0.7,
        cache_hash="cache-hash",
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
        "db_snapshot_id",
        "dataset_hash",
        "result_file_path",
        "temperature",
        "cache_hash",
        "started_at",
        "finished_at",
        "duration_seconds",
        "result_schema_version",
    }
    assert required <= set(manifest)
    assert manifest["git_sha"] == "abc123"
    assert manifest["db_snapshot_id"] == "db-snap-1"
    assert manifest["dataset_hash"] == "dataset-hash"
    assert manifest["result_file_path"] == "result.json"
    assert manifest["temperature"] == 0.7
    assert manifest["cache_hash"] == "cache-hash"


def test_finalize_run_manifest_computes_duration_from_iso_z_times(tmp_path):
    manifest = build_run_manifest(
        harness="personamem_v2",
        eval_mode="assistant_eval",
        started_at="2026-05-20T00:00:00Z",
    )

    finalize_run_manifest(
        manifest,
        result_file_path=tmp_path / "result.json",
        finished_at="2026-05-20T00:00:01.234Z",
    )

    assert manifest["duration_seconds"] == 1.234
    assert manifest["result_file_path"] == str(tmp_path / "result.json")


def test_finalize_run_manifest_rejects_negative_duration():
    manifest = build_run_manifest(
        harness="personamem_v2",
        eval_mode="assistant_eval",
        started_at="2026-05-20T00:00:02Z",
    )

    finalize_run_manifest(manifest, finished_at="2026-05-20T00:00:01Z")

    assert manifest["duration_seconds"] is None


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


def test_personamem_v2_pytest_entry_real_db_write_requires_explicit_allow(monkeypatch):
    monkeypatch.setattr(settings, "database_url", "postgresql+asyncpg://user:pass@localhost/mymem")
    config = _FakePytestConfig(
        {
            "--allow-real-db-write": False,
            "--converted-sample": None,
            "--converted-all": False,
            "--personamem-v2": True,
            "--personamem-v2-orthogonal": False,
            "--personamem-v2-diagnostic-rerank": None,
            "--personamem-v2-generator-replay-context-snapshot": None,
            "--personamem-v2-retrieval-only": False,
            "--personamem-v2-import-only": False,
            "--personamem-v2-reset-memory": False,
            "--converted-retrieval-only": False,
            "--converted-import-only": False,
            "--converted-reset-memory": False,
        }
    )

    with pytest.raises(pytest.UsageError, match="PersonaMem-v2"):
        _assert_real_db_usage_is_safe(config)


@pytest.mark.asyncio
async def test_model_sweep_default_evaluator_is_fixed_to_original_model(monkeypatch, tmp_path):
    calls = []

    async def fake_run_personamem_v2_eval(**kwargs):
        calls.append(kwargs)
        result = _result(is_correct=True, answerable=True)
        return [
            PersonaMemReport(
                sample_index=0,
                character="66",
                user_id=f"user-{kwargs['chat_model']}",
                db_snapshot_id=f"db:{kwargs['chat_model']}",
                total_sessions=1,
                total_memories=1,
                total_questions=1,
                results=[result],
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
    assert payload["run_manifest"]["db_snapshot_id"].startswith("db-sweep:")


@pytest.mark.asyncio
async def test_model_sweep_forwards_timeout_and_output_dir(monkeypatch, tmp_path):
    calls = []

    async def fake_run_personamem_v2_eval(**kwargs):
        calls.append(kwargs)
        result = _result(is_correct=True, answerable=True)
        return [
            PersonaMemReport(
                sample_index=0,
                character="66",
                user_id="user-1",
                db_snapshot_id="db:user-1",
                total_sessions=1,
                total_memories=1,
                total_questions=1,
                results=[result],
                chat_model=kwargs["chat_model"],
                evaluator_model="Judge-Default",
                evaluator_isolated=False,
            )
        ]

    def fake_save_model_sweep_summary(**kwargs):
        return {"ranked_models": [], "output_dir": str(kwargs["output_dir"])}

    monkeypatch.setattr(personamem_runner, "run_personamem_v2_eval", fake_run_personamem_v2_eval)
    monkeypatch.setattr(personamem_runner, "save_model_sweep_summary", fake_save_model_sweep_summary)

    payload = await personamem_runner.run_personamem_v2_model_sweep(
        chat_models=["Model-A"],
        retrieval_only=True,
        output_dir=tmp_path,
        question_timeout_seconds=42,
    )

    assert calls[0]["output_dir"] == tmp_path
    assert calls[0]["question_timeout_seconds"] == 42
    assert payload["output_dir"] == str(tmp_path)


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


def test_report_contract_rejects_accuracy_only_report():
    report = {
        "run_manifest": build_run_manifest(
            harness="personamem_v2",
            eval_mode="assistant_eval",
            dataset="bowen-upenn/PersonaMem-v2",
            chat_model="Model-A",
            evaluator_model="Judge-1",
            top_k=10,
            scoring_config={},
            rerank_config=None,
            db_snapshot_id="db:1",
            dataset_hash="dataset",
            cache_hash="cache",
            temperature=0.7,
        ),
        "statistics": {"accuracy": 100.0},
        "samples": [],
    }
    finalize_run_manifest(report["run_manifest"], result_file_path="result.json")

    contract = validate_personamem_report_contract(report)

    assert contract["valid"] is False
    assert "primary_metrics.answerable_context_hit_at_k_missing" in contract["issues"]
    assert "missing_row_level_retrieval_and_answer_stage_payloads" in contract["issues"]


def test_report_contract_accepts_evidence_first_report():
    report = _contract_report()

    contract = validate_personamem_report_contract(report)

    assert contract["valid"] is True


def test_report_contract_rejects_empty_provenance_fields():
    report = _contract_report()
    report["run_manifest"]["db_snapshot_id"] = None

    contract = validate_personamem_report_contract(report)

    assert contract["valid"] is False
    assert "run_manifest.db_snapshot_id_empty" in contract["issues"]


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
    assert paired["evidence_gain"] == 2
    assert paired["evidence_regression"] == 0
    assert paired["per_row"][0]["answer_outcome"] in {"win", "loss", "stable_success", "stable_failure"}
    assert paired["bucket_report"]
    assert paired["statistical_confidence"]["answer_paired_win_loss"]["discordant_n"] == 2


def test_bucket_report_tracks_required_evidence_and_answer_metrics():
    qa_results = [
        {
            "question": "What exact snack does Caroline like?",
            "standard_answer": "warm cocoa",
            "supporting_preference": "Caroline likes warm cocoa.",
            "is_correct": True,
            "retrieval_stage": {
                "answerable_context_hit": True,
                "target_answer_anchor_hit": True,
                "retrieval_failure_subtype": "none",
            },
        },
        {
            "question": "What should Caroline do for adoption advice?",
            "standard_answer": "make a checklist",
            "supporting_preference": "Caroline wanted adoption advice.",
            "is_correct": False,
            "retrieval_stage": {
                "answerable_context_hit": False,
                "target_answer_anchor_hit": False,
                "retrieval_failure_subtype": "target_evidence_not_retrieved",
            },
        },
    ]

    report = build_bucket_report(qa_results)

    assert report["exact_fact"]["sample_count"] == 1
    assert report["exact_fact"]["answer_accuracy"] == 100
    assert report["broad_advice"]["target_evidence_not_retrieved_count"] == 1
    assert report["broad_advice"]["bucket_schema_version"] == BUCKET_SCHEMA_VERSION
    assert report["broad_advice"]["matched_patterns"]


def test_bucket_schema_exposes_stable_sources_for_required_buckets():
    schema = bucket_schema_payload()

    assert schema["version"] == BUCKET_SCHEMA_VERSION
    assert set(schema["buckets"]) >= {
        "exact_fact",
        "broad_advice",
        "negative_constraint",
        "sensitive_info",
        "third_person_narrative",
        "quoted_artifact",
        "forget_request",
        "time_date_question",
    }
    bucket, source = classify_with_bucket_schema({
        "question": "Please forget that I like watercolor painting. What should I do instead?",
        "supporting_preference": "Do not remember watercolor painting.",
    })
    assert bucket == "forget_request"
    assert source["evidence_source"]


def test_statistical_confidence_marks_small_samples_as_diagnostic():
    confidence = build_statistical_confidence({"gain": 3, "regression": 1, "evidence_gain": 2, "evidence_regression": 0})

    assert confidence["answer_paired_win_loss"]["paired_delta"] == 2
    assert "normal_approx_ci_95" in confidence["answer_paired_win_loss"]
    assert confidence["answer_paired_win_loss"]["decision_strength"] == "diagnostic_small_sample"


def test_statistical_confidence_zero_discordant_is_inconclusive():
    confidence = build_statistical_confidence({"gain": 0, "regression": 0, "evidence_gain": 0, "evidence_regression": 0})

    assert confidence["answer_paired_win_loss"]["normal_approx_ci_95"] == [0, 0]
    assert confidence["answer_paired_win_loss"]["decision_strength"] == "inconclusive"


def test_statistical_confidence_large_delta_marks_direction():
    positive = build_statistical_confidence({"gain": 35, "regression": 1, "evidence_gain": 35, "evidence_regression": 1})
    negative = build_statistical_confidence({"gain": 1, "regression": 35, "evidence_gain": 1, "evidence_regression": 35})

    assert positive["answer_paired_win_loss"]["decision_strength"] == "candidate_win_supported"
    assert negative["answer_paired_win_loss"]["decision_strength"] == "candidate_regression_supported"


@pytest.mark.asyncio
async def test_build_db_snapshot_id_is_stable_for_same_user_state(monkeypatch):
    fake_resources = [
        SimpleNamespace(
            id="r1",
            raw_content="The user likes warm cocoa.",
            description="likes warm cocoa",
            importance_score=2,
            modality="text",
            created_at=None,
            updated_at=None,
        )
    ]
    fake_categories = [
        SimpleNamespace(
            id="c1",
            category_name="Core Self",
            content="Likes warm cocoa.",
            importance_score=2,
            created_at=None,
            updated_at=None,
        )
    ]

    class FakeResourceRepository:
        def __init__(self, session):
            self.session = session

        get_by_user_id = AsyncMock(return_value=fake_resources)

    class FakeCategoryRepository:
        def __init__(self, session):
            self.session = session

        get_by_user_id = AsyncMock(return_value=fake_categories)

    monkeypatch.setattr(personamem_runner, "ResourceRepository", FakeResourceRepository)
    monkeypatch.setattr(personamem_runner, "CategoryRepository", FakeCategoryRepository)

    first = await build_db_snapshot_id(object(), "user-1")
    second = await build_db_snapshot_id(object(), "user-1")

    assert first == second
    assert first.startswith("db:")


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
        db_snapshot_id="db:candidate-user",
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
        "paired_comparison": {
            "shared_questions": 0,
            "gain": 0,
            "regression": 0,
            "evidence_gain": 0,
            "evidence_regression": 0,
            "statistical_confidence": {},
            "formal_ab_eligible": False,
        },
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


def test_candidate_projection_paired_comparison_uses_per_row_evidence():
    baseline = {
        "rows": [
            {
                "row_index": 1,
                "question": "What did Caroline research?",
                "is_correct": False,
                "retrieval_stage": {"answerable_context_hit": False},
            }
        ]
    }
    candidate = {
        "rows": [
            {
                "row_index": 1,
                "question": "What did Caroline research?",
                "is_correct": True,
                "retrieval_stage": {"answerable_context_hit": True},
            }
        ]
    }

    paired = build_candidate_paired_comparison(baseline, candidate)

    assert paired["gain"] == 1
    assert paired["evidence_gain"] == 1
    assert paired["per_row"][0]["answer_outcome"] == "win"
    assert paired["formal_ab_eligible"] is False


def test_official_persona66_summary_keeps_pairwise_diagnostic(tmp_path):
    paths = []
    for model, correct in [("GLM-5.1", False), ("GLM-5-Turbo", True)]:
        payload = _contract_report(chat_model=model, is_correct=correct, answerable=correct)
        path = tmp_path / f"{model}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        paths.append(path)

    summary = build_official_persona66_summary(paths, output_dir=tmp_path)

    assert summary["test_info"]["formal_ab_eligible"] is False
    assert summary["models"][0]["evaluator_model"] == "GLM-5"
    assert summary["pairwise_comparisons"][0]["formal_ab_eligible"] is False
    assert summary["pairwise_comparisons"][0]["paired_comparison"]["gain"] == 1
    assert Path(summary["json_path"]).exists()
    assert Path(summary["markdown_path"]).exists()


def test_official_persona66_summary_rejects_empty_result(tmp_path):
    payload = _contract_report(chat_model="GLM-5.1")
    payload["samples"] = []
    path = tmp_path / "empty.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="no QA rows"):
        build_official_persona66_summary([path], output_dir=tmp_path)


def test_official_persona66_summary_can_require_focus_models(tmp_path):
    payload = _contract_report(chat_model="GLM-5.1")
    path = tmp_path / "glm51.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="missing focus models"):
        build_official_persona66_summary([path], output_dir=tmp_path, require_focus_models=True)


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


def test_result_artifact_layout_rejects_logs_in_official_dir(tmp_path):
    for name in ("official", "legacy", "diagnostic", "scratch", "logs"):
        (tmp_path / name).mkdir()
    (tmp_path / "official" / "result.json").write_text("{}", encoding="utf-8")
    (tmp_path / "official" / "run.log").write_text("log", encoding="utf-8")

    layout = validate_result_artifact_layout(tmp_path)

    assert layout["valid"] is False
    assert "diagnostic_artifact_in_official:run.log" in layout["issues"]


def test_recommended_result_subdir_separates_official_diagnostic_and_legacy():
    assert recommended_result_subdir(official=True) == "official"
    assert recommended_result_subdir(diagnostic=True) == "diagnostic"
    assert recommended_result_subdir(legacy=True) == "legacy"
    assert recommended_result_subdir() == "scratch"
    with pytest.raises(ValueError):
        recommended_result_subdir(official=True, diagnostic=True)


def _comparison_item(question: str, *, is_correct: bool, answerable: bool) -> dict[str, object]:
    return {
        "persona_id": "66",
        "source_split": "benchmark_text",
        "row_index": question,
        "question": question,
        "is_correct": is_correct,
        "retrieval_stage": {"answerable_context_hit": answerable},
    }


class _FakePytestConfig:
    def __init__(self, options: dict[str, object]):
        self.options = options

    def getoption(self, name: str) -> object:
        return self.options.get(name)


def _result(*, is_correct: bool, answerable: bool) -> PersonaMemResult:
    result = PersonaMemResult(
        question="What cozy drink does the user like?",
        expected_answer="warm cocoa",
        persona_id="66",
        preference="The user likes warm cocoa.",
        related_conversation_snippet="The user likes warm cocoa.",
        retrieved_contexts=["The user likes warm cocoa." if answerable else "The user likes tea."],
        retrieved_scores=[0.9],
        retrieval_hit=answerable,
        rank_position=1 if answerable else None,
        is_correct=is_correct,
        llm_answer="warm cocoa" if is_correct else "tea",
    )
    return result


def _contract_report(
    *,
    chat_model: str = "Model-A",
    is_correct: bool = True,
    answerable: bool = True,
) -> dict[str, object]:
    primary = {
        "answerable_context_hit_at_k": 100.0 if answerable else 0.0,
        "target_preference_hit_at_k": 100.0 if answerable else 0.0,
        "target_answer_anchor_hit_at_k": 100.0 if answerable else 0.0,
        "wrong_neighbor_substitution_rate": 0.0 if answerable else 100.0,
        "target_evidence_not_retrieved_rate": 0.0 if answerable else 100.0,
        "accuracy": 100.0 if is_correct else 0.0,
    }
    manifest = build_run_manifest(
        harness="personamem_v2",
        eval_mode="assistant_eval",
        dataset="bowen-upenn/PersonaMem-v2",
        split="benchmark_text",
        persona_id="66",
        question_count=1,
        import_only=False,
        retrieval_only=True,
        reset_memory=False,
        chat_model=chat_model,
        evaluator_model="GLM-5",
        evaluator_isolated=True,
        top_k=10,
        scoring_config={},
        rerank_config=None,
        db_snapshot_id=f"db:{chat_model}",
        dataset_hash=f"dataset:{chat_model}",
        cache_hash=f"cache:{chat_model}",
        temperature=0.7,
        started_at="2026-05-20T00:00:00Z",
    )
    finalize_run_manifest(
        manifest,
        result_file_path=f"{chat_model}.json",
        finished_at="2026-05-20T00:00:01Z",
    )
    stage = {
        "answerable_context_hit": answerable,
        "target_answer_anchor_hit": answerable,
        "retrieval_failure_subtype": "none" if answerable else "target_evidence_not_retrieved",
    }
    return {
        "run_manifest": manifest,
        "statistics": {
            "total_questions": 1,
            "accuracy": primary["accuracy"],
            "bucket_report": {
                "exact_fact": {
                    "sample_count": 1,
                    "answer_accuracy": primary["accuracy"],
                    "evidence_hit_rate": primary["answerable_context_hit_at_k"],
                }
            },
            "personamem_evidence": {
                "evidence_first_summary": {"primary_metrics": primary}
            },
        },
        "samples": [
            {
                "qa_results": [
                    {
                        "persona_id": "66",
                        "source_split": "benchmark_text",
                        "row_index": 1,
                        "question": "What does the user like?",
                        "standard_answer": "warm cocoa",
                        "is_correct": is_correct,
                        "retrieval_stage": stage,
                        "answer_stage": stage,
                    }
                ]
            }
        ],
    }
