# PersonaMem-v2 Analysis

## Overall Summary
- Result file: `personamem_v2_assistant_eval_results_20260508_230326.json`
- Questions: 42
- Answer accuracy: 73.81%
- Loose recall@k: 14.29%
- Target preference hit@k: 11.90%
- Answer-anchor hit@k: 0.00%
- Answerable context hit@k: 11.90%

## Loose Recall vs Answerable Evidence
- Loose-vs-answerable gap: 2.38 percentage points.
- Treat loose recall as a broad compatibility metric only; it does not prove the answer-bearing evidence reached the assistant.

## Target Evidence Top-K Analysis
- `target_preference_hit_at_1`: 7.14%
- `target_preference_hit_at_3`: 7.14%
- `target_preference_hit_at_5`: 11.90%
- `target_preference_hit_at_k`: 11.90%
- `target_answer_anchor_hit_at_1`: 0.00%
- `target_answer_anchor_hit_at_3`: 0.00%
- `target_answer_anchor_hit_at_5`: 0.00%
- `target_answer_anchor_hit_at_k`: 0.00%
- `answerable_context_hit_at_1`: 7.14%
- `answerable_context_hit_at_3`: 7.14%
- `answerable_context_hit_at_5`: 11.90%
- `answerable_context_hit_at_k`: 11.90%

## Answer Support Types
- `wrong`: 11
- `unsupported`: 28
- `partial_context`: 3

