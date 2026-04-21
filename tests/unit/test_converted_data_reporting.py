from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from tests.evals.converted_data.metrics import calculate_metrics_from_qa_dicts
from tests.evals.converted_data.report_analysis import (
    build_analysis_prompt,
    build_fallback_analysis_markdown,
)
from tests.evals.converted_data.report_json import LiveResultWriter, save_results_json


def _results_data(eval_mode: str, qa_results: list[dict]):
    return {
        "test_info": {"eval_mode": eval_mode},
        "statistics": {},
        "samples": [
            {
                "sample_index": 0,
                "character": "caroline",
                "qa_results": qa_results,
            }
        ],
    }


def test_storage_metrics_and_report_do_not_talk_about_llm_answers():
    qa = [
        {"eval_mode": "storage_eval", "is_correct": True, "storage_hit": True, "category": 1},
        {"eval_mode": "storage_eval", "is_correct": False, "storage_hit": False, "category": 1},
    ]
    metrics = calculate_metrics_from_qa_dicts(qa, eval_mode="storage_eval")
    assert metrics["storage_coverage_rate"] == 50
    assert "storage_hit_rate" not in metrics
    assert metrics["category_accuracy"]["1"]["display_name"] == "Category 1 - 事实回忆（单一事实）"

    markdown = build_fallback_analysis_markdown(
        _results_data("storage_eval", qa),
        Path("storage_results.json"),
        eval_mode="storage_eval",
    )
    assert "存储覆盖率" in markdown
    assert "Category 1 - 事实回忆（单一事实）" in markdown
    assert "失败原因" in markdown
    assert "LLM回答正确率" not in markdown
    assert "Retrieval hit rate" not in markdown


def test_retrieval_metrics_focus_on_rank_and_recall():
    qa = [
        {
            "eval_mode": "retrieval_eval",
            "is_correct": True,
            "storage_hit": True,
            "retrieval_hit": True,
            "rank_position": 1,
            "category": 1,
            "retrieval_layer": {"resolved_layer": "resource_only"},
        },
        {
            "eval_mode": "retrieval_eval",
            "is_correct": False,
            "storage_hit": True,
            "retrieval_hit": False,
            "rank_position": None,
            "category": 1,
            "retrieval_layer": {"resolved_layer": "category_only"},
        },
    ]
    metrics = calculate_metrics_from_qa_dicts(qa, eval_mode="retrieval_eval")
    assert metrics["recall_at_k"] == 50
    assert "retrieval_hit_rate" not in metrics
    assert metrics["top1_hit_rate"] == 50

    markdown = build_fallback_analysis_markdown(
        _results_data("retrieval_eval", qa),
        Path("retrieval_results.json"),
        eval_mode="retrieval_eval",
    )
    assert "Recall@K" in markdown
    assert "retrieval_hit_rate" not in markdown
    assert "成功模式" in markdown
    assert "LLM回答正确率" not in markdown


def test_assistant_report_keeps_adjusted_accuracy_and_chain_attribution():
    qa = [
        {
            "eval_mode": "assistant_eval",
            "is_correct": True,
            "storage_hit": True,
            "retrieval_hit": True,
            "standard_answer": "school",
            "generated_answer": "She is at school.",
            "category": 1,
            "retrieval_layer": {"resolved_layer": "resource_only"},
        },
        {
            "eval_mode": "assistant_eval",
            "is_correct": True,
            "storage_hit": True,
            "retrieval_hit": True,
            "standard_answer": "",
            "generated_answer": "I don't have enough information.",
            "category": 5,
            "retrieval_layer": {"resolved_layer": "none"},
        },
    ]
    metrics = calculate_metrics_from_qa_dicts(qa, eval_mode="assistant_eval")
    assert metrics["answer_accuracy"] == 100
    assert metrics["adjusted_accuracy_excluding_empty_standard"] == 100
    assert metrics["non_empty_answer_questions"] == 1
    assert metrics["retrieval_support_rate"] == 100

    markdown = build_fallback_analysis_markdown(
        _results_data("assistant_eval", qa),
        Path("assistant_results.json"),
        eval_mode="assistant_eval",
    )
    assert "这轮 trace 能直接证明什么" in markdown
    assert "回答准确率" in markdown
    assert "adjusted accuracy" in markdown
    assert "失败原因" in markdown
    assert "成功模式" in markdown


