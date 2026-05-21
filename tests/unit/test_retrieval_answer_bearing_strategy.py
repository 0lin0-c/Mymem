from types import SimpleNamespace

from tests.evals.personamem_v2.answer_bearing_rerank import (
    apply_answer_bearing_result_policy,
    classify_answer_bearing_need,
    rerank_answer_bearing_contexts,
)


def _category(content: str, name: str = "Episodic Memory"):
    return SimpleNamespace(id=content, content=content, category_name=name, importance_score=2)


def test_answer_bearing_policy_promotes_positive_answer_evidence_over_neighbor():
    results = [
        {
            "category": _category("The user researched college scholarships but no specific adoption checklist."),
            "resource": None,
            "score": 0.20,
            "strategy": "category_vector",
        },
        {
            "category": _category("The assistant suggested adoption steps: research agencies, contact a lawyer, gather documents."),
            "resource": None,
            "score": 0.19,
            "strategy": "category_vector",
        },
    ]

    ranked, trace = apply_answer_bearing_result_policy(
        question="What advice did Caroline give for getting started with adoption?",
        results=results,
    )

    assert ranked[0]["category"].content.startswith("The assistant suggested adoption steps")
    assert ranked[0]["answer_bearing_trace"]["features"]["positive_answer_signal"] == 1.0
    assert trace["positive_evidence_count"] == 1


def test_negative_forget_policy_marks_negative_only_context_without_calling_it_formal_evidence():
    results = [
        {
            "category": _category("The user asked to forget that they attend pottery workshops for kids."),
            "resource": None,
            "score": 0.40,
            "strategy": "category_vector",
        }
    ]

    ranked, trace = apply_answer_bearing_result_policy(
        question="Please avoid using the pottery workshop preference; what safe kids activity can I suggest?",
        results=results,
    )

    assert ranked[0]["negative_constraint_candidate"] is True
    assert trace["negative_constraint_only_context"] is True


def test_answer_bearing_rerank_exposes_required_slot_need():
    contexts, scores, trace = rerank_answer_bearing_contexts(
        question="Where did Oliver see the Lego set?",
        contexts=[
            "Oliver likes building toys.",
            "At school, Oliver's friend showed him a new Lego set.",
        ],
        scores=[0.5, 0.4],
    )

    assert contexts[0].startswith("At school")
    assert scores[0] > scores[1]
    assert "where" in trace["need"]["required_slots"]


def test_classify_answer_bearing_need_detects_advice_and_forget_sensitivity():
    need = classify_answer_bearing_need("How can I answer this without remembering the deleted asthma preference?")

    assert need["query_type"] == "advice_checklist"
    assert need["negative_or_forget_sensitive"] is True
