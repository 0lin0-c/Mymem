from __future__ import annotations

from tests.evals.converted_data.runner import EvalMode, TestResult, postprocess_bad_case_diagnoses


class _DummyLayer:
    resolved_layer = "resource_only"
    is_sufficient_at_category = False
    llm_classified_categories = []
    category_results_count = 0
    resource_results_count = 0


async def _fake_diagnose_bad_case(**kwargs):
    return {
        "diagnosis_type": "retrieval_gap",
        "summary": f"diagnosed: {kwargs['question']}",
        "matched_in_retrieved": [],
        "missed_in_retrieval": [],
        "llm_verification": None,
    }


async def test_postprocess_bad_case_diagnoses_only_fills_failed_results(monkeypatch):
    monkeypatch.setattr("tests.evals.converted_data.runner.diagnose_bad_case", _fake_diagnose_bad_case)
    monkeypatch.setattr("services.llm.factory.LLMFactory.get_provider", lambda: object())

    ok_result = TestResult(
        question="ok question",
        expected_answer="ok",
        category=1,
        evidence=["D1:1"],
        eval_mode=EvalMode.ASSISTANT.value,
    )
    ok_result.retrieval_layer = _DummyLayer()
    ok_result.retrieved_contexts = ["context"]
    ok_result.is_correct = True

    bad_result = TestResult(
        question="bad question",
        expected_answer="bad",
        category=2,
        evidence=["D1:2"],
        eval_mode=EvalMode.ASSISTANT.value,
    )
    bad_result.retrieval_layer = _DummyLayer()
    bad_result.retrieved_contexts = ["missing context"]
    bad_result.is_correct = False

    results = [ok_result, bad_result]
    await postprocess_bad_case_diagnoses(
        session=object(),
        user_id="user-1",
        results=results,
        eval_mode=EvalMode.ASSISTANT,
    )

    assert ok_result.db_diagnosis is None
    assert bad_result.db_diagnosis is not None
    assert bad_result.db_diagnosis["diagnosis_type"] == "retrieval_gap"
    assert "bad question" in bad_result.db_diagnosis["summary"]