def test_analysis_prompt_is_mode_aware_and_data_driven():
    qa = [{"eval_mode": "retrieval_eval", "is_correct": True, "retrieval_hit": True, "rank_position": 1}]
    prompt = build_analysis_prompt(
        _results_data("retrieval_eval", qa),
        Path("retrieval_results.json"),
        eval_mode="retrieval_eval",
    )
    assert "本次 eval_mode: retrieval_eval" in prompt
    assert "LLM 回答正确率" not in prompt
    assert "2023/2026" not in prompt
    assert "category 5" not in prompt
    assert "category_display" in prompt


def test_assistant_report_explains_failure_and_success_reasons():
    qa = [
        {
            "eval_mode": "assistant_eval",
            "question": "When did Caroline go to the LGBTQ support group?",
            "standard_answer": "4 January 2026",
            "generated_answer": "I do not know.",
            "is_correct": False,
            "storage_hit": True,
            "retrieval_hit": False,
            "category": 2,
            "retrieval_layer": {"resolved_layer": "category_only"},
            "retrieved_contexts": ["Noise context"],
            "retrieved_scores": [0.11],
            "trace_detail": {
                "db_diagnosis": {
                            "diagnosis_type": "retrieval_gap",
                            "missed_in_retrieval": [
                        {
                            "matched_keyword": "the",
                            "text_preview": "The user attended an LGBTQ support group on 4 January 2026.",
                        }
                            ],
                        }
            },
            "evaluation_trace": {
                "storage_eval": {
                    "db_memories_sample": [
                        {"matched_keyword": "the", "text": "Candidate evidence"},
                    ]
                }
            },
        },
        {
            "eval_mode": "assistant_eval",
            "question": "What is Caroline's identity?",
            "standard_answer": "Transgender woman",
            "generated_answer": "I am not sure.",
            "is_correct": False,
            "storage_hit": True,
            "retrieval_hit": False,
            "category": 1,
            "retrieval_layer": {"resolved_layer": "category_only"},
            "retrieved_contexts": ["User's name is Caro."],
            "retrieved_scores": [0.72],
            "trace_detail": {
                "db_diagnosis": {
                    "diagnosis_type": "retrieval_gap",
                    "missed_in_retrieval": [
                        {"matched_keyword": "identity", "text_preview": "The user is a transgender woman."},
                        {"matched_keyword": "woman", "text_preview": "The user is proud to be a woman."},
                    ],
                },
                "evaluation_trace": {
                    "storage_eval": {
                        "db_memories_sample": [
                            {"matched_keyword": "identity", "text": "Candidate memory"},
                        ]
                    }
                },
            },
        },
        {
            "eval_mode": "assistant_eval",
            "question": "What did Caroline research?",
            "standard_answer": "Adoption agencies",
            "generated_answer": "Adoption agencies",
            "is_correct": True,
            "storage_hit": True,
            "retrieval_hit": False,
            "category": 1,
            "retrieval_layer": {"resolved_layer": "category+resource"},
            "retrieved_contexts": ["The user researched adoption agencies."],
            "retrieved_scores": [0.87],
        },
    ]
    markdown = build_fallback_analysis_markdown(
        _results_data("assistant_eval", qa),
        Path("assistant_results.json"),
        eval_mode="assistant_eval",
    )
    assert "本报告只基于当前 JSON trace 可直接支撑的事实下结论" in markdown
    assert "这轮 assistant 失败主要表现为“回答层缺少可用证据”" in markdown
    assert "较高置信的检索失配样本" in markdown
    assert "需要保守表述的样本" in markdown
    assert "这题较高置信属于检索失配" in markdown
    assert "该样本不能作为检索成功案例" in markdown


