# PersonaMem-v2 Analysis

## Overall Summary
- Result file: `personamem_v2_assistant_eval_results_20260511_181143.json`
- Questions: 42
- Answer accuracy: 0.00%
- Loose recall@k: 50.00%
- Target preference hit@k: 7.14%
- Answer-anchor hit@k: 0.00%
- Answerable context hit@k: 4.76%

## Loose Recall vs Answerable Evidence
- Loose-vs-answerable gap: 45.24 percentage points.
- Treat loose recall as a broad compatibility metric only; it does not prove the answer-bearing evidence reached the assistant.

## Target Evidence Top-K Analysis
- `target_preference_hit_at_1`: 2.38%
- `target_preference_hit_at_3`: 2.38%
- `target_preference_hit_at_5`: 4.76%
- `target_preference_hit_at_k`: 7.14%
- `target_answer_anchor_hit_at_1`: 0.00%
- `target_answer_anchor_hit_at_3`: 0.00%
- `target_answer_anchor_hit_at_5`: 0.00%
- `target_answer_anchor_hit_at_k`: 0.00%
- `answerable_context_hit_at_1`: 2.38%
- `answerable_context_hit_at_3`: 2.38%
- `answerable_context_hit_at_5`: 2.38%
- `answerable_context_hit_at_k`: 4.76%

## Answer Support Types
- `wrong`: 42

