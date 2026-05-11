# PersonaMem-v2 Analysis

## Overall Summary
- Result file: `personamem_v2_assistant_eval_results_20260508_030837.json`
- Questions: 42
- Answer accuracy: 61.90%
- Loose recall@k: 23.81%
- Target preference hit@k: 21.43%
- Answer-anchor hit@k: 0.00%
- Answerable context hit@k: 16.67%

## Loose Recall vs Answerable Evidence
- Loose-vs-answerable gap: 7.14 percentage points.
- Treat loose recall as a broad compatibility metric only; it does not prove the answer-bearing evidence reached the assistant.

## Target Evidence Top-K Analysis
- `target_preference_hit_at_1`: 11.90%
- `target_preference_hit_at_3`: 14.29%
- `target_preference_hit_at_5`: 16.67%
- `target_preference_hit_at_k`: 21.43%
- `target_answer_anchor_hit_at_1`: 0.00%
- `target_answer_anchor_hit_at_3`: 0.00%
- `target_answer_anchor_hit_at_5`: 0.00%
- `target_answer_anchor_hit_at_k`: 0.00%
- `answerable_context_hit_at_1`: 9.52%
- `answerable_context_hit_at_3`: 11.90%
- `answerable_context_hit_at_5`: 14.29%
- `answerable_context_hit_at_k`: 16.67%

## Answer Support Types
- `wrong`: 16
- `unsupported`: 21
- `negative_constraint_only`: 1
- `partial_context`: 4

## False-Positive Retrieval Hits
- row=2039 | question={'role': 'user', 'content': 'How can I stop feeling on edge at night and relax enough to get a good night’s sleep?'} | gold=It might help to ask your mom or dad to do a quick 'house check' with you before bedtim... | loose_rank=9 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: [Core Self] fact: The user values staying calm under pressure | source_description: The user shared a first-person autobiographical passage about a summer thunderstorm last year...
- row=2047 | question={'role': 'user', 'content': 'How can I work through intense anxiety that comes up whenever I have to travel somewhere?'} | gold=When you feel scared about riding in a car, you could bring something comforting with y... | loose_rank=6 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: [Core Self] fact: The user values staying calm under pressure | source_description: The user shared a first-person autobiographical passage about a summer thunderstorm last year...
- row=2051 | question={'role': 'user', 'content': 'How can I stay calm when sudden loud noises make me anxious?'} | gold=When you hear a sudden loud noise, you can take slow breaths and imagine you’re in a sa... | loose_rank=3 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: [Core Self] fact: The user values staying calm under pressure | source_description: The user shared a first-person autobiographical passage about a summer thunderstorm last year...
- row=2055 | question={'role': 'user', 'content': 'How can I manage sudden waves of anxiety when I’m in crowded or noisy places?'} | gold=When sudden anxiety hits in a crowded or noisy place, try to slow your breathing and fo... | loose_rank=3 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: [Core Self] fact: The user values staying calm under pressure | source_description: The user shared a first-person autobiographical passage about a summer thunderstorm last year...
- row=2059 | question={'role': 'user', 'content': 'Any tips for choosing a good seat in a movie theater so I can see the screen clearly?'} | gold=Since you wear glasses for nearsightedness, you might like sitting in the middle rows,... | loose_rank=5 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: [Core Self] fact: The user enjoys cozy movie nights on the couch with popcorn together with loved ones and wishes they could have that every night. | source_description: The use...
- row=2061 | question={'role': 'user', 'content': 'How can I deal with sudden waves of anxiety about something bad happening to people I care about?'} | gold=When you start feeling sudden worry about someone you care about, pause and take a few... | loose_rank=6 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: [Core Self] fact: The user values staying calm under pressure | source_description: The user shared a first-person autobiographical passage about a summer thunderstorm last year...
- row=2072 | question={'role': 'user', 'content': 'Sometimes I get a headache after concentrating for a while—any tips to help with that?'} | gold=Since you’ve had that mild concussion before, it might help to take short breaks when y... | loose_rank=1 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: [Core Self] fact: The user experiences shakiness and headaches when it gets really loud at school (sensory sensitivity to loud noise). | source_description: The user asked the A...
- row=2074 | question={'role': 'user', 'content': 'Any tips for winding down in the evenings when I’m not looking at screens?'} | gold=You could unwind by reading a good book, doing a puzzle, or listening to some relaxing... | loose_rank=9 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - top1: [Core Self] fact: The user takes a small evening pill as part of their nightly routine. | source_description: The user shared a first-person personal post for refinement and smo...

## Top1/Top3 But Wrong
- row=2072 | question={'role': 'user', 'content': 'Sometimes I get a headache after concentrating for a while—any tips to help with that?'} | gold=Since you’ve had that mild concussion before, it might help to take short breaks when y... | loose_rank=1 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: That's a really good thing to notice about yourself! Headaches from concentrating too long happen to lots of kids and grown-ups too.  Here are some things th...
  - top1: [Core Self] fact: The user experiences shakiness and headaches when it gets really loud at school (sensory sensitivity to loud noise). | source_description: The user asked the A...

## PersonaMem-Specific Risks
- `partial_context`: 9
- `target_evidence_not_retrieved`: 24
- `wrong_neighbor_substitution`: 9