def test_save_results_json_compacts_top_level_and_keeps_trace_detail(tmp_path: Path):
    retrieval_layer = SimpleNamespace(
        resolved_layer="resource_only",
        is_sufficient_at_category=False,
        llm_classified_categories=["Career"],
        category_results_count=1,
        resource_results_count=3,
    )
    result = SimpleNamespace(
        question="What career is Caroline considering?",
        expected_answer="Counseling",
        llm_answer="Counseling",
        is_correct=True,
        category=3,
        storage_hit=True,
        retrieval_hit=True,
        rank_position=1,
        retrieval_layer=retrieval_layer,
        evaluation_trace={"storage_eval": {"storage_hit": True}},
        retrieved_contexts=["The user is considering counseling as a career.", "Second context"],
        retrieved_scores=[0.91, 0.72],
        db_diagnosis=None,
        correctness_explanation="Matches the gold answer.",
        evidence=["D1:9"],
        error=None,
    )
    report = SimpleNamespace(
        sample_index=0,
        character="Caroline",
        user_id="user-1",
        total_sessions=19,
        total_memories=100,
        total_questions=1,
        results=[result],
    )

    path = save_results_json([report], tmp_path, eval_mode="assistant_eval")
    data = json.loads(path.read_text(encoding="utf-8"))

    assert set(data["test_info"].keys()) == {"timestamp", "eval_mode"}
    assert "answer_accuracy" not in data["statistics"]
    assert "retrieval_support_rate" not in data["statistics"]

    sample = data["samples"][0]
    assert set(sample.keys()) == {
        "sample_index",
        "character",
        "total_memories",
        "total_questions",
        "completed_questions",
        "status",
        "qa_results",
    }
    assert sample["status"] == "completed"
    assert sample["completed_questions"] == 1

    qa = sample["qa_results"][0]
    assert qa["failure_type"] == "none"
    assert "trace_summary" in qa
    assert "trace_detail" in qa
    assert qa["trace_summary"]["top_contexts"] == ["The user is considering counseling as a career.", "Second context"]
    assert qa["trace_detail"]["correctness_explanation"] == "Matches the gold answer."
    assert qa["trace_detail"]["evidence"] == ["D1:9"]


def test_save_results_json_keeps_storage_db_sample_but_dedups_diagnosis_payload(tmp_path: Path):
    retrieval_layer = SimpleNamespace(
        resolved_layer="category_only",
        is_sufficient_at_category=True,
        llm_classified_categories=["Core Self"],
        category_results_count=5,
        resource_results_count=0,
    )
    repeated_db_sample = [
        {
            "id": "mem-1",
            "source": "resource",
            "text": "Candidate memory",
            "importance_score": 3,
            "updated_at": "2026-03-25T09:55:00+00:00",
            "matched_keyword": "the",
        }
    ]
    result = SimpleNamespace(
        question="When did Caroline go to the LGBTQ support group?",
        expected_answer="4 January 2026",
        llm_answer="Wrong answer",
        is_correct=False,
        category=2,
        storage_hit=True,
        retrieval_hit=False,
        rank_position=None,
        retrieval_layer=retrieval_layer,
        evaluation_trace={
            "storage_eval": {
                "storage_hit": True,
                "keywords": ["when", "lgbtq"],
                "db_hits": {"resource_count": 1, "category_count": 0},
                "db_memories_sample": repeated_db_sample,
            }
        },
        retrieved_contexts=["Noise memory"],
        retrieved_scores=[0.11],
        db_diagnosis={
            "diagnosis_type": "retrieval_gap",
            "summary": "DB evidence exists but was not retrieved.",
            "keywords": ["when", "lgbtq"],
            "db_hits": {"resource_count": 1, "category_count": 0},
            "db_memories_sample": repeated_db_sample,
            "matched_in_retrieved": [],
            "missed_in_retrieval": repeated_db_sample,
            "llm_verification": {"can_answer": False, "reason": "missing date"},
        },
        correctness_explanation="Dates do not match.",
        evidence=["D1:3"],
        error=None,
    )
    report = SimpleNamespace(
        sample_index=0,
        character="Caroline",
        user_id="user-1",
        total_sessions=19,
        total_memories=100,
        total_questions=1,
        results=[result],
    )

    path = save_results_json([report], tmp_path, eval_mode="assistant_eval")
    data = json.loads(path.read_text(encoding="utf-8"))
    qa = data["samples"][0]["qa_results"][0]

    assert qa["trace_detail"]["evaluation_trace"]["storage_eval"]["db_memories_sample"] == repeated_db_sample
    assert "db_memories_sample" not in qa["trace_detail"]["db_diagnosis"]
    assert "db_hits" not in qa["trace_detail"]["db_diagnosis"]
    assert "keywords" not in qa["trace_detail"]["db_diagnosis"]
    assert qa["trace_detail"]["db_diagnosis"]["diagnosis_type"] == "retrieval_gap"
    assert qa["trace_detail"]["db_diagnosis"]["matched_in_retrieved"] == []

    missed = qa["trace_detail"]["db_diagnosis"]["missed_in_retrieval"][0]
    assert set(missed.keys()) == {
        "id",
        "source",
        "importance_score",
        "updated_at",
        "matched_keyword",
        "text_preview",
    }
    assert missed["text_preview"] == "Candidate memory"
    assert "text" not in missed


