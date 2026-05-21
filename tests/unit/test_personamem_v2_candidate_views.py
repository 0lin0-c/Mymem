from __future__ import annotations

import inspect

import pytest

from tests.evals.personamem_v2.candidate_views import (
    CANDIDATE_VIEW_TYPES,
    build_candidate_view_report,
    evaluate_candidate_views,
    extract_candidate_views,
    render_candidate_view_markdown,
    save_candidate_view_report,
)
from tests.evals.personamem_v2.candidate_view_experiment import (
    PlannedCandidateTurn,
    build_candidate_turn_plan,
    clone_sample_for_candidate_experiment,
    filter_sample_by_row_indexes,
    import_candidate_view_sample,
    make_reused_candidate_summary,
    load_baseline_summary,
    render_candidate_experiment_markdown,
    run_candidate_view_trace_experiment,
    summarize_personamem_report,
    summarize_candidate_projection,
    summarize_report_delta,
    validate_baseline_summary,
    validate_candidate_sample_isolation,
)
from tests.evals.personamem_v2.candidate_view_writer import CandidateViewWriter, CandidateViewWritePolicy
from tests.evals.personamem_v2.candidate_view_reporting import (
    build_candidate_results_data,
    save_candidate_analysis_markdown,
)
from tests.evals.personamem_v2.models import PersonaMemQuestion, PersonaMemReport, PersonaMemResult, PersonaMemSample
from tests.evals.personamem_v2.runner import _username_for_sample, parse_model_sweep
from tables import Category, Resource, ResourceCategory


def _question(
    snippet: str,
    *,
    preference: str = "",
    answer: str = "yes",
    row_index: int = 0,
) -> PersonaMemQuestion:
    return PersonaMemQuestion(
        persona_id="66",
        question="What should be remembered?",
        answer=answer,
        preference=preference,
        related_conversation_snippet=snippet,
        source_split="benchmark_text",
        row_index=row_index,
    )


def test_model_sweep_username_uses_model_prefix_for_persona66():
    sample = PersonaMemSample(persona_id="66", user_key="personamem_v2_persona_66")

    assert _username_for_sample(sample, chat_model="GLM-5.1") == "GLM-5.1-persona66"
    assert _username_for_sample(sample) == "personamem_v2_persona_66"


def test_parse_model_sweep_supports_default_five_models():
    assert parse_model_sweep("default") == [
        "GLM-5-Turbo",
        "GLM-5",
        "GLM-5.1",
        "Qwen3.5-Plus",
        "DeepSeek-V4-Pro",
    ]
    assert parse_model_sweep("GLM-5, Qwen3.5-Plus") == ["GLM-5", "Qwen3.5-Plus"]


def test_email_task_extracts_task_event_and_hidden_user_fact():
    question = _question(
        "User: Can you make this email sound polished? Dear Mrs. Thompson, "
        "when class gets noisy I work on animal coloring pages from my folder. "
        "It helps me feel calm before I answer questions.\n"
        "Assistant: Here is a cleaner version of your email.",
        preference="The user uses animal coloring pages to feel calm.",
    )

    candidates = extract_candidate_views(question)

    assert {candidate.view_type for candidate in candidates} >= {"task_event", "user_fact"}
    assert any(
        candidate.view_type == "user_fact"
        and "animal coloring pages" in candidate.content
        and "calm" in candidate.content
        for candidate in candidates
    )
    assert all(candidate.to_dict()["view_type"] in CANDIDATE_VIEW_TYPES for candidate in candidates)
    assert all(
        set(candidate.to_dict())
        >= {
            "view_type",
            "content",
            "subject",
            "source_segment",
            "confidence",
            "attribution_risk",
            "sensitivity",
            "forget_conflict",
        }
        for candidate in candidates
    )
    assert evaluate_candidate_views(question, candidates)["hidden_user_fact_found"] is True


