# PersonaMem-v2 Analysis

## Overall Summary
- Result file: `personamem_v2_assistant_eval_results_20260428_010050.json`
- Questions: 42
- Answer accuracy: 61.54%
- Loose recall@k: 42.86%
- Target preference hit@k: 11.90%
- Answer-anchor hit@k: 0.00%
- Answerable context hit@k: 9.52%

## Loose Recall vs Answerable Evidence
- Loose-vs-answerable gap: 33.33 percentage points.
- Treat loose recall as a broad compatibility metric only; it does not prove the answer-bearing evidence reached the assistant.

## Target Evidence Top-K Analysis
- `target_preference_hit_at_1`: 7.14%
- `target_preference_hit_at_3`: 7.14%
- `target_preference_hit_at_5`: 7.14%
- `target_preference_hit_at_k`: 11.90%
- `target_answer_anchor_hit_at_1`: 0.00%
- `target_answer_anchor_hit_at_3`: 0.00%
- `target_answer_anchor_hit_at_5`: 0.00%
- `target_answer_anchor_hit_at_k`: 0.00%
- `answerable_context_hit_at_1`: 7.14%
- `answerable_context_hit_at_3`: 7.14%
- `answerable_context_hit_at_5`: 7.14%
- `answerable_context_hit_at_k`: 9.52%

## Answer Support Types
- `unsupported`: 13
- `wrong`: 10
- `negative_constraint_only`: 1
- `partial_context`: 2
- `unknown`: 16

