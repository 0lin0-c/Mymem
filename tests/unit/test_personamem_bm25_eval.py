from types import SimpleNamespace

import pytest

from tests.evals.personamem_v2.bm25_eval import (
    bm25_rerank_results,
    tokenize_bm25_text,
)


def _result(description: str, score: float = 0.1) -> dict:
    return {
        "resource": SimpleNamespace(
            id=description,
            user_id="u1",
            modality="text",
            description=description,
            description_vector=None,
            raw_content="",
            importance_score=2,
            assistant_response="",
            access_count=0,
            created_at=None,
            updated_at=None,
        ),
        "category": None,
        "score": score,
        "strategy": "vector",
    }


def test_tokenize_bm25_filters_stopwords_but_keeps_negation_terms():
    tokens = tokenize_bm25_text("The user should not forget the warm cocoa, never.")

    assert "the" not in tokens
    assert "should" not in tokens
    assert "not" in tokens
    assert "forget" in tokens
    assert "never" in tokens
    assert "cocoa" in tokens


def test_bm25_rerank_prefers_document_with_query_terms():
    results = [
        _result("The user enjoys gardening with their grandmother."),
        _result("The user likes warm cocoa with marshmallows on chilly evenings."),
        _result("The user asked about pottery safety for children."),
    ]

    reranked, trace = bm25_rerank_results(
        query="cozy warm cocoa marshmallows",
        retrieved_results=results,
        top_n=2,
    )

    assert len(reranked) == 2
    assert "cocoa" in reranked[0]["resource"].description
    assert reranked[0]["bm25_score"] > reranked[1]["bm25_score"]
    assert trace["candidate_count"] == 3


def test_bm25_rerank_empty_query_keeps_original_candidate_order():
    results = [
        _result("First candidate"),
        _result("Second candidate"),
        _result("Third candidate"),
    ]

    reranked, trace = bm25_rerank_results(
        query="the and should",
        retrieved_results=results,
        top_n=2,
    )

    assert [item["resource"].description for item in reranked] == [
        "First candidate",
        "Second candidate",
    ]
    assert [item["bm25_score"] for item in reranked] == [0.0, 0.0]
    assert trace["empty_query"] is True


def test_bm25_rerank_empty_documents_returns_empty_list():
    reranked, trace = bm25_rerank_results(
        query="warm cocoa",
        retrieved_results=[],
        top_n=5,
    )

    assert reranked == []
    assert trace["candidate_count"] == 0


def test_bm25_rerank_top_n_zero_returns_empty_list_with_trace():
    results = [_result("Warm cocoa with marshmallows")]

    reranked, trace = bm25_rerank_results(
        query="warm cocoa",
        retrieved_results=results,
        top_n=0,
    )

    assert reranked == []
    assert trace["top_n"] == 0
    assert trace["candidate_count"] == 1


def test_bm25_rerank_equal_scores_keep_original_order():
    results = [
        _result("Warm cocoa one"),
        _result("Warm cocoa two"),
        _result("Warm cocoa three"),
    ]

    reranked, _ = bm25_rerank_results(
        query="warm cocoa",
        retrieved_results=results,
        top_n=3,
    )

    assert [item["resource"].id for item in reranked] == [
        "Warm cocoa one",
        "Warm cocoa two",
        "Warm cocoa three",
    ]
    assert [item["original_score"] for item in reranked] == [0.1, 0.1, 0.1]


def test_bm25_rerank_rejects_invalid_parameters():
    results = [_result("Warm cocoa with marshmallows")]

    with pytest.raises(ValueError, match="k1"):
        bm25_rerank_results(
            query="warm cocoa",
            retrieved_results=results,
            top_n=1,
            k1=0,
        )

    with pytest.raises(ValueError, match="b"):
        bm25_rerank_results(
            query="warm cocoa",
            retrieved_results=results,
            top_n=1,
            b=1.5,
        )


def test_bm25_rerank_limits_results_and_preserves_result_structure():
    results = [
        _result("Warm cocoa with marshmallows", score=0.9),
        _result("Warm vanilla milk", score=0.8),
    ]

    reranked, _ = bm25_rerank_results(
        query="warm cocoa",
        retrieved_results=results,
        top_n=1,
    )

    assert len(reranked) == 1
    assert "resource" in reranked[0]
    assert "score" in reranked[0]
    assert "strategy" in reranked[0]
    assert "bm25_score" in reranked[0]
    assert reranked[0]["original_score"] == 0.9
    assert reranked[0]["score"] == reranked[0]["bm25_score"]
