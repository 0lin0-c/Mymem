from __future__ import annotations

from tests.evals.personamem_v2.loader import build_samples, snippet_to_turns


def test_build_samples_maps_personamem_fields():
    rows = [
        {
            "persona_id": 7,
            "short_persona": '{"persona": "A frequent hiker who enjoys practical food."}',
            "expanded_persona": '{"hobbies_interests": ["Hiking", "Trail cooking"], "occupation": {"title": "Teacher"}}',
            "user_query": "What snack should I suggest?",
            "correct_answer": "Suggest trail mix.",
            "incorrect_answers": ["Suggest cake."],
            "preference": "The user likes portable snacks.",
            "related_conversation_snippet": "I usually bring trail mix when traveling.",
            "pref_type": "food",
            "who": "user",
            "updated": "false",
        }
    ]

    samples = build_samples(rows, split="benchmark_text", max_personas=1, max_questions=1)

    assert len(samples) == 1
    sample = samples[0]
    assert sample.persona_id == "7"
    assert sample.user_key == "personamem_v2_persona_7"
    assert sample.short_persona
    assert sample.expanded_persona
    assert sample.interests[:2] == ["Hiking", "Trail cooking"]
    question = sample.questions[0]
    assert question.question == "What snack should I suggest?"
    assert question.answer == "Suggest trail mix."
    assert question.incorrect_answers == ["Suggest cake."]
    assert question.evidence == [
        "I usually bring trail mix when traveling.",
        "The user likes portable snacks.",
    ]
    assert question.pref_type == "food"
    assert question.who == "user"
    assert question.updated == "false"
    assert question.source_split == "benchmark_text"


def test_snippet_to_turns_uses_plain_snippet_as_memory_evidence():
    question = build_samples(
        [
            {
                "persona_id": "abc",
                "user_query": "What should the assistant remember?",
                "correct_answer": "The user likes concise answers.",
                "related_conversation_snippet": "Please keep answers concise.",
            }
        ],
        split="benchmark_text",
    )[0].questions[0]

    turns = snippet_to_turns(question)

    assert turns == [
        (
            "Preference evidence for persona abc: Please keep answers concise.",
            "I will remember this preference for future personalized answers.",
        )
    ]


def test_build_samples_respects_persona_and_question_limits():
    rows = [
        {"persona_id": "a", "user_query": "q1", "correct_answer": "a1"},
        {"persona_id": "a", "user_query": "q2", "correct_answer": "a2"},
        {"persona_id": "b", "user_query": "q3", "correct_answer": "a3"},
    ]

    samples = build_samples(rows, split="benchmark_text", max_personas=1, max_questions=1)

    assert [sample.persona_id for sample in samples] == ["a"]
    assert [question.question for question in samples[0].questions] == ["q1"]


def test_build_samples_can_filter_specific_persona():
    rows = [
        {"persona_id": "a", "user_query": "q1", "correct_answer": "a1"},
        {"persona_id": "b", "user_query": "q2", "correct_answer": "a2"},
        {"persona_id": "b", "user_query": "q3", "correct_answer": "a3"},
    ]

    samples = build_samples(rows, split="benchmark_text", persona_id="b", max_questions=None)

    assert [sample.persona_id for sample in samples] == ["b"]
    assert [question.question for question in samples[0].questions] == ["q2", "q3"]
