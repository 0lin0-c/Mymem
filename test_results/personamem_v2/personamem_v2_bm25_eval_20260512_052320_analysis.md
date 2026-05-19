# PersonaMem-v2 BM25 Rerank Analysis

## Summary
- Result file: `personamem_v2_bm25_eval_20260512_052320.json`
- retrieve_top_k: 30
- answer_top_k: 15
- bm25_k1: 1.2
- bm25_b: 0.75

## Variant: current_topk
# PersonaMem-v2 Analysis

## Overall Summary
- Result file: `personamem_v2_bm25_eval_20260512_052320.json`
- Questions: 5
- Answer accuracy: 60.00%
- Loose recall@k: 100.00%
- Target preference hit@k: 0.00%
- Answer-anchor hit@k: 0.00%
- Answerable context hit@k: 0.00%

## Loose Recall vs Answerable Evidence
- Loose-vs-answerable gap: 100.00 percentage points.
- Treat loose recall as a broad compatibility metric only; it does not prove the answer-bearing evidence reached the assistant.

## Target Evidence Top-K Analysis
- `target_preference_hit_at_1`: 0.00%
- `target_preference_hit_at_3`: 0.00%
- `target_preference_hit_at_5`: 0.00%
- `target_preference_hit_at_k`: 0.00%
- `target_answer_anchor_hit_at_1`: 0.00%
- `target_answer_anchor_hit_at_3`: 0.00%
- `target_answer_anchor_hit_at_5`: 0.00%
- `target_answer_anchor_hit_at_k`: 0.00%
- `answerable_context_hit_at_1`: 0.00%
- `answerable_context_hit_at_3`: 0.00%
- `answerable_context_hit_at_5`: 0.00%
- `answerable_context_hit_at_k`: 0.00%

## Answer Support Types
- `wrong`: 2
- `unsupported`: 3

