import asyncio
import json
from pathlib import Path

from core.database import AsyncSessionLocal
from repositories import UserRepository
from tests.evals.converted_data.runner import (
    EvalMode,
    _load_onboarding_profiles,
    parse_qa_file,
    run_layered_qa_evaluation,
    postprocess_bad_case_diagnoses,
    QAData,
)

QUESTIONS = [
    'When did Caroline go to the LGBTQ support group?',
    'When did Caroline meet up with her friends, family, and mentors?',
    'How long has Caroline had her current group of friends for?',
    'Who supports Caroline when she has a negative experience?',
    'What workshop did Caroline attend recently?',
]
PREV_PATH = Path('test_results/converted_data/legacy/mymem_test_results_20260422_010054.json')


def load_previous_results() -> dict[str, dict]:
    data = json.loads(PREV_PATH.read_text(encoding='utf-8'))
    out = {}
    for sample in data.get('samples', []):
        for r in sample.get('qa_results', []):
            q = r.get('question')
            if q in QUESTIONS:
                out[q] = {
                    'question': q,
                    'standard_answer': r.get('standard_answer'),
                    'generated_answer': r.get('generated_answer'),
                    'is_correct': r.get('is_correct'),
                    'resolved_layer': (r.get('trace_detail') or {}).get('retrieval_layer', {}).get('resolved_layer'),
                    'diagnosis_type': r.get('failure_type'),
                }
    return out


async def main():
    qa_path = Path('data/converted_data_recent_2026q1_name_trimmed/sample_0_qa.json')
    qa_data = parse_qa_file(qa_path)
    selected = [q for q in qa_data.questions if q.target_character == 'Caroline' and q.question in QUESTIONS]
    filtered = QAData(
        sample_index=qa_data.sample_index,
        characters=qa_data.characters,
        total_questions=len(selected),
        questions=selected,
    )

    profiles = _load_onboarding_profiles()
    username = profiles.get('sample_0_caroline', {}).get('username', 'sample_0_caroline')
    previous = load_previous_results()

    async with AsyncSessionLocal() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_username(username)
        if not user:
            raise RuntimeError(f'user not found: {username}')

        results = await run_layered_qa_evaluation(
            session=session,
            user_id=user.id,
            qa_data=filtered,
            live_writer=None,
            eval_mode=EvalMode.ASSISTANT,
        )
        await postprocess_bad_case_diagnoses(
            session=session,
            user_id=user.id,
            results=results,
            eval_mode=EvalMode.ASSISTANT,
        )

        out = []
        for r in results:
            current = {
                'question': r.question,
                'standard_answer': r.expected_answer,
                'generated_answer': r.llm_answer,
                'is_correct': r.is_correct,
                'correctness_explanation': r.correctness_explanation,
                'resolved_layer': r.retrieval_layer.resolved_layer,
                'is_sufficient_at_category': r.retrieval_layer.is_sufficient_at_category,
                'retrieved_contexts': r.retrieved_contexts[:5],
                'retrieved_scores': [round(s, 4) for s in r.retrieved_scores[:5]],
                'diagnosis_type': (r.db_diagnosis or {}).get('diagnosis_type'),
                'retrieval_failure_analysis': (r.db_diagnosis or {}).get('retrieval_failure_analysis'),
            }
            out.append({'question': r.question, 'previous': previous.get(r.question), 'current': current})
        print(json.dumps(out, ensure_ascii=False, indent=2))

asyncio.run(main())