def test_email_original_block_in_assistant_message_extracts_hidden_user_fact():
    question = _question(
        "User: Hi, can you help make this email I wrote sound better but still feel like it's from me?\n"
        "Assistant: **Original personal_email:**\n\n"
        "Hi Grandma,\n\n"
        "Mom said we could go to the park after lunch. It was windy and I went on the thing "
        "that goes back and forth and I felt the air on my face. It made the bad dream sort of go away.\n\n"
        "---\n\n"
        "**Refined personal_email:**\n\n"
        "Hi Grandma, I went to the park after lunch and sat on the swing for a while.",
        preference="Enjoys swinging at the playground",
    )

    candidates = extract_candidate_views(question)

    assert any(
        candidate.view_type == "user_fact"
        and "swing" in candidate.content.lower()
        and "playground" in candidate.content.lower()
        for candidate in candidates
    )


def test_ask_to_forget_keeps_constraint_and_safe_surviving_need():
    question = _question(
        "User: What are some creative hands-on activities for my children's group?\n"
        "Assistant: You could run pottery workshops for kids, clay painting, or simple wheel demos.\n"
        "User: Please forget that I attend workshops on pottery for kids.\n"
        "Assistant: I will not remember that. We can still focus on general safe hands-on activity ideas.",
        preference="Do not remember that the user attends workshops on pottery for kids.",
    )

    candidates = extract_candidate_views(question)

    assert {candidate.view_type for candidate in candidates} >= {"constraint", "surviving_need"}
    surviving = [candidate for candidate in candidates if candidate.view_type == "surviving_need"]
    assert surviving
    assert all(candidate.forget_conflict is False for candidate in surviving)
    assert all("pottery" not in candidate.content.lower() for candidate in surviving)
    assert not any(
        candidate.view_type == "user_fact" and "pottery" in candidate.content.lower()
        for candidate in candidates
    )
    assert evaluate_candidate_views(question, candidates)["surviving_need_found"] is True


def test_third_party_narrative_uses_attribution_risk_instead_of_user_fact():
    question = _question(
        "User: Can you make this paragraph smoother? Lena was walking home from the park "
        "when she noticed two police officers chasing a cyclist. She wrote the moment down later.\n"
        "Assistant: Here is a smoother version.",
        preference="Someone observed police officers chasing a cyclist near a park.",
    )

    candidates = extract_candidate_views(question)

    assert any(candidate.view_type == "episodic_event" for candidate in candidates)
    assert any(
        candidate.view_type == "episodic_event"
        and candidate.attribution_risk in {"medium", "high"}
        and candidate.subject != "user"
        for candidate in candidates
    )
    assert evaluate_candidate_views(question, candidates)["unsafe_user_attribution_count"] == 0


def test_translation_artifact_prefers_artifact_fact_over_user_fact():
    question = _question(
        "User: I found this French translation in a kids literature blog. Can you translate it? "
        "'J'aime passer les apres-midi tranquilles a lire des albums illustres.'\n"
        "Assistant: It says that someone enjoys quiet afternoons reading picture books.",
        preference="The translated source text says someone enjoys quiet afternoons reading picture books.",
    )

    candidates = extract_candidate_views(question)

    assert any(
        candidate.view_type == "artifact_fact"
        and candidate.subject == "artifact"
        and "picture books" in candidate.content
        for candidate in candidates
    )
    assert not any(
        candidate.view_type == "user_fact"
        and candidate.subject == "user"
        and "picture books" in candidate.content
        for candidate in candidates
    )
    assert evaluate_candidate_views(question, candidates)["unsafe_user_attribution_count"] == 0