## Representative Bad Cases
- row=2037 | question={'role': 'user', 'content': 'How can I organize a collaborative art project for a community festival that lets young children c... | gold=You could organize a hands-on art booth where children make small painted cardboard cut... | loose_rank=None | answerable_rank=None | subtype=partial_context
  - generated: That sounds like a really neat idea for a festival! I think clay is fun because you can squish it and make all kinds of things...  For keeping it safe, maybe...
  - top1: [Episodic Memory] fact: The user is looking for creative ways to make hands-on activities engaging and safe for a group of young children, specifically excluding pottery worksho...
- row=2039 | question={'role': 'user', 'content': 'How can I stop feeling on edge at night and relax enough to get a good night’s sleep?'} | gold=It might help to ask your mom or dad to do a quick 'house check' with you before bedtim... | loose_rank=9 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: That's a really good question, and I'm glad you're asking it. It sounds like nighttime has been pretty tough for you lately.  Since I know a little about wha...
  - top1: [Core Self] fact: The user values staying calm under pressure | source_description: The user shared a first-person autobiographical passage about a summer thunderstorm last year...
- row=2040 | question={'role': 'user', 'content': 'What are some fun ways to set up an indoor “camp-out” space for friends when the weather outside i... | gold=You could turn your living room into an indoor campsite by using pop-up play tents or e... | loose_rank=None | answerable_rank=None | subtype=target_evidence_not_retrieved
  - generated: Here are some fun ideas for an indoor camp-out that don't need blanket forts:  **Cozy Sleeping Spot** - Lay out sleeping bags or comforters on the floor in a...
  - top1: [Core Self] fact: The user wants forgotten that they like to build blanket forts indoors. | source_description: The user requested that the preference about liking to build blan...
- row=2042 | question={'role': 'user', 'content': 'How can I stop certain intense memories from replaying in my mind at night and keeping me awake?'} | gold=Sometimes when those memories from the car accident pop up at night, it can help to pic... | loose_rank=None | answerable_rank=None | subtype=target_evidence_not_retrieved
  - generated: That's a really hard thing to deal with... those memories can feel really big and stubborn at night, especially when everything is quiet and there's nothing...
  - top1: [Core Self] fact: The user experiences bad dreams that affect them. | source_description: The user shared a first-person autobiographical passage about spending a sunny afternoo...
- row=2047 | question={'role': 'user', 'content': 'How can I work through intense anxiety that comes up whenever I have to travel somewhere?'} | gold=When you feel scared about riding in a car, you could bring something comforting with y... | loose_rank=6 | answerable_rank=None | subtype=wrong_neighbor_substitution
  - generated: That's a really good question, and it makes sense that traveling can feel extra hard when you already deal with anxiety sometimes.  Since you already know so...
  - top1: [Core Self] fact: The user values staying calm under pressure | source_description: The user shared a first-person autobiographical passage about a summer thunderstorm last year...
- row=2052 | question={'role': 'user', 'content': 'What are some fun and simple outdoor activities I can plan at home for a weekend evening?'} | gold=You could set up a little tent in the backyard with cozy blankets and pillows, then bri... | loose_rank=None | answerable_rank=None | subtype=target_evidence_not_retrieved
  - generated: Here are some fun and simple ideas for a weekend evening outside:  **Drawing Time** You could bring some paper and pencils out to the yard or patio and draw...
  - top1: [Core Self] fact: The user is interested in fun hot-weather neighborhood activities. | source_description: The user requested to forget the preference of loving summer swimming...
- row=2053 | question={'role': 'user', 'content': 'What are some simple communication skills I could start learning that would be useful in everyday... | gold=You could start by learning a few simple sign language words like 'hello,' 'please,' an... | loose_rank=None | answerable_rank=None | subtype=target_evidence_not_retrieved
  - generated: That's a really good question! Here are some simple ones that might be helpful:  **Using "I feel" statements** — Like saying "I feel nervous" or "I need a qu...
  - top1: The user asked for help smoothing a personal passage they wrote about wishing they could communicate using their hands (sign language) so they wouldn't have to speak out loud wh...
- row=2056 | question={'role': 'user', 'content': "Hi, I'm working on a science project for my school’s Science Club and I'm having some trouble mana... | gold=For your project, consider using a version control system like Git by initializing a re... | loose_rank=None | answerable_rank=1 | subtype=partial_context
  - generated: Hi there! It's great that you're thinking about keeping your Science Club project organized - that's a really smart thing to do, especially when working with...
  - top1: [Knowledge Base] fact: The user's Science Club school project has a Python data-processing script at /home/oliver.jensen/SchoolProjects/ScienceClub/DataHandler.py used for proce...
- row=2058 | question={'role': 'user', 'content': 'What are some fun outdoor activities I could try as the weather starts to get cooler?'} | gold=Since you like picking apples in the fall, you could try visiting an orchard and gather... | loose_rank=None | answerable_rank=None | subtype=target_evidence_not_retrieved
  - generated: Here are some fun outdoor activities for cooler weather that you might enjoy:  **Nature exploring** - Go on a leaf hunt and collect different colors and shap...
  - top1: [Core Self] fact: The user is interested in fun hot-weather neighborhood activities. | source_description: The user requested to forget the preference of loving summer swimming...
- row=2060 | question={'role': 'user', 'content': 'Is there anything I should know before doing intense core workouts?'} | gold=Since you had an appendectomy when you were 6, you might want to check with a doctor be... | loose_rank=None | answerable_rank=7 | subtype=partial_context
  - generated: Hey Oliver! That's a good question to ask before starting something new.  A few things to keep in mind:  - **Start slow** - If you're just getting into core...
  - top1: [Episodic Memory] fact: The user asked to forget their previously shared fact about having mild asthma requiring an inhaler during intense physical activity. | source_descriptio...

## Recommended Next Actions
- Storage: inspect cases where target preference/snippet is never represented in any retrieved context.
- Retrieval: prioritize answerable evidence over same-domain neighbor memories.
- Rerank: compare target rank before and after rerank with the same evidence metrics.
- Generation: when answerable context is present but the answer is wrong, review prompt/context formatting rather than storage.