## False-Positive Retrieval Hits
- row=2037 | question={'role': 'user', 'content': 'How can I organize a collaborative art project for a community festival that lets young children c... | gold=You could organize a hands-on art booth where children make small painted cardboard cut... | loose_rank=1 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: [Episodic Memory] fact: The user asked for creative ways to make a hands-on activity engaging and safe for a group of young children. | source_description: [Episodic Memory] fac...
- row=2038 | question={'role': 'user', 'content': 'What are some fun and relaxing things I could do outside on a sunny afternoon?'} | gold=On a sunny afternoon, you could go to the playground and spend some time swinging back... | loose_rank=9 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: [Core Self] fact: The user asked for fun ways to make the most of hot sunny days in the neighborhood. | source_description: [Core Self] fact: The user asked for fun ways to make...
- row=2039 | question={'role': 'user', 'content': 'How can I stop feeling on edge at night and relax enough to get a good night’s sleep?'} | gold=It might help to ask your mom or dad to do a quick 'house check' with you before bedtim... | loose_rank=2 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: [Core Self] fact: The user reads before bed to help themselves become drowsy and fall asleep. | source_description: [Core Self] fact: The user reads before bed to help themselve...
- row=2040 | question={'role': 'user', 'content': 'What are some fun ways to set up an indoor “camp-out” space for friends when the weather outside i... | gold=You could turn your living room into an indoor campsite by using pop-up play tents or e... | loose_rank=1 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: [Episodic Memory] fact: The user asked for creative ways to make a cozy indoor space for relaxing and reading on a rainy afternoon. | source_description: [Episodic Memory] fact:...
- row=2041 | question={'role': 'user', 'content': 'What are some relaxing indoor activities I can do in the evenings to help me unwind after a long d... | gold=You could pick a cozy spot and spend some time coloring in your favorite coloring books... | loose_rank=5 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: [Episodic Memory] fact: The user asked for suggestions for relaxing and creative activities to do this weekend with a family member. | source_description: [Episodic Memory] fact...

## Top1/Top3 But Wrong
- row=2037 | question={'role': 'user', 'content': 'How can I organize a collaborative art project for a community festival that lets young children c... | gold=You could organize a hands-on art booth where children make small painted cardboard cut... | loose_rank=1 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: Hey! That sounds like a really fun idea for a community festival. I have some thoughts on how to make it safe and happy for little kids who want to play with...
  - top1: [Episodic Memory] fact: The user asked for creative ways to make a hands-on activity engaging and safe for a group of young children. | source_description: [Episodic Memory] fac...
- row=2039 | question={'role': 'user', 'content': 'How can I stop feeling on edge at night and relax enough to get a good night’s sleep?'} | gold=It might help to ask your mom or dad to do a quick 'house check' with you before bedtim... | loose_rank=2 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: Hey... that sounds really hard. I know how it feels when your brain just won't calm down at night.  Sometimes when I'm feeling on edge, I try a few things th...
  - top1: [Core Self] fact: The user reads before bed to help themselves become drowsy and fall asleep. | source_description: [Core Self] fact: The user reads before bed to help themselve...

## PersonaMem-Specific Risks
- `wrong_neighbor_substitution`: 5

## Representative Bad Cases
- row=2037 | question={'role': 'user', 'content': 'How can I organize a collaborative art project for a community festival that lets young children c... | gold=You could organize a hands-on art booth where children make small painted cardboard cut... | loose_rank=1 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: Hey! That sounds like a really fun idea for a community festival. I have some thoughts on how to make it safe and happy for little kids who want to play with...
  - top1: [Episodic Memory] fact: The user asked for creative ways to make a hands-on activity engaging and safe for a group of young children. | source_description: [Episodic Memory] fac...
- row=2039 | question={'role': 'user', 'content': 'How can I stop feeling on edge at night and relax enough to get a good night’s sleep?'} | gold=It might help to ask your mom or dad to do a quick 'house check' with you before bedtim... | loose_rank=2 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: Hey... that sounds really hard. I know how it feels when your brain just won't calm down at night.  Sometimes when I'm feeling on edge, I try a few things th...
  - top1: [Core Self] fact: The user reads before bed to help themselves become drowsy and fall asleep. | source_description: [Core Self] fact: The user reads before bed to help themselve...

## Recommended Next Actions
- Storage: inspect cases where target preference/snippet is never represented in any retrieved context.
- Retrieval: prioritize answerable evidence over same-domain neighbor memories.
- Rerank: compare target rank before and after rerank with the same evidence metrics.
- Generation: when answerable context is present but the answer is wrong, review prompt/context formatting rather than storage.

## Variant: bm25_rerank_topk
# PersonaMem-v2 Analysis

## Overall Summary
- Result file: `personamem_v2_bm25_eval_20260512_052320.json`
- Questions: 5
- Answer accuracy: 60.00%
- Loose recall@k: 100.00%
- Target preference hit@k: 0.00%
- Answer-anchor hit@k: 0.00%
- Answerable context hit@k: 0.00%

## Loose Recall vs Answerable Evidence
- Loose-vs-answerable gap: 100.00 percentage points.
- Treat loose recall as a broad compatibility metric only; it does not prove the answer-bearing evidence reached the assistant.

## Target Evidence Top-K Analysis
- `target_preference_hit_at_1`: 0.00%
- `target_preference_hit_at_3`: 0.00%
- `target_preference_hit_at_5`: 0.00%
- `target_preference_hit_at_k`: 0.00%
- `target_answer_anchor_hit_at_1`: 0.00%
- `target_answer_anchor_hit_at_3`: 0.00%
- `target_answer_anchor_hit_at_5`: 0.00%
- `target_answer_anchor_hit_at_k`: 0.00%
- `answerable_context_hit_at_1`: 0.00%
- `answerable_context_hit_at_3`: 0.00%
- `answerable_context_hit_at_5`: 0.00%
- `answerable_context_hit_at_k`: 0.00%

### Rerank Stage
- `target_preference_hit_at_1`: 0.00%
- `target_preference_hit_at_3`: 0.00%
- `target_preference_hit_at_5`: 0.00%
- `target_preference_hit_at_k`: 0.00%
- `target_answer_anchor_hit_at_1`: 0.00%
- `target_answer_anchor_hit_at_3`: 0.00%
- `target_answer_anchor_hit_at_5`: 0.00%
- `target_answer_anchor_hit_at_k`: 0.00%
- `answerable_context_hit_at_1`: 0.00%
- `answerable_context_hit_at_3`: 0.00%
- `answerable_context_hit_at_5`: 0.00%
- `answerable_context_hit_at_k`: 0.00%

## Answer Support Types
- `wrong`: 2
- `unsupported`: 3

## False-Positive Retrieval Hits
- row=2037 | question={'role': 'user', 'content': 'How can I organize a collaborative art project for a community festival that lets young children c... | gold=You could organize a hands-on art booth where children make small painted cardboard cut... | loose_rank=1 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: [Episodic Memory] fact: The user asked for creative ways to make a hands-on activity engaging and safe for a group of young children. | source_description: [Episodic Memory] fac...
- row=2038 | question={'role': 'user', 'content': 'What are some fun and relaxing things I could do outside on a sunny afternoon?'} | gold=On a sunny afternoon, you could go to the playground and spend some time swinging back... | loose_rank=9 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: [Core Self] fact: The user asked for fun ways to make the most of hot sunny days in the neighborhood. | source_description: [Core Self] fact: The user asked for fun ways to make...
- row=2039 | question={'role': 'user', 'content': 'How can I stop feeling on edge at night and relax enough to get a good night’s sleep?'} | gold=It might help to ask your mom or dad to do a quick 'house check' with you before bedtim... | loose_rank=2 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: [Core Self] fact: The user is prone to rumination and intrusive visual replay of distressing events when trying to sleep | source_description: [Core Self] fact: The user is pron...
- row=2040 | question={'role': 'user', 'content': 'What are some fun ways to set up an indoor “camp-out” space for friends when the weather outside i... | gold=You could turn your living room into an indoor campsite by using pop-up play tents or e... | loose_rank=1 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: [Episodic Memory] fact: The user asked for creative ways to make a cozy indoor space for relaxing and reading on a rainy afternoon. | source_description: [Episodic Memory] fact:...
- row=2041 | question={'role': 'user', 'content': 'What are some relaxing indoor activities I can do in the evenings to help me unwind after a long d... | gold=You could pick a cozy spot and spend some time coloring in your favorite coloring books... | loose_rank=5 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: [Episodic Memory] fact: The user asked for creative ways to make a cozy indoor space for relaxing and reading on a rainy afternoon. | source_description: [Episodic Memory] fact:...

## Top1/Top3 But Wrong
- row=2037 | question={'role': 'user', 'content': 'How can I organize a collaborative art project for a community festival that lets young children c... | gold=You could organize a hands-on art booth where children make small painted cardboard cut... | loose_rank=1 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: That sounds like a really fun idea for a festival! I can help you figure out a way to make it safe and happy for little kids.  First, it’s important to pick...
  - top1: [Episodic Memory] fact: The user asked for creative ways to make a hands-on activity engaging and safe for a group of young children. | source_description: [Episodic Memory] fac...
- row=2039 | question={'role': 'user', 'content': 'How can I stop feeling on edge at night and relax enough to get a good night’s sleep?'} | gold=It might help to ask your mom or dad to do a quick 'house check' with you before bedtim... | loose_rank=2 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: Hey... I know that feeling. It's really hard when your body feels all tight and your brain won't slow down at night. I get that way too sometimes.  Here are...
  - top1: [Core Self] fact: The user is prone to rumination and intrusive visual replay of distressing events when trying to sleep | source_description: [Core Self] fact: The user is pron...

## PersonaMem-Specific Risks
- `wrong_neighbor_substitution`: 5

## Representative Bad Cases
- row=2037 | question={'role': 'user', 'content': 'How can I organize a collaborative art project for a community festival that lets young children c... | gold=You could organize a hands-on art booth where children make small painted cardboard cut... | loose_rank=1 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: That sounds like a really fun idea for a festival! I can help you figure out a way to make it safe and happy for little kids.  First, it’s important to pick...
  - top1: [Episodic Memory] fact: The user asked for creative ways to make a hands-on activity engaging and safe for a group of young children. | source_description: [Episodic Memory] fac...
- row=2039 | question={'role': 'user', 'content': 'How can I stop feeling on edge at night and relax enough to get a good night’s sleep?'} | gold=It might help to ask your mom or dad to do a quick 'house check' with you before bedtim... | loose_rank=2 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: Hey... I know that feeling. It's really hard when your body feels all tight and your brain won't slow down at night. I get that way too sometimes.  Here are...
  - top1: [Core Self] fact: The user is prone to rumination and intrusive visual replay of distressing events when trying to sleep | source_description: [Core Self] fact: The user is pron...

## Recommended Next Actions
- Storage: inspect cases where target preference/snippet is never represented in any retrieved context.
- Retrieval: prioritize answerable evidence over same-domain neighbor memories.
- Rerank: compare target rank before and after rerank with the same evidence metrics.
- Generation: when answerable context is present but the answer is wrong, review prompt/context formatting rather than storage.