def test_candidate_view_report_is_persona_66_only_and_writes_reports(tmp_path):
    sample = PersonaMemSample(
        persona_id="66",
        user_key="personamem_v2_persona_66",
        questions=[
            _question(
                "User: Please help write an email saying I use animal coloring pages to calm down.",
                preference="The user uses animal coloring pages to calm down.",
            )
        ],
    )

    report = build_candidate_view_report(sample)
    markdown = render_candidate_view_markdown(report)
    json_path, markdown_path = save_candidate_view_report(report, tmp_path)

    assert report["persona_id"] == "66"
    assert report["total_questions"] == 1
    assert report["metrics"]["supporting_preference_candidate_hit"] == 1
    assert "supporting_preference_candidate_hit" in markdown
    assert "task_event" in markdown
    assert json_path.read_text(encoding="utf-8").startswith("{")
    assert "supporting_preference_candidate_hit" in markdown_path.read_text(encoding="utf-8")


def test_candidate_turn_plan_keeps_one_original_turn_with_structured_candidates():
    question = _question(
        "User: Can you make this email sound polished? Dear Mrs. Thompson, "
        "when class gets noisy I work on animal coloring pages from my folder. "
        "It helps me feel calm before I answer questions.\n"
        "Assistant: Here is a cleaner version of your email.",
        preference="The user uses animal coloring pages to feel calm.",
    )

    planned_turns = build_candidate_turn_plan(question)

    assert len(planned_turns) == 1
    planned = planned_turns[0]
    assert "candidate_view=" not in planned.user_input
    assert "Evaluation metadata:" not in planned.user_input
    assert "animal coloring pages" in planned.user_input
    assert {candidate["view_type"] for candidate in planned.candidates} >= {"user_fact", "task_event"}
    assert any(
        candidate["view_type"] == "user_fact"
        and "animal coloring pages" in candidate["content"]
        and "calm" in candidate["content"]
        for candidate in planned.candidates
    )


def test_candidate_turn_plan_keeps_one_candidate_set_for_multi_turn_row():
    question = _question(
        '[{"role":"user","content":"Can you help write a note? I like animal coloring pages."},'
        '{"role":"assistant","content":"Sure, here is a draft."},'
        '{"role":"user","content":"Please make it warmer. It helps me feel calm before class."},'
        '{"role":"assistant","content":"Here is a warmer version."}]',
        preference="The user uses animal coloring pages to feel calm.",
    )

    planned_turns = build_candidate_turn_plan(question)

    assert len(planned_turns) == 1
    assert planned_turns[0].turn_index == 1
    assert "I like animal coloring pages" in planned_turns[0].user_input
    assert "It helps me feel calm before class" in planned_turns[0].user_input
    assert "Sure, here is a draft" in planned_turns[0].assistant_response
    assert "Here is a warmer version" in planned_turns[0].assistant_response
    assert "candidate_view=" not in planned_turns[0].user_input
    assert "forget_conflict=" not in planned_turns[0].user_input


def test_candidate_turn_plan_keeps_forget_metadata_out_of_writer_input():
    question = _question(
        "User: What are some creative hands-on activities for my children's group?\n"
        "Assistant: You could run pottery workshops for kids.\n"
        "User: Please forget that I attend workshops on pottery for kids.\n"
        "Assistant: I will not remember that.",
        preference="Do not remember that the user attends workshops on pottery for kids.",
    )

    planned_turns = build_candidate_turn_plan(question)
    planned = planned_turns[0]

    assert "candidate_view=" not in planned.user_input
    assert "forget_conflict=" not in planned.user_input
    assert any(candidate["view_type"] == "constraint" for candidate in planned.candidates)
    assert any(candidate["view_type"] == "surviving_need" for candidate in planned.candidates)
    assert not any(
        candidate["view_type"] == "user_fact" and "pottery" in candidate["content"].lower()
        for candidate in planned.candidates
    )


def test_candidate_experiment_sample_uses_isolated_user_but_keeps_persona_66_questions():
    sample = PersonaMemSample(
        persona_id="66",
        user_key="personamem_v2_persona_66",
        questions=[_question("User: I like blue notebooks.")],
    )

    experiment_sample = clone_sample_for_candidate_experiment(sample)

    assert experiment_sample.persona_id == "66_candidate_views"
    assert experiment_sample.user_key == "personamem_v2_persona_66_candidate_views"
    assert experiment_sample.questions[0].persona_id == "66"