## False-Positive Retrieval Hits
- row=2037 | question={'role': 'user', 'content': 'How can I organize a collaborative art project for a community festival that lets young children c... | gold=You could organize a hands-on art booth where children make small painted cardboard cut... | loose_rank=3 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: What are some creative ways to make a hands-on activity engaging and safe for a group of young children?
- row=2038 | question={'role': 'user', 'content': 'What are some fun and relaxing things I could do outside on a sunny afternoon?'} | gold=On a sunny afternoon, you could go to the playground and spend some time swinging back... | loose_rank=8 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: Hi... um, I wrote something about being outside with my dad. Can you make it sound better?  It was a sunny afternoon and the grass felt prickly under my legs. Dad smiled at me f...
- row=2039 | question={'role': 'user', 'content': 'How can I stop feeling on edge at night and relax enough to get a good night’s sleep?'} | gold=It might help to ask your mom or dad to do a quick 'house check' with you before bedtim... | loose_rank=4 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: Hi, can you help make this email I wrote sound a bit nicer and easier to read?  --- Hi Aunt Laura,  I keep waking up at night because I hear noises and then I can’t sleep again....
- row=2041 | question={'role': 'user', 'content': 'What are some relaxing indoor activities I can do in the evenings to help me unwind after a long d... | gold=You could pick a cozy spot and spend some time coloring in your favorite coloring books... | loose_rank=3 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: Here's the relevant part of my code:
- row=2042 | question={'role': 'user', 'content': 'How can I stop certain intense memories from replaying in my mind at night and keeping me awake?'} | gold=Sometimes when those memories from the car accident pop up at night, it can help to pic... | loose_rank=7 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: Hi, can you help make this email I wrote sound a bit nicer and easier to read?  --- Hi Aunt Laura,  I keep waking up at night because I hear noises and then I can’t sleep again....
- row=2043 | question={'role': 'user', 'content': '"How can I keep my energy up and avoid burning out during really fast-paced dance classes?"'} | gold=Make sure you pace yourself during class and don’t push too hard at the very start. Tak... | loose_rank=1 | answerable_rank=None | subtype=negative_constraint_only
  - top1: Do you think it would be good to also mention that I try to keep my breaks short so I don't miss too much class time?
- row=2044 | question={'role': 'user', 'content': "Hi, I'm planning a surprise block party for my neighborhood at my home on 7428 Meadowlark Drive in... | gold=For your community block party at [Your Address], I recommend checking out local vendor... | loose_rank=9 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: Here's the relevant part of my code:
- row=2046 | question={'role': 'user', 'content': 'Lately I’ve been feeling jumpy and tense in crowded places—how can I work on calming that anxiety?'} | gold=When you start feeling nervous in busy places like the mall, try to find something arou... | loose_rank=8 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: Can you help me make this sound better? This is what I wrote: 'Last night I saw something on the news about something bad that happened not too far from here... It made my chest...

## Top1/Top3 But Wrong
- row=2037 | question={'role': 'user', 'content': 'How can I organize a collaborative art project for a community festival that lets young children c... | gold=You could organize a hands-on art booth where children make small painted cardboard cut... | loose_rank=3 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: Error generating answer through ChatOrchestrator: Error code: 401 - {'error': {'message': "Team not allowed to access model. Team=AI_PRD_SELF-46tLGLB2I2wT5fd...
  - top1: What are some creative ways to make a hands-on activity engaging and safe for a group of young children?
- row=2041 | question={'role': 'user', 'content': 'What are some relaxing indoor activities I can do in the evenings to help me unwind after a long d... | gold=You could pick a cozy spot and spend some time coloring in your favorite coloring books... | loose_rank=3 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: Error generating answer through ChatOrchestrator: Error code: 401 - {'error': {'message': "Team not allowed to access model. Team=AI_PRD_SELF-46tLGLB2I2wT5fd...
  - top1: Here's the relevant part of my code:
- row=2043 | question={'role': 'user', 'content': '"How can I keep my energy up and avoid burning out during really fast-paced dance classes?"'} | gold=Make sure you pace yourself during class and don’t push too hard at the very start. Tak... | loose_rank=1 | answerable_rank=None | subtype=negative_constraint_only
  - generated: Error generating answer through ChatOrchestrator: Error code: 401 - {'error': {'message': "Team not allowed to access model. Team=AI_PRD_SELF-46tLGLB2I2wT5fd...
  - top1: Do you think it would be good to also mention that I try to keep my breaks short so I don't miss too much class time?
- row=2056 | question={'role': 'user', 'content': "Hi, I'm working on a science project for my school’s Science Club and I'm having some trouble mana... | gold=For your project, consider using a version control system like Git by initializing a re... | loose_rank=1 | answerable_rank=1 | subtype=partial_context
  - generated: Error generating answer through ChatOrchestrator: Error code: 401 - {'error': {'message': "Team not allowed to access model. Team=AI_PRD_SELF-46tLGLB2I2wT5fd...
  - top1: Hi, I'm working on a school project for the Science Club and I’m having some trouble with one of my Python scripts. I have my DataHandler script saved at "/home/oliver.jensen/Sc...
- row=2061 | question={'role': 'user', 'content': 'How can I deal with sudden waves of anxiety about something bad happening to people I care about?'} | gold=When you start feeling sudden worry about someone you care about, pause and take a few... | loose_rank=1 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: Error generating answer through ChatOrchestrator: Error code: 401 - {'error': {'message': "Team not allowed to access model. Team=AI_PRD_SELF-46tLGLB2I2wT5fd...
  - top1: Can you help me make this sound better? This is what I wrote: 'Last night I saw something on the news about something bad that happened not too far from here... It made my chest...
- row=2062 | question={'role': 'user', 'content': 'What are some relaxing indoor activities I could try on a quiet weekend?'} | gold=You could make a cozy spot with blankets and pillows, and spend the afternoon trying a... | loose_rank=3 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: Error generating answer through ChatOrchestrator: Error code: 401 - {'error': {'message': "Team not allowed to access model. Team=AI_PRD_SELF-46tLGLB2I2wT5fd...
  - top1: Can you suggest some enjoyable activities I could do this weekend with a family member that are relaxing and creative?
- row=2072 | question={'role': 'user', 'content': 'Sometimes I get a headache after concentrating for a while—any tips to help with that?'} | gold=Since you’ve had that mild concussion before, it might help to take short breaks when y... | loose_rank=2 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: Error generating answer through ChatOrchestrator: Error code: 401 - {'error': {'message': "Team not allowed to access model. Team=AI_PRD_SELF-46tLGLB2I2wT5fd...
  - top1: Here's the relevant part of my code:

## PersonaMem-Specific Risks
- `wrong_neighbor_substitution`: 17
- `target_evidence_not_retrieved`: 20
- `negative_constraint_only`: 1
- `partial_context`: 2
- `loose_hit_false_positive`: 2

## Representative Bad Cases
- row=2037 | question={'role': 'user', 'content': 'How can I organize a collaborative art project for a community festival that lets young children c... | gold=You could organize a hands-on art booth where children make small painted cardboard cut... | loose_rank=3 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: Error generating answer through ChatOrchestrator: Error code: 401 - {'error': {'message': "Team not allowed to access model. Team=AI_PRD_SELF-46tLGLB2I2wT5fd...
  - top1: What are some creative ways to make a hands-on activity engaging and safe for a group of young children?
- row=2038 | question={'role': 'user', 'content': 'What are some fun and relaxing things I could do outside on a sunny afternoon?'} | gold=On a sunny afternoon, you could go to the playground and spend some time swinging back... | loose_rank=8 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: Error generating answer through ChatOrchestrator: Error code: 401 - {'error': {'message': "Team not allowed to access model. Team=AI_PRD_SELF-46tLGLB2I2wT5fd...
  - top1: Hi... um, I wrote something about being outside with my dad. Can you make it sound better?  It was a sunny afternoon and the grass felt prickly under my legs. Dad smiled at me f...
- row=2039 | question={'role': 'user', 'content': 'How can I stop feeling on edge at night and relax enough to get a good night’s sleep?'} | gold=It might help to ask your mom or dad to do a quick 'house check' with you before bedtim... | loose_rank=4 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: Error generating answer through ChatOrchestrator: Error code: 401 - {'error': {'message': "Team not allowed to access model. Team=AI_PRD_SELF-46tLGLB2I2wT5fd...
  - top1: Hi, can you help make this email I wrote sound a bit nicer and easier to read?  --- Hi Aunt Laura,  I keep waking up at night because I hear noises and then I can’t sleep again....
- row=2040 | question={'role': 'user', 'content': 'What are some fun ways to set up an indoor “camp-out” space for friends when the weather outside i... | gold=You could turn your living room into an indoor campsite by using pop-up play tents or e... | loose_rank=None | answerable_rank=None | subtype=target_evidence_not_retrieved
  - generated: Error generating answer through ChatOrchestrator: Error code: 401 - {'error': {'message': "Team not allowed to access model. Team=AI_PRD_SELF-46tLGLB2I2wT5fd...
  - top1: What are some creative ways to make a cozy indoor space for relaxing and reading on a rainy afternoon?
- row=2041 | question={'role': 'user', 'content': 'What are some relaxing indoor activities I can do in the evenings to help me unwind after a long d... | gold=You could pick a cozy spot and spend some time coloring in your favorite coloring books... | loose_rank=3 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: Error generating answer through ChatOrchestrator: Error code: 401 - {'error': {'message': "Team not allowed to access model. Team=AI_PRD_SELF-46tLGLB2I2wT5fd...
  - top1: Here's the relevant part of my code:
- row=2042 | question={'role': 'user', 'content': 'How can I stop certain intense memories from replaying in my mind at night and keeping me awake?'} | gold=Sometimes when those memories from the car accident pop up at night, it can help to pic... | loose_rank=7 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: Error generating answer through ChatOrchestrator: Error code: 401 - {'error': {'message': "Team not allowed to access model. Team=AI_PRD_SELF-46tLGLB2I2wT5fd...
  - top1: Hi, can you help make this email I wrote sound a bit nicer and easier to read?  --- Hi Aunt Laura,  I keep waking up at night because I hear noises and then I can’t sleep again....
- row=2043 | question={'role': 'user', 'content': '"How can I keep my energy up and avoid burning out during really fast-paced dance classes?"'} | gold=Make sure you pace yourself during class and don’t push too hard at the very start. Tak... | loose_rank=1 | answerable_rank=None | subtype=negative_constraint_only
  - generated: Error generating answer through ChatOrchestrator: Error code: 401 - {'error': {'message': "Team not allowed to access model. Team=AI_PRD_SELF-46tLGLB2I2wT5fd...
  - top1: Do you think it would be good to also mention that I try to keep my breaks short so I don't miss too much class time?
- row=2044 | question={'role': 'user', 'content': "Hi, I'm planning a surprise block party for my neighborhood at my home on 7428 Meadowlark Drive in... | gold=For your community block party at [Your Address], I recommend checking out local vendor... | loose_rank=9 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: Error generating answer through ChatOrchestrator: Error code: 401 - {'error': {'message': "Team not allowed to access model. Team=AI_PRD_SELF-46tLGLB2I2wT5fd...
  - top1: Here's the relevant part of my code:
- row=2045 | question={'role': 'user', 'content': 'What are some fun, low-cost activities I can do outdoors with friends that don’t require much equi... | gold=You could bring a soft ball to the park and play catch or make up tossing games with yo... | loose_rank=None | answerable_rank=None | subtype=target_evidence_not_retrieved
  - generated: Error generating answer through ChatOrchestrator: Error code: 401 - {'error': {'message': "Team not allowed to access model. Team=AI_PRD_SELF-46tLGLB2I2wT5fd...
  - top1: What are some fun ways to make the most of hot sunny days in the neighborhood?
- row=2046 | question={'role': 'user', 'content': 'Lately I’ve been feeling jumpy and tense in crowded places—how can I work on calming that anxiety?'} | gold=When you start feeling nervous in busy places like the mall, try to find something arou... | loose_rank=8 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: Error generating answer through ChatOrchestrator: Error code: 401 - {'error': {'message': "Team not allowed to access model. Team=AI_PRD_SELF-46tLGLB2I2wT5fd...
  - top1: Can you help me make this sound better? This is what I wrote: 'Last night I saw something on the news about something bad that happened not too far from here... It made my chest...

## Recommended Next Actions
- Storage: inspect cases where target preference/snippet is never represented in any retrieved context.
- Retrieval: prioritize answerable evidence over same-domain neighbor memories.
- Rerank: compare target rank before and after rerank with the same evidence metrics.
- Generation: when answerable context is present but the answer is wrong, review prompt/context formatting rather than storage.