def test_save_results_json_compacts_matched_and_missed_retrieval_items_to_previews(tmp_path: Path):
    retrieval_layer = SimpleNamespace(
        resolved_layer="resource_only",
        is_sufficient_at_category=True,
        llm_classified_categories=["Goals"],
        category_results_count=1,
        resource_results_count=2,
    )
    long_text = (
        "The user expressed their dream of creating a safe and loving home for children in need, "
        "emphasizing that love and acceptance are fundamental rights that everyone deserves."
    )
    memory_item = {
        "id": "mem-2",
        "source": "resource",
        "text": long_text,
        "importance_score": 2,
        "updated_at": "2026-03-25T09:55:00+00:00",
        "matched_keyword": "home",
    }
    result = SimpleNamespace(
        question="What kind of home does the user want to create?",
        expected_answer="A safe and loving home for children in need.",
        llm_answer="A safe and loving home.",
        is_correct=True,
        category=1,
        storage_hit=True,
        retrieval_hit=True,
        rank_position=1,
        retrieval_layer=retrieval_layer,
        evaluation_trace={"storage_eval": {"db_memories_sample": [memory_item]}},
        retrieved_contexts=[long_text],
        retrieved_scores=[0.88],
        db_diagnosis={
            "diagnosis_type": "retrieval_ok",
            "summary": "Relevant evidence was retrieved.",
            "matched_in_retrieved": [memory_item],
            "missed_in_retrieval": [memory_item],
        },
        correctness_explanation="Answer is supported.",
        evidence=["D1:1"],
        error=None,
    )
    report = SimpleNamespace(
        sample_index=0,
        character="Caroline",
        user_id="user-1",
        total_sessions=10,
        total_memories=30,
        total_questions=1,
        results=[result],
    )

    path = save_results_json([report], tmp_path, eval_mode="assistant_eval")
    data = json.loads(path.read_text(encoding="utf-8"))
    diagnosis = data["samples"][0]["qa_results"][0]["trace_detail"]["db_diagnosis"]

    matched = diagnosis["matched_in_retrieved"][0]
    missed = diagnosis["missed_in_retrieval"][0]

    for item in (matched, missed):
        assert "text" not in item
        assert item["id"] == "mem-2"
        assert item["matched_keyword"] == "home"
        assert item["text_preview"].startswith("The user expressed their dream")
        assert item["text_preview"].endswith("...")
        assert len(item["text_preview"]) <= 160

    full_storage_text = data["samples"][0]["qa_results"][0]["trace_detail"]["evaluation_trace"]["storage_eval"][
        "db_memories_sample"
    ][0]["text"]
    assert full_storage_text == long_text


def test_live_result_writer_persists_in_progress_sample_with_completed_question_count(tmp_path: Path):
    writer = LiveResultWriter(tmp_path, eval_mode="assistant_eval")
    writer.start_sample(
        sample_index=0,
        character="Caroline",
        user_id="user-1",
        total_sessions=10,
        total_memories=30,
        total_questions=2,
    )
    writer.add_qa_result(
        {
            "eval_mode": "assistant_eval",
            "question": "What career is Caroline considering?",
            "standard_answer": "Counseling",
            "generated_answer": "Counseling",
            "is_correct": True,
            "category": 3,
            "storage_hit": True,
            "retrieval_hit": True,
            "rank_position": 1,
            "retrieval_layer": {"resolved_layer": "resource_only"},
            "retrieved_contexts": ["The user is considering counseling as a career."],
            "retrieved_scores": [0.91],
            "evaluation_trace": {"storage_eval": {"storage_hit": True}},
            "db_diagnosis": None,
            "correctness_explanation": "Matches the gold answer.",
            "evidence": ["D1:9"],
            "error": None,
        }
    )

    data = json.loads(writer.results_path.read_text(encoding="utf-8"))
    sample = data["samples"][0]
    assert sample["status"] == "in_progress"
    assert sample["total_questions"] == 2
    assert sample["completed_questions"] == 1
    assert len(sample["qa_results"]) == 1

    writer.finish_sample(status="interrupted")
    final_data = json.loads(writer.results_path.read_text(encoding="utf-8"))
    assert final_data["samples"][0]["status"] == "interrupted"