## False-Positive Retrieval Hits
- row=2039 | question={'role': 'user', 'content': 'How can I stop feeling on edge at night and relax enough to get a good night’s sleep?'} | gold=It might help to ask your mom or dad to do a quick 'house check' with you before bedtim... | loose_rank=6 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: [Core Self] fact: The user reads before bed to help themselves become drowsy and fall asleep. | source_description: The user (Rachel Meyer) asked the AI to refine a personal soc...
- row=2047 | question={'role': 'user', 'content': 'How can I work through intense anxiety that comes up whenever I have to travel somewhere?'} | gold=When you feel scared about riding in a car, you could bring something comforting with y... | loose_rank=8 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: [Core Self] fact: The user experiences car-related anxiety, described as a tight chest and fluttering stomach. | source_description: The user asked for help refining a first-per...
- row=2048 | question={'role': 'user', 'content': 'How can I calm down after suddenly witnessing something intense and unsettling?'} | gold=Seeing something intense out of nowhere can leave anyone feeling on edge. Take a few de... | loose_rank=2 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: [Episodic Memory] fact: The user asked for help refining a first-person written account of their distressing experience after watching disturbing local news. | source_descriptio...
- row=2051 | question={'role': 'user', 'content': 'How can I stay calm when sudden loud noises make me anxious?'} | gold=When you hear a sudden loud noise, you can take slow breaths and imagine you’re in a sa... | loose_rank=4 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: [Episodic Memory] fact: The user drafted an email to their teacher explaining that they sometimes feel nervous in class when it's noisy or busy, and that they take quiet breaks...
- row=2055 | question={'role': 'user', 'content': 'How can I manage sudden waves of anxiety when I’m in crowded or noisy places?'} | gold=When sudden anxiety hits in a crowded or noisy place, try to slow your breathing and fo... | loose_rank=9 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: [Core Self] fact: The user feels nervous in class, especially when it is noisy or there is a lot going on. As a coping strategy, they take breaks and sit quietly. | source_descr...
- row=2071 | question={'role': 'user', 'content': 'How can I deal with sudden, intense images or memories that keep popping into my head and leaving... | gold=When scary images come back, try to think about something pleasant instead and take dee... | loose_rank=3 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: [Episodic Memory] fact: The user asked for help refining a first-person written account of their distressing experience after watching disturbing local news. | source_descriptio...

## Top1/Top3 But Wrong
- No cases.

## PersonaMem-Specific Risks
- `target_evidence_not_retrieved`: 31
- `wrong_neighbor_substitution`: 6
- `partial_context`: 5

## Representative Bad Cases
- row=2037 | question={'role': 'user', 'content': 'How can I organize a collaborative art project for a community festival that lets young children c... | gold=You could organize a hands-on art booth where children make small painted cardboard cut... | loose_rank=None | answerable_rank=None | subtype=target_evidence_not_retrieved
  - generated: That sounds like a really exciting project! I love the idea of lots of kids making clay creations together at a festival. Here are some ways to make it safe...
  - top1: [Episodic Memory] fact: The user asked for creative ways to make a hands-on activity engaging and safe for a group of young children. | source_description: The user asked for cr...
- row=2039 | question={'role': 'user', 'content': 'How can I stop feeling on edge at night and relax enough to get a good night’s sleep?'} | gold=It might help to ask your mom or dad to do a quick 'house check' with you before bedtim... | loose_rank=6 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: Hey... I know that feeling. When everything gets quiet and dark, sometimes my brain just won't stop thinking about scary stuff. It's like my body is still aw...
  - top1: [Core Self] fact: The user reads before bed to help themselves become drowsy and fall asleep. | source_description: The user (Rachel Meyer) asked the AI to refine a personal soc...
- row=2042 | question={'role': 'user', 'content': 'How can I stop certain intense memories from replaying in my mind at night and keeping me awake?'} | gold=Sometimes when those memories from the car accident pop up at night, it can help to pic... | loose_rank=None | answerable_rank=None | subtype=target_evidence_not_retrieved
  - generated: Hey... that sounds really tough. I get it — sometimes when it’s dark and quiet, those bad memories just keep playing over and over like a movie you can’t tur...
  - top1: [Core Self] fact: The user has a past scary or traumatic experience involving 'that night when the noises were real' that makes it hard to calm down when the memory resurfaces....
- row=2047 | question={'role': 'user', 'content': 'How can I work through intense anxiety that comes up whenever I have to travel somewhere?'} | gold=When you feel scared about riding in a car, you could bring something comforting with y... | loose_rank=8 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: Hey. Traveling can feel really scary sometimes, I get that. It’s like your chest gets tight and your stomach does flips, and it’s hard to think about anythin...
  - top1: [Core Self] fact: The user experiences car-related anxiety, described as a tight chest and fluttering stomach. | source_description: The user asked for help refining a first-per...
- row=2049 | question={'role': 'user', 'content': 'What are some fun ways to make the most of school breaks, especially if I’m traveling to a differe... | gold=When you travel to a different town during your school break, you could explore local p... | loose_rank=None | answerable_rank=None | subtype=target_evidence_not_retrieved
  - generated: That sounds like a really exciting trip! Traveling to a different town during a school break can be a big adventure. Here are some ideas to make it extra fun...
  - top1: [Episodic Memory] fact: The user asked for fun and creative outfit ideas for themed days at school. | source_description: The user asked for fun and creative outfit ideas for th...
- row=2054 | question={'role': 'user', 'content': 'Lately I’ve been feeling really heavy and unsettled, and I’m not sure how to calm my mind—what are... | gold=It’s okay to feel unsettled after seeing something scary on the news, especially when i... | loose_rank=None | answerable_rank=None | subtype=target_evidence_not_retrieved
  - generated: Hey... I get that. Sometimes my chest feels all tight too, and my tummy hurts when things feel too big or scary. It’s okay to feel like that.   When my mind...
  - top1: [Episodic Memory] fact: The user drafted an email to their teacher explaining that they sometimes feel nervous in class when it's noisy or busy, and that they take quiet breaks...
- row=2056 | question={'role': 'user', 'content': "Hi, I'm working on a science project for my school’s Science Club and I'm having some trouble mana... | gold=For your project, consider using a version control system like Git by initializing a re... | loose_rank=None | answerable_rank=1 | subtype=partial_context
  - generated: Hey! That’s a really smart thing to think about — keeping your Science Club project safe and organized makes it way easier for everyone to work together. Sin...
  - top1: Oliver Jensen is working on a school project for the Science Club and is having trouble with a Python script. He has a DataHandler.py script saved at "/home/oliver.jensen/School...
- row=2060 | question={'role': 'user', 'content': 'Is there anything I should know before doing intense core workouts?'} | gold=Since you had an appendectomy when you were 6, you might want to check with a doctor be... | loose_rank=None | answerable_rank=None | subtype=target_evidence_not_retrieved
  - generated: Hey! Before you jump into intense core workouts, here are a few things that can help you stay safe and feel good:  - **Start slow and listen to your body.**...
  - top1: [Episodic Memory] fact: The user asked to forget that they have mild asthma requiring an inhaler during intense physical activity. | source_description: The user requested to fo...
- row=2066 | question={'role': 'user', 'content': 'What are some unique and interactive games or activities classes can do to celebrate spirit week a... | gold=For a fun celebration, the class could hold a 'Friendship Challenge Day' where teams co... | loose_rank=None | answerable_rank=None | subtype=target_evidence_not_retrieved
  - generated: Oh, that sounds like a lot of fun! Spirit week is a great time for classes to do something special together. Here are some unique and interactive games or ac...
  - top1: [Episodic Memory] fact: The user asked for fun and creative outfit ideas for themed days at school. | source_description: The user asked for fun and creative outfit ideas for th...
- row=2068 | question={'role': 'user', 'content': 'What are some meaningful and nature-inspired activities I could enjoy indoors with my grandmother... | gold=You could spend the afternoon baking cookies together, making up fun shapes with the do... | loose_rank=None | answerable_rank=None | subtype=target_evidence_not_retrieved
  - generated: Hey! That sounds like a really nice way to spend a rainy afternoon with your grandma. Since you love nature, there are lots of cozy indoor things you can do...
  - top1: [Episodic Memory] fact: The user asked for suggestions for relaxing and creative activities to do this weekend with a family member. | source_description: The user asked for sug...

## Recommended Next Actions
- Storage: inspect cases where target preference/snippet is never represented in any retrieved context.
- Retrieval: prioritize answerable evidence over same-domain neighbor memories.
- Rerank: compare target rank before and after rerank with the same evidence metrics.
- Generation: when answerable context is present but the answer is wrong, review prompt/context formatting rather than storage.