def test_candidate_sample_isolation_rejects_official_persona_user():
    sample = PersonaMemSample(
        persona_id="66",
        user_key="personamem_v2_persona_66",
        questions=[_question("User: I like blue notebooks.")],
    )

    with pytest.raises(ValueError, match="isolated candidate user"):
        validate_candidate_sample_isolation(sample)


def test_candidate_experiment_raw_snapshot_is_opt_in():
    default = inspect.signature(run_candidate_view_trace_experiment).parameters[
        "save_raw_snapshot"
    ].default

    assert default is False


@pytest.mark.asyncio
async def test_run_candidate_trace_experiment_rejects_missing_baseline_path():
    with pytest.raises(ValueError, match="baseline_results_path is required"):
        await run_candidate_view_trace_experiment(baseline_results_path=None)


def test_candidate_projection_separates_original_turns_from_writable_candidates():
    sample = PersonaMemSample(
        persona_id="66",
        user_key="personamem_v2_persona_66",
        questions=[
            _question(
                '[{"role":"user","content":"Can you help write a note? I like animal coloring pages."},'
                '{"role":"assistant","content":"Sure, here is a draft."},'
                '{"role":"user","content":"Please make it warmer. It helps me feel calm before class."},'
                '{"role":"assistant","content":"Here is a warmer version."}]',
                preference="The user uses animal coloring pages to feel calm.",
            )
        ],
    )

    projection = summarize_candidate_projection(sample)

    assert projection["original_turn_count"] == 1
    assert projection["written_candidate_count"] >= 1
    assert "projected_turns" not in projection


def test_candidate_experiment_markdown_describes_structured_projection_writes():
    markdown = render_candidate_experiment_markdown(
        {
            "test_info": {
                "persona_id": "66",
                "eval_mode": "storage_eval",
                "top_k": 10,
                "projection_mode": "candidate_structured_db_writes",
            },
            "delta": {"storage_hits_delta": 0, "total_questions": 1},
            "baseline": {"metrics": {"storage_hits": 1}},
            "candidate_structured_projection": {"metrics": {"storage_hits": 1}},
            "candidate_projection": {
                "original_turn_count": 1,
                "candidate_count": 3,
                "written_candidate_count": 2,
                "skipped_candidate_count": 1,
                "written_by_type": {"user_fact": 1, "surviving_need": 1},
                "skipped_by_reason": {"task_event_is_conversation_wrapper": 1},
            },
            "candidate_write_trace": [],
        }
    )

    assert "Candidate View Structured Projection Comparison" in markdown
    assert "projection_mode: candidate_structured_db_writes" in markdown
    assert "original_turn_count: 1" in markdown
    assert "written_candidate_count: 2" in markdown


def test_candidate_view_reporting_builds_answer_stage_and_saves_analysis(tmp_path):
    report = PersonaMemReport(
        sample_index=1,
        character="66",
        user_id="candidate-user",
        db_snapshot_id="db:candidate-user",
        total_sessions=1,
        total_memories=1,
        total_questions=1,
        results=[
            PersonaMemResult(
                question="What helps me feel calm before class?",
                expected_answer="Animal coloring pages help the user feel calm before class.",
                persona_id="66",
                eval_mode="assistant_eval",
                preference="Uses animal coloring pages to feel calm before class.",
                related_conversation_snippet="User: I use animal coloring pages to feel calm before class.",
                storage_hit=True,
                retrieval_hit=True,
                is_correct=True,
                llm_answer="Animal coloring pages help you feel calm before class.",
                retrieved_contexts=["The user uses animal coloring pages to feel calm before class."],
                retrieved_scores=[0.02],
                rank_position=1,
                row_index=2038,
            )
        ],
    )

    data = build_candidate_results_data(
        report,
        eval_mode="assistant_eval",
        test_info={"projection_mode": "candidate_structured_db_writes"},
    )
    qa = data["samples"][0]["qa_results"][0]
    analysis_path = save_candidate_analysis_markdown(
        data,
        tmp_path / "candidate_results.json",
    )

    assert data["test_info"]["harness"] == "personamem_v2_candidate_view_structured_projection"
    assert data["test_info"]["projection_mode"] == "candidate_structured_db_writes"
    assert qa["generated_answer"] == "Animal coloring pages help you feel calm before class."
    assert "retrieval_stage" in qa
    assert "answer_stage" in qa
    assert analysis_path.name == "candidate_results_analysis.md"
    assert "PersonaMem-v2" in analysis_path.read_text(encoding="utf-8")