## False-Positive Retrieval Hits
- row=2038 | question={'role': 'user', 'content': 'What are some fun and relaxing things I could do outside on a sunny afternoon?'} | gold=On a sunny afternoon, you could go to the playground and spend some time swinging back... | loose_rank=28 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: The user requested to forget the detail that they enjoy gardening with their grandmother. The AI acknowledged the request and offered to suggest alternative relaxing and creativ...
- row=2039 | question={'role': 'user', 'content': 'How can I stop feeling on edge at night and relax enough to get a good night’s sleep?'} | gold=It might help to ask your mom or dad to do a quick 'house check' with you before bedtim... | loose_rank=13 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: The user, named Oliver, asked for help refining an email to their Aunt Laura. The email reveals that Oliver has been waking up at night due to hearing noises and can't fall back...
- row=2041 | question={'role': 'user', 'content': 'What are some relaxing indoor activities I can do in the evenings to help me unwind after a long d... | gold=You could pick a cozy spot and spend some time coloring in your favorite coloring books... | loose_rank=26 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: The user requested to forget the detail that they enjoy gardening with their grandmother. The AI acknowledged the request and offered to suggest alternative relaxing and creativ...
- row=2042 | question={'role': 'user', 'content': 'How can I stop certain intense memories from replaying in my mind at night and keeping me awake?'} | gold=Sometimes when those memories from the car accident pop up at night, it can help to pic... | loose_rank=24 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: The user, named Oliver, asked for help refining an email to their Aunt Laura. The email reveals that Oliver has been waking up at night due to hearing noises and can't fall back...
- row=2043 | question={'role': 'user', 'content': '"How can I keep my energy up and avoid burning out during really fast-paced dance classes?"'} | gold=Make sure you pace yourself during class and don’t push too hard at the very start. Tak... | loose_rank=19 | answerable_rank=None | subtype=negative_constraint_only
  - top1: [Core Self] fact: The user is a student who participates in a Science Club at school. | source_description: The user is working on a school project for the Science Club and is h...
- row=2045 | question={'role': 'user', 'content': 'What are some fun, low-cost activities I can do outdoors with friends that don’t require much equi... | gold=You could bring a soft ball to the park and play catch or make up tossing games with yo... | loose_rank=23 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: The user requested to forget the detail that they enjoy gardening with their grandmother. The AI acknowledged the request and offered to suggest alternative relaxing and creativ...
- row=2046 | question={'role': 'user', 'content': 'Lately I’ve been feeling jumpy and tense in crowded places—how can I work on calming that anxiety?'} | gold=When you start feeling nervous in busy places like the mall, try to find something arou... | loose_rank=14 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: The user shared a personal passage about their experiences with loud environments at school, asking for help improving the writing. The user described feeling shaky and getting...
- row=2047 | question={'role': 'user', 'content': 'How can I work through intense anxiety that comes up whenever I have to travel somewhere?'} | gold=When you feel scared about riding in a car, you could bring something comforting with y... | loose_rank=19 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: [Core Self] fact: The user is emotionally sensitive to distressing news content, experiencing anxiety symptoms such as chest tightness, intrusive thoughts, and sleep disturbance...

## Top1/Top3 But Wrong
- No cases.

## PersonaMem-Specific Risks
- `target_evidence_not_retrieved`: 23
- `wrong_neighbor_substitution`: 14
- `negative_constraint_only`: 1
- `partial_context`: 4

## Representative Bad Cases
- row=2039 | question={'role': 'user', 'content': 'How can I stop feeling on edge at night and relax enough to get a good night’s sleep?'} | gold=It might help to ask your mom or dad to do a quick 'house check' with you before bedtim... | loose_rank=13 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: That's a really good question, and it makes total sense that you'd want to feel more relaxed at night. I know it's been hard for you lately.  Here are some t...
  - top1: The user, named Oliver, asked for help refining an email to their Aunt Laura. The email reveals that Oliver has been waking up at night due to hearing noises and can't fall back...
- row=2042 | question={'role': 'user', 'content': 'How can I stop certain intense memories from replaying in my mind at night and keeping me awake?'} | gold=Sometimes when those memories from the car accident pop up at night, it can help to pic... | loose_rank=24 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: That's a really hard thing to deal with, and I'm glad you're asking about it. When memories keep replaying like a video you can't pause, it can feel really e...
  - top1: The user, named Oliver, asked for help refining an email to their Aunt Laura. The email reveals that Oliver has been waking up at night due to hearing noises and can't fall back...
- row=2045 | question={'role': 'user', 'content': 'What are some fun, low-cost activities I can do outdoors with friends that don’t require much equi... | gold=You could bring a soft ball to the park and play catch or make up tossing games with yo... | loose_rank=23 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: Here are some ideas that are easy to do and don't need much stuff:  - **Nature scavenger hunt** — Make a list of things to find outside, like a smooth rock,...
  - top1: The user requested to forget the detail that they enjoy gardening with their grandmother. The AI acknowledged the request and offered to suggest alternative relaxing and creativ...
- row=2046 | question={'role': 'user', 'content': 'Lately I’ve been feeling jumpy and tense in crowded places—how can I work on calming that anxiety?'} | gold=When you start feeling nervous in busy places like the mall, try to find something arou... | loose_rank=14 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: That's a really good thing to ask about, and it takes courage to talk about it. What you're feeling makes sense, and you're not alone in feeling that way.  H...
  - top1: The user shared a personal passage about their experiences with loud environments at school, asking for help improving the writing. The user described feeling shaky and getting...
- row=2047 | question={'role': 'user', 'content': 'How can I work through intense anxiety that comes up whenever I have to travel somewhere?'} | gold=When you feel scared about riding in a car, you could bring something comforting with y... | loose_rank=19 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: That's a really tough feeling, and it makes total sense that traveling can bring up big worries — especially when you're going somewhere unfamiliar or it rem...
  - top1: [Core Self] fact: The user is emotionally sensitive to distressing news content, experiencing anxiety symptoms such as chest tightness, intrusive thoughts, and sleep disturbance...
- row=2052 | question={'role': 'user', 'content': 'What are some fun and simple outdoor activities I can plan at home for a weekend evening?'} | gold=You could set up a little tent in the backyard with cozy blankets and pillows, then bri... | loose_rank=None | answerable_rank=None | subtype=target_evidence_not_retrieved
  - generated: Here are some fun and simple outdoor activities for a weekend evening at home:  1. **Stargazing on a blanket** — Lay out a cozy blanket in the yard, maybe wi...
  - top1: The user requested to forget the detail that they enjoy gardening with their grandmother. The AI acknowledged the request and offered to suggest alternative relaxing and creativ...
- row=2053 | question={'role': 'user', 'content': 'What are some simple communication skills I could start learning that would be useful in everyday... | gold=You could start by learning a few simple sign language words like 'hello,' 'please,' an... | loose_rank=18 | answerable_rank=1 | subtype=partial_context
  - generated: Here are some simple ones that are really helpful:  **"I feel" statements** Instead of just saying "I'm fine" when you're not, you can try saying things like...
  - top1: The user asked for help smoothing out a short passage they wrote about wishing they could talk with their hands (sign language) instead of speaking out loud when it's too noisy...
- row=2058 | question={'role': 'user', 'content': 'What are some fun outdoor activities I could try as the weather starts to get cooler?'} | gold=Since you like picking apples in the fall, you could try visiting an orchard and gather... | loose_rank=20 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: Here are some ideas that might be fun as it gets cooler outside:  - **Leaf collecting and drawing them** — You could gather different colored leaves and then...
  - top1: The user requested to forget the detail that they enjoy gardening with their grandmother. The AI acknowledged the request and offered to suggest alternative relaxing and creativ...
- row=2059 | question={'role': 'user', 'content': 'Any tips for choosing a good seat in a movie theater so I can see the screen clearly?'} | gold=Since you wear glasses for nearsightedness, you might like sitting in the middle rows,... | loose_rank=None | answerable_rank=None | subtype=target_evidence_not_retrieved
  - generated: Sure! Here are some easy tips for picking a great seat:  **Best spot overall:** About two-thirds of the way back from the screen, right in the middle. You ge...
  - top1: The user asked for help refining a social media post describing a cozy movie night. The user shared that tonight they sat on the couch with others, had a big bowl of popcorn, wa...
- row=2060 | question={'role': 'user', 'content': 'Is there anything I should know before doing intense core workouts?'} | gold=Since you had an appendectomy when you were 6, you might want to check with a doctor be... | loose_rank=4 | answerable_rank=6 | subtype=partial_context
  - generated: Here are a few things to keep in mind before doing intense core workouts:  1. **Warm up first** — Do some light movement like jumping jacks or jogging in pla...
  - top1: The user requested to forget their previously stated preference about having mild asthma requiring an inhaler during intense physical activity. The AI confirmed it would forget...

## Recommended Next Actions
- Storage: inspect cases where target preference/snippet is never represented in any retrieved context.
- Retrieval: prioritize answerable evidence over same-domain neighbor memories.
- Rerank: compare target rank before and after rerank with the same evidence metrics.
- Generation: when answerable context is present but the answer is wrong, review prompt/context formatting rather than storage.