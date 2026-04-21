from datetime import datetime, timezone

from tests.evals.converted_data.helpers import (
    extract_keywords,
    first_retrieved_rank,
    normalize_text,
    parse_session_date,
    parse_session_datetime,
)


def test_parse_session_date_converts_source_format():
    assert parse_session_date("1:56 pm on 8 May, 2023") == "2023-05-08 13:56:00"


def test_parse_session_datetime_returns_utc_datetime():
    assert parse_session_datetime("10:37 am on 27 June, 2023") == datetime(
        2023, 6, 27, 10, 37, tzinfo=timezone.utc
    )


def test_parse_session_date_returns_none_for_invalid_input():
    assert parse_session_date("not a converted-data date") is None
    assert parse_session_datetime("not a converted-data date") is None


def test_normalize_text_removes_whitespace_and_lowercases():
    assert normalize_text(" The User\nLikes Counseling ") == "theuserlikescounseling"


def test_extract_keywords_preserves_order_and_filters_stopwords():
    keywords = extract_keywords(
        question="What field is Caroline interested in?",
        standard_answer="Counseling and mental health",
        evidence=["Caroline said counseling felt meaningful."],
        limit=5,
    )

    assert keywords[:4] == ["what", "field", "caroline", "interested"]
    assert "answer" not in keywords


def test_first_retrieved_rank_finds_db_memory_inside_context():
    rank = first_retrieved_rank(
        db_memories=[{"text": "The user is interested in counseling"}],
        contexts=[
            "The user likes hiking.",
            "[Core Self] The user is interested in counseling.",
        ],
    )

    assert rank == 2


def test_first_retrieved_rank_returns_none_without_match():
    assert first_retrieved_rank(
        db_memories=[{"text": "The user is interested in counseling"}],
        contexts=["The user likes hiking."],
    ) is None