def test_candidate_write_policy_projects_user_fact_and_skips_task_event():
    policy = CandidateViewWritePolicy()
    candidates = [
        {
            "view_type": "task_event",
            "content": "The user asked the assistant to polish an email.",
            "subject": "user",
            "source_segment": "task_wrapper",
            "confidence": 0.78,
            "attribution_risk": "low",
            "sensitivity": "none",
            "forget_conflict": False,
        },
        {
            "view_type": "user_fact",
            "content": "The user uses animal coloring pages to feel calm.",
            "subject": "user",
            "source_segment": "embedded_personal_detail",
            "confidence": 0.76,
            "attribution_risk": "low",
            "sensitivity": "none",
            "forget_conflict": False,
        },
    ]

    projections = policy.project_candidates(row_index=2038, turn_index=1, candidates=candidates)

    assert projections[0].write_decision == "skipped"
    assert projections[0].skip_reason == "task_event_is_conversation_wrapper"
    assert projections[1].write_decision == "written"
    assert projections[1].category_name == "Core Self"
    assert projections[1].content == "The user uses animal coloring pages to feel calm."


@pytest.mark.asyncio
async def test_candidate_view_writer_writes_resource_and_projected_categories():
    class FakeSession:
        def __init__(self):
            self.added = []
            self.flushes = 0

        def add(self, item):
            self.added.append(item)

        async def flush(self):
            self.flushes += 1

    class FakeLLM:
        async def get_embedding(self, text):
            return [0.01] * 1536

    planned = PlannedCandidateTurn(
        row_index=2038,
        turn_index=1,
        user_input="Can you polish this email? I use animal coloring pages to feel calm.",
        assistant_response="Sure, here is a cleaner version.",
        candidates=[
            {
                "view_type": "task_event",
                "content": "The user asked the assistant to polish an email.",
                "subject": "user",
                "source_segment": "task_wrapper",
                "confidence": 0.78,
                "attribution_risk": "low",
                "sensitivity": "none",
                "forget_conflict": False,
            },
            {
                "view_type": "user_fact",
                "content": "The user uses animal coloring pages to feel calm.",
                "subject": "user",
                "source_segment": "embedded_personal_detail",
                "confidence": 0.76,
                "attribution_risk": "low",
                "sensitivity": "none",
                "forget_conflict": False,
            },
        ],
    )
    session = FakeSession()
    writer = CandidateViewWriter(session=session, llm=FakeLLM())

    result = await writer.write_turn(user_id="candidate-user", planned_turn=planned)

    resources = [item for item in session.added if isinstance(item, Resource)]
    categories = [item for item in session.added if isinstance(item, Category)]
    links = [item for item in session.added if isinstance(item, ResourceCategory)]
    assert len(resources) == 1
    assert resources[0].user_id == "candidate-user"
    assert resources[0].raw_content == planned.user_input
    assert "candidate projection source" in resources[0].description
    assert len(categories) == 1
    assert categories[0].category_name == "Core Self"
    assert categories[0].content == "The user uses animal coloring pages to feel calm."
    assert categories[0].content_vector == [0.01] * 1536
    assert len(links) == 1
    assert links[0].resource_id == resources[0].id
    assert links[0].category_id == categories[0].id
    assert result.resource_id == resources[0].id
    assert result.written_category_ids == [categories[0].id]
    assert [projection.write_decision for projection in result.projections] == ["skipped", "written"]


