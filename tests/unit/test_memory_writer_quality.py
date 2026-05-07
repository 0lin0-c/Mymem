from services.memory.writer import _normalize_atomic_item_for_storage


def test_quality_filter_drops_low_confidence_item():
    item = _normalize_atomic_item_for_storage({
        "category_name": "Core Self",
        "content": "The user may like thunderstorms.",
        "importance_score": 2,
        "confidence": 0.40,
        "extraction_origin": "direct_user_statement",
    })

    assert item is None


def test_quality_filter_drops_third_person_core_self():
    item = _normalize_atomic_item_for_storage({
        "category_name": "Core Self",
        "content": "The user values creative/resourceful solutions.",
        "importance_score": 3,
        "memory_type": "profile_fact",
        "confidence": 0.90,
        "extraction_origin": "third_person_narrative",
    })

    assert item is None


def test_quality_filter_caps_quoted_first_person_importance():
    item = _normalize_atomic_item_for_storage({
        "category_name": "Core Self",
        "content": "The user had an appendectomy at age 6.",
        "importance_score": 3,
        "memory_type": "profile_fact",
        "confidence": 0.95,
        "extraction_origin": "quoted_first_person",
    })

    assert item is not None
    assert item["importance_score"] == 2


def test_quality_filter_caps_third_person_episodic_importance():
    item = _normalize_atomic_item_for_storage({
        "category_name": "Episodic Memory",
        "content": "The user described witnessing a police incident through a narrative about Lena.",
        "importance_score": 3,
        "memory_type": "event_fact",
        "confidence": 0.55,
        "extraction_origin": "third_person_narrative",
    })

    assert item is not None
    assert item["importance_score"] == 1


def test_quality_filter_drops_assistant_advice_as_core_profile():
    item = _normalize_atomic_item_for_storage({
        "category_name": "Core Self",
        "content": "The user prefers taking regular hydration breaks.",
        "importance_score": 2,
        "memory_type": "profile_fact",
        "confidence": 0.90,
        "extraction_origin": "assistant_advice",
    })

    assert item is None
