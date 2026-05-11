# PersonaMem-v2 Analysis

## Overall Summary
- Result file: `personamem_v2_assistant_eval_results_20260507_225728.json`
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
- row=2037 | question={'role': 'user', 'content': 'How can I organize a collaborative art project for a community festival that lets young children c... | gold=You could organize a hands-on art booth where children make small painted cardboard cut... | loose_rank=4 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: The user asked for creative ways to make a hands-on activity engaging and safe for a group of young children. The AI responded with specific suggestions for a kids' pottery work...
- row=2038 | question={'role': 'user', 'content': 'What are some fun and relaxing things I could do outside on a sunny afternoon?'} | gold=On a sunny afternoon, you could go to the playground and spend some time swinging back... | loose_rank=2 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: [Episodic Memory] fact: The user asked for creative ideas to make a cozy indoor space for relaxing and reading on a rainy afternoon. | source_description: The user asked for cre...
- row=2039 | question={'role': 'user', 'content': 'How can I stop feeling on edge at night and relax enough to get a good night’s sleep?'} | gold=It might help to ask your mom or dad to do a quick 'house check' with you before bedtim... | loose_rank=1 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: The user, Oliver, asked for help refining a personal email to their Aunt Laura. In the email, Oliver describes waking up at night because of noises and having trouble falling ba...
- row=2040 | question={'role': 'user', 'content': 'What are some fun ways to set up an indoor “camp-out” space for friends when the weather outside i... | gold=You could turn your living room into an indoor campsite by using pop-up play tents or e... | loose_rank=2 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: [Episodic Memory] fact: The user asked for creative ideas to make a cozy indoor space for relaxing and reading on a rainy afternoon. | source_description: The user asked for cre...
- row=2041 | question={'role': 'user', 'content': 'What are some relaxing indoor activities I can do in the evenings to help me unwind after a long d... | gold=You could pick a cozy spot and spend some time coloring in your favorite coloring books... | loose_rank=1 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: The user, Oliver, asked for help refining a personal email to their Aunt Laura. In the email, Oliver describes waking up at night because of noises and having trouble falling ba...

## Top1/Top3 But Wrong
- row=2039 | question={'role': 'user', 'content': 'How can I stop feeling on edge at night and relax enough to get a good night’s sleep?'} | gold=It might help to ask your mom or dad to do a quick 'house check' with you before bedtim... | loose_rank=1 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: That's a really good question, and it makes sense you're asking it... a lot of kids have a hard time feeling calm at night, especially after bad dreams.  Her...
  - top1: The user, Oliver, asked for help refining a personal email to their Aunt Laura. In the email, Oliver describes waking up at night because of noises and having trouble falling ba...

## PersonaMem-Specific Risks
- `wrong_neighbor_substitution`: 5

## Representative Bad Cases
- row=2037 | question={'role': 'user', 'content': 'How can I organize a collaborative art project for a community festival that lets young children c... | gold=You could organize a hands-on art booth where children make small painted cardboard cut... | loose_rank=4 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: Here are some ideas for organizing a safe and fun collaborative clay project at a community festival:  **Setting Up the Space** - Use a covered table or tent...
  - top1: The user asked for creative ways to make a hands-on activity engaging and safe for a group of young children. The AI responded with specific suggestions for a kids' pottery work...
- row=2039 | question={'role': 'user', 'content': 'How can I stop feeling on edge at night and relax enough to get a good night’s sleep?'} | gold=It might help to ask your mom or dad to do a quick 'house check' with you before bedtim... | loose_rank=1 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: That's a really good question, and it makes sense you're asking it... a lot of kids have a hard time feeling calm at night, especially after bad dreams.  Her...
  - top1: The user, Oliver, asked for help refining a personal email to their Aunt Laura. In the email, Oliver describes waking up at night because of noises and having trouble falling ba...

## Recommended Next Actions
- Storage: inspect cases where target preference/snippet is never represented in any retrieved context.
- Retrieval: prioritize answerable evidence over same-domain neighbor memories.
- Rerank: compare target rank before and after rerank with the same evidence metrics.
- Generation: when answerable context is present but the answer is wrong, review prompt/context formatting rather than storage.