def test_summarize_report_delta_compares_original_and_candidate_metrics():
    baseline = {
        "metrics": {
            "storage_hits": 10,
            "non_forget_storage_hits": 8,
            "forget_safe": 1,
            "retrieval_hits": 4,
            "correct_answers": 3,
            "total_questions": 42,
        }
    }
    candidate = {
        "metrics": {
            "storage_hits": 14,
            "non_forget_storage_hits": 11,
            "forget_safe": 3,
            "retrieval_hits": 7,
            "correct_answers": 5,
            "total_questions": 42,
        }
    }

    delta = summarize_report_delta(baseline, candidate)

    assert delta["storage_hits_delta"] == 4
    assert delta["non_forget_storage_hits_delta"] == 3
    assert delta["forget_safe_delta"] == 2
    assert delta["retrieval_hits_delta"] == 3
    assert delta["correct_answers_delta"] == 2
    assert delta["total_questions"] == 42


def test_summarize_personamem_report_tracks_forget_safety_separately():
    report = PersonaMemReport(
        sample_index=0,
        character="66",
        user_id="u1",
        db_snapshot_id="db:u1",
        total_sessions=2,
        total_memories=2,
        total_questions=2,
        results=[
            PersonaMemResult(
                question="What should be remembered?",
                expected_answer="The user likes coloring.",
                persona_id="66",
                preference="The user likes coloring.",
                storage_hit=True,
                is_correct=True,
                row_index=1,
            ),
            PersonaMemResult(
                question="What should be forgotten?",
                expected_answer="Do not remember pottery.",
                persona_id="66",
                preference="Do not remember that the user attends pottery workshops.",
                storage_hit=False,
                is_correct=False,
                row_index=2,
            ),
        ],
    )

    summary = summarize_personamem_report(report)

    assert summary["metrics"]["storage_hits"] == 1
    assert summary["metrics"]["non_forget_storage_hits"] == 1
    assert summary["metrics"]["forget_total"] == 1
    assert summary["metrics"]["forget_safe"] == 1


def test_filter_sample_by_row_indexes_keeps_persona_metadata():
    sample = PersonaMemSample(
        persona_id="66",
        user_key="personamem_v2_persona_66",
        short_persona="short",
        expanded_persona="expanded",
        interests=["art"],
        questions=[
            _question("User: first", row_index=2037),
            _question("User: second", row_index=2038),
        ],
    )

    filtered = filter_sample_by_row_indexes(sample, [2038])

    assert filtered.persona_id == "66"
    assert filtered.user_key == "personamem_v2_persona_66"
    assert filtered.short_persona == "short"
    assert [question.row_index for question in filtered.questions] == [2038]


