from tests.evals.converted_data.retrieval_tuning_ab import (
    QuestionProbe,
    _classify_effect,
    _rank_candidates,
)


class _FakeResource:
    def __init__(self, resource_id: str, description: str, importance_score: int = 3, updated_at=None):
        self.id = resource_id
        self.description = description
        self.raw_content = description
        self.importance_score = importance_score
        self.updated_at = updated_at


class _FakeCategory:
    def __init__(self, category_id: str, category_name: str, content: str, importance_score: int = 3, updated_at=None):
        self.id = category_id
        self.category_name = category_name
        self.content = content
        self.importance_score = importance_score
        self.updated_at = updated_at


def test_classify_effect_prefers_route_blocked_when_all_variants_stop_at_category_only():
    payload = {
        name: {
            "resolved_layer": "category_only",
            "retrieval_hit": False,
            "shadow_resource_hit": False,
        }
        for name in ("A", "B", "C", "D")
    }
    assert _classify_effect(payload) == "neither helps because route stops at category_only"


def test_classify_effect_detects_scoring_help():
    payload = {
        "A": {"resolved_layer": "category+resource", "retrieval_hit": False, "shadow_resource_hit": False},
        "B": {"resolved_layer": "category+resource", "retrieval_hit": True, "shadow_resource_hit": True},
        "C": {"resolved_layer": "category+resource", "retrieval_hit": False, "shadow_resource_hit": False},
        "D": {"resolved_layer": "category+resource", "retrieval_hit": True, "shadow_resource_hit": True},
    }
    assert _classify_effect(payload) == "scoring helps"


def test_classify_effect_does_not_call_it_help_when_baseline_already_hits():
    payload = {
        name: {
            "resolved_layer": "category_only",
            "retrieval_hit": True,
            "shadow_resource_hit": False,
        }
        for name in ("A", "B", "C", "D")
    }
    assert _classify_effect(payload) == "neither helps"


def test_rank_candidates_prefers_resource_with_more_anchor_matches():
    probe = QuestionProbe(
        question="What workshop did Caroline attend recently?",
        expected_answer="LGBTQ+ counseling workshop",
        anchors=("attended an LGBTQ+ counseling workshop", "January 23, 2026"),
    )
    resources = [
        _FakeResource("r1", "The user attended an LGBTQ+ counseling workshop on Friday, January 23, 2026."),
        _FakeResource("r2", "The user attended a workshop."),
    ]
    categories = [
        _FakeCategory("c1", "Timeline", "The user attended an LGBTQ+ counseling workshop."),
    ]
    ranked = _rank_candidates(resources, categories, probe)
    assert ranked[0].source == "resource"
    assert ranked[0].id == "r1"
    assert ranked[0].match_score == 2
