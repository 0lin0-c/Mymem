import asyncio
import json
from pathlib import Path

from core.database import AsyncSessionLocal
from services.llm.factory import LLMFactory
from services.retrieval.retriever import MemoryRetriever
from services.retrieval.scoring_config import RetrievalScoringConfig
from tests.evals.converted_data.loader import parse_qa_file
from tests.evals.converted_data.retrieval_tuning_ab import (
    DEFAULT_DATA_DIR,
    TARGET_QUESTION_PROBES,
    _find_user_id,
    _load_all_memory_texts,
    _rank_candidates,
    _run_read_only_retrieval,
    _variant_payload,
)

SIM_VALUES = [1.5, 2.0, 2.5, 3.0]
REC_VALUES = [1.0, 0.5, 0.25, 0.1]
TOPK_VALUES = [5, 10, 12]
ACCESS_POWER = 1.0
IMPORTANCE_POWER = 1.0
RECENCY_DECAY_DAYS = 60
CHARACTER = 'caroline'
SAMPLE = 0


def avg_rank(ranks):
    vals = [r for r in ranks if r is not None]
    return sum(vals) / len(vals) if vals else 999.0


async def main():
    qa_data = parse_qa_file(DEFAULT_DATA_DIR / f'sample_{SAMPLE}_qa.json')
    targets = [q for q in qa_data.questions if q.question in TARGET_QUESTION_PROBES]
    async with AsyncSessionLocal() as session:
        user_id = await _find_user_id(session, CHARACTER)
        llm = LLMFactory.get_provider()
        retriever = MemoryRetriever(session, llm)
        resources, categories = await _load_all_memory_texts(session, user_id)
        evidence_map = {
            q.question: _rank_candidates(resources, categories, TARGET_QUESTION_PROBES[q.question])
            for q in targets
        }

        rows = []
        for top_k in TOPK_VALUES:
            for sim in SIM_VALUES:
                for rec in REC_VALUES:
                    config = RetrievalScoringConfig(
                        recency_decay_days=RECENCY_DECAY_DAYS,
                        similarity_power=sim,
                        access_power=ACCESS_POWER,
                        recency_power=rec,
                        importance_power=IMPORTANCE_POWER,
                    )
                    per_question = []
                    hits = 0
                    route_blocks = 0
                    for qa in targets:
                        raw = await _run_read_only_retrieval(
                            retriever,
                            user_id=user_id,
                            query=qa.question,
                            top_k=top_k,
                            scoring_config=config,
                        )
                        payload = _variant_payload(
                            final_results=raw['final_results'],
                            shadow_resource_results=raw['shadow_resource_results'],
                            evidence_candidates=evidence_map[qa.question],
                        )
                        if payload['retrieval_hit']:
                            hits += 1
                        if payload['resolved_layer'] == 'category_only' and not payload['retrieval_hit']:
                            route_blocks += 1
                        per_question.append({
                            'question': qa.question,
                            'hit': payload['retrieval_hit'],
                            'rank': payload['rank_position'],
                            'layer': payload['resolved_layer'],
                            'top1': (payload['top_contexts'][0] if payload['top_contexts'] else None),
                        })
                    rows.append({
                        'top_k': top_k,
                        'similarity_power': sim,
                        'recency_power': rec,
                        'hits': hits,
                        'avg_rank': avg_rank([x['rank'] for x in per_question]),
                        'route_blocks': route_blocks,
                        'per_question': per_question,
                    })
                    print(f"done top_k={top_k} sim={sim} rec={rec} hits={hits} avg_rank={avg_rank([x['rank'] for x in per_question]):.2f} route_blocks={route_blocks}", flush=True)

    rows.sort(key=lambda x: (-x['hits'], x['route_blocks'], x['avg_rank'], x['top_k'], -x['similarity_power'], x['recency_power']))
    out = {
        'search_space': {
            'top_k': TOPK_VALUES,
            'similarity_power': SIM_VALUES,
            'recency_power': REC_VALUES,
            'access_power': ACCESS_POWER,
            'importance_power': IMPORTANCE_POWER,
            'recency_decay_days': RECENCY_DECAY_DAYS,
        },
        'best': rows[:10],
        'all': rows,
    }
    path = Path('test_results/retrieval/retrieval_tuning_grid_search_20260422.json')
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'RESULT_PATH={path.resolve()}')
    print('TOP10:')
    for row in rows[:10]:
        print(json.dumps({k: row[k] for k in ('top_k','similarity_power','recency_power','hits','avg_rank','route_blocks')}, ensure_ascii=False))

asyncio.run(main())