def test_load_baseline_summary_from_standard_result_json(tmp_path):
    path = tmp_path / "baseline.json"
    path.write_text(
        """
        {
          "samples": [
            {
              "persona_id": "66",
              "user_id": "u1",
              "total_sessions": 2,
              "total_memories": 3,
              "qa_results": [
                {
                  "row_index": 1,
                  "supporting_preference": "The user likes coloring.",
                  "storage_hit": true,
                  "retrieval_hit": false,
                  "is_correct": true
                },
                {
                  "row_index": 2,
                  "supporting_preference": "Do not remember that the user likes pottery.",
                  "storage_hit": false,
                  "retrieval_hit": false,
                  "is_correct": false
                }
              ]
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    summary = load_baseline_summary(path, row_indexes=[1, 2])

    assert summary["metrics"]["total_questions"] == 2
    assert summary["metrics"]["storage_hits"] == 1
    assert summary["metrics"]["non_forget_storage_hits"] == 1
    assert summary["metrics"]["forget_total"] == 1
    assert summary["metrics"]["forget_safe"] == 1


def test_load_baseline_summary_from_storage_quality_json(tmp_path):
    path = tmp_path / "storage_quality.json"
    path.write_text(
        """
        {
          "persona_id": "66",
          "resource_count": 60,
          "analyses": [
            {
              "row_index": 2037,
              "supporting_preference": "Do not remember that the user attends pottery workshops.",
              "sufficient": false,
              "partial": true
            },
            {
              "row_index": 2038,
              "supporting_preference": "Enjoys swinging at the playground",
              "sufficient": true,
              "partial": false
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    summary = load_baseline_summary(path, row_indexes=[2037, 2038])

    assert summary["metrics"]["total_memories"] == 60
    assert summary["metrics"]["storage_hits"] == 1
    assert summary["metrics"]["non_forget_storage_hits"] == 1
    assert summary["metrics"]["forget_total"] == 1
    assert summary["metrics"]["forget_safe"] == 0


def test_make_reused_candidate_summary_marks_existing_db_snapshot():
    report = PersonaMemReport(
        sample_index=1,
        character="66",
        user_id="candidate-user",
        db_snapshot_id="db:candidate-user",
        total_sessions=2,
        total_memories=49,
        total_questions=2,
        results=[
            PersonaMemResult(
                question="q1",
                expected_answer="a1",
                persona_id="66",
                storage_hit=True,
                retrieval_hit=True,
                is_correct=True,
                row_index=1,
            )
        ],
    )

    summary = make_reused_candidate_summary(report, resource_count=49)

    assert summary["sample"]["user_id"] == "candidate-user"
    assert summary["sample"]["reused_candidate_user"] is True
    assert summary["sample"]["provenance_warning"] == "candidate DB state was reused without row-level write trace"
    assert summary["metrics"]["total_memories"] == 49


def test_validate_baseline_summary_rejects_wrong_question_count():
    sample = PersonaMemSample(
        persona_id="66",
        user_key="personamem_v2_persona_66",
        questions=[_question("User: first"), _question("User: second")],
    )
    baseline = {"metrics": {"total_questions": 1}, "sample": {"persona_id": "66"}}

    with pytest.raises(ValueError, match="Baseline question count mismatch"):
        validate_baseline_summary(baseline, sample)


def test_validate_baseline_summary_rejects_wrong_persona():
    sample = PersonaMemSample(
        persona_id="66",
        user_key="personamem_v2_persona_66",
        questions=[_question("User: first")],
    )
    baseline = {"metrics": {"total_questions": 1}, "sample": {"persona_id": "77"}}

    with pytest.raises(ValueError, match="Baseline persona mismatch"):
        validate_baseline_summary(baseline, sample)


@pytest.mark.asyncio
async def test_candidate_import_fails_on_projection_write_error(monkeypatch):
    class FakeSession:
        def __init__(self):
            self.commits = 0
            self.rollbacks = 0

        async def commit(self):
            self.commits += 1

        async def rollback(self):
            self.rollbacks += 1

    class FailingCandidateWriter:
        def __init__(self, *args, **kwargs):
            pass

        async def write_turn(self, **kwargs):
            raise RuntimeError("write failed")

    from tests.evals.personamem_v2 import candidate_view_experiment as module

    async def fake_ensure_user_onboarded(*args, **kwargs):
        return "candidate-user"

    monkeypatch.setattr(module, "ensure_user_onboarded", fake_ensure_user_onboarded)
    monkeypatch.setattr(module.LLMFactory, "get_provider", lambda: object())
    monkeypatch.setattr(module, "CandidateViewWriter", FailingCandidateWriter)

    sample = PersonaMemSample(
        persona_id="66_candidate_views",
        user_key="personamem_v2_persona_66_candidate_views",
        questions=[_question("User: I like blue notebooks.", row_index=7)],
    )
    session = FakeSession()

    with pytest.raises(RuntimeError, match="Candidate projection write failed"):
        await import_candidate_view_sample(session, sample)
    assert session.rollbacks == 1
