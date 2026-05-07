# Category + TurnMemory + Resource Evaluation

- generated_at_utc: `2026-04-24T14:39:32.925688+00:00`
- character: `caroline`
- user_id: `dbafc7e4-5d73-4acd-b3aa-7d7fd7d79c92`
- qa_path: `tests\fixtures\converted_data\unsupported_success_recheck\sample_0_qa.json`
- top_k: `15`

## Summary

- current: correct=`11/23`, gain=`0`, regression=`0`, nonempty_gold_gain=`0`, empty_gold_regression=`0`
- category_only: correct=`12/23`, gain=`3`, regression=`2`, nonempty_gold_gain=`1`, empty_gold_regression=`2`
- turnmemory_only: correct=`14/23`, gain=`4`, regression=`1`, nonempty_gold_gain=`2`, empty_gold_regression=`0`
- category_turn_resource_hybrid: correct=`12/23`, gain=`2`, regression=`1`, nonempty_gold_gain=`1`, empty_gold_regression=`0`
- category_turn_resource_selective: correct=`13/23`, gain=`5`, regression=`3`, nonempty_gold_gain=`2`, empty_gold_regression=`2`
- cache_hits: `1068`
- cache_misses: `0`
- cache_hit_rate: `1.0`

## Questions

### What fields would Caroline be likely to pursue in her educaton?

- standard_answer: `Psychology, counseling certification`
- question_kind: `profile`
- classified_categories: `['Core Self', 'Timeline']`
- retrieval_seconds: `34.759`
- top_category: User is exploring counseling or mental health work as a career direction, acknowledging it is tough but rewarding
- top_turnmemory: Gonna continue my edu and check out career options, which is pretty exciting!
- top_expanded_resource: [ResourceSummary] The user, who is transgender, is considering a career path focused on counseling and supporting trans people with self-acceptance and mental health. They attended an LGBTQ+ counseling workshop on Friday, January 23, 2026, where they learned about various therapeutic methods for wor
- selective_decision: `{'selected': 'category', 'reason': 'profile_or_default_category_priority', 'question_kind': 'profile', 'top_category_score': 0.0844, 'top_turn_score': 0.0674, 'top_turn_similarity': 0.4504}`
- current: correct=`True`, anchor_rank=`None`, answer_seconds=`25.014`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.0844, 0.0828, 0.0692, 0.0508, 0.0479]`
  - answer: Based on what I know about Caroline, she'd most likely pursue fields related to **psychology and mental health counseling**. She's specifically drawn to counseling as a career path, with a strong interest in supporting trans people with self-acceptance and mental health. That kind of focus could lea
- category_only: correct=`True`, anchor_rank=`None`, answer_seconds=`22.011`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.0844, 0.0828, 0.0692, 0.0508, 0.0479]`
  - answer: Based on what I know, Caroline would most likely pursue fields related to **psychological counseling** or **mental health work**. She's specifically drawn to helping trans people with self-acceptance and mental health support, which ties into her passion for LGBTQ rights.

Given her broader interest
- turnmemory_only: correct=`True`, anchor_rank=`None`, answer_seconds=`35.932`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.0674, 0.0508, 0.0398, 0.0368, 0.0346]`
  - answer: Based on what Caroline has shared, she'd most likely pursue fields related to **counseling and mental health**, particularly with a focus on **LGBTQ+ affirming therapy**. She's expressed a strong interest in working with trans people specifically — helping them with self-acceptance and mental health
- category_turn_resource_hybrid: correct=`True`, anchor_rank=`None`, answer_seconds=`20.386`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.0844, 0.0828, 0.0692, 0.0508, 0.0479]`
  - answer: Based on what Caroline has shared, she'd most likely pursue fields related to **counseling and mental health**. She's specifically interested in supporting people with issues similar to her own, and she was deeply inspired by an LGBTQ+ counseling workshop she attended — especially the dedication of 
- category_turn_resource_selective: correct=`True`, anchor_rank=`None`, answer_seconds=`25.54`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.0844, 0.0828, 0.0692, 0.0508, 0.0479]`
  - answer: Based on what I know, Caroline would most likely pursue fields related to **psychology, counseling, or mental health**. She's specifically drawn to the idea of becoming a counselor to help trans people with self-acceptance and mental health support, which suggests she'd be interested in programs tha

### When did Caroline join a new activist group?

- standard_answer: `The Tuesday before 8 February 2026`
- question_kind: `exact_fact`
- classified_categories: `['Timeline', 'Social Graph']`
- retrieval_seconds: `31.372`
- top_category: The user joined a new LGBTQ activist group on Tuesday, February 3, 2026.
- top_turnmemory: Hey Mel! A lot's happened since we last chatted - I just joined a new LGBTQ activist group last Tues. I'm meeting so many cool people who are as passionate as I am about rights and community support. I'm giving my voice and making a real difference, plus it's fulfilling in so many ways. It's just gr
- top_expanded_resource: [ResourceSummary] The user is excited about an upcoming LGBTQ art show happening next month (March 2026), which will feature their own paintings. They expressed enthusiasm about the event. The AI responded with encouragement and asked if the user had any previews of the artwork.
- selective_decision: `{'selected': 'turnmemory', 'reason': 'exact_fact_turnmemory_competitive', 'question_kind': 'exact_fact', 'top_category_score': 0.0975, 'top_turn_score': 0.0561, 'top_turn_similarity': 0.3721}`
- current: correct=`True`, anchor_rank=`None`, answer_seconds=`22.026`
  - strategies: `['category_vector', 'resource_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.0975, 0.0577, 0.0547, 0.0506, 0.0474]`
  - answer: Caroline joined a new LGBTQ activist group called "Connected LGBTQ Activists" on Tuesday, February 3, 2026.
- category_only: correct=`True`, anchor_rank=`None`, answer_seconds=`25.49`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.0975, 0.0547, 0.0506, 0.0474, 0.0377]`
  - answer: Caroline joined a new LGBTQ activist group on Tuesday, February 3, 2026.
- turnmemory_only: correct=`False`, anchor_rank=`None`, answer_seconds=`33.99`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.0561, 0.0389, 0.029, 0.0284, 0.0283]`
  - answer: Based on what you shared before, you mentioned joining the new LGBTQ activist group "last Tuesday" — but there wasn't a specific date attached to it, so I can't pin down the exact calendar date. Do you remember which Tuesday it was?
- category_turn_resource_hybrid: correct=`True`, anchor_rank=`None`, answer_seconds=`9.129`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.0975, 0.0547, 0.0506, 0.0474, 0.0377]`
  - answer: Caroline joined the new LGBTQ activist group on Tuesday, February 3, 2026.
- category_turn_resource_selective: correct=`False`, anchor_rank=`None`, answer_seconds=`12.073`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.0561, 0.0389, 0.029, 0.0284, 0.0283]`
  - answer: Caroline joined the new LGBTQ activist group last Tuesday!

### What is Caroline's identity?

- standard_answer: `Transgender woman`
- question_kind: `profile`
- classified_categories: `['Core Self', 'Knowledge Base']`
- retrieval_seconds: `50.536`
- top_category: The user's name is Caroline.
- top_turnmemory: Hey Mel! A lot's happened since we last chatted - I just joined a new LGBTQ activist group last Tues. I'm meeting so many cool people who are as passionate as I am about rights and community support. I'm giving my voice and making a real difference, plus it's fulfilling in so many ways. It's just gr
- top_expanded_resource: [ResourceSummary] The user is casually chatting about creative hobbies. They mention they are currently learning to play the piano and ask someone named Melanie about her interest in pottery. The AI responds enthusiastically about pottery, praising its creativity and calming nature.
- selective_decision: `{'selected': 'category', 'reason': 'profile_or_default_category_priority', 'question_kind': 'profile', 'top_category_score': 0.4258, 'top_turn_score': 0.0481, 'top_turn_similarity': 0.2206}`
- current: correct=`True`, anchor_rank=`None`, answer_seconds=`17.573`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.4258, 0.1794, 0.158, 0.1341, 0.1074]`
  - answer: Based on what I know about you, Caroline, here's what I can share about your identity:

You're a transgender woman who's going through a life transition and values friendship and compassion deeply. You're either a mom or planning to become one, and you feel that being a mom is awesome — you're even 
- category_only: correct=`True`, anchor_rank=`None`, answer_seconds=`30.031`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.4258, 0.1794, 0.158, 0.1341, 0.1074]`
  - answer: Based on what I know, Caroline is **you** — and here's what makes up your identity:

- **Transgender** — you're navigating your own journey of self-acceptance and growth
- **A mom or planning to become one** — and you feel being a mom is awesome
- **Someone going through a life transition** — which 
- turnmemory_only: correct=`True`, anchor_rank=`None`, answer_seconds=`31.41`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.0481, 0.0397, 0.0362, 0.0319, 0.0301]`
  - answer: Based on what Caroline has shared, she's transgender — she mentioned mentoring a transgender teen "just like me." She's also from Sweden, passionate about LGBTQ rights, and has been actively involved in an activist group called "Connected LGBTQ Activists."
- category_turn_resource_hybrid: correct=`False`, anchor_rank=`None`, answer_seconds=`6.639`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.4258, 0.1794, 0.158, 0.1341, 0.1074]`
  - answer: Based on what I know, Caroline's identity is listed as "other."
- category_turn_resource_selective: correct=`True`, anchor_rank=`None`, answer_seconds=`14.082`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.4258, 0.1794, 0.158, 0.1341, 0.1074]`
  - answer: Based on what I know, Caroline is transgender. Is there something more specific you were wondering about?

### What would Caroline's political leaning likely be?

- standard_answer: `Liberal`
- question_kind: `profile`
- classified_categories: `['Core Self', 'Knowledge Base']`
- retrieval_seconds: `33.356`
- top_category: The user's name is Caroline.
- top_turnmemory: Hey Mel! A lot's happened since we last chatted - I just joined a new LGBTQ activist group last Tues. I'm meeting so many cool people who are as passionate as I am about rights and community support. I'm giving my voice and making a real difference, plus it's fulfilling in so many ways. It's just gr
- top_expanded_resource: [ResourceSummary] The user shared that they selected their adoption agency because of its LGBTQ+ inclusivity and support, indicating that they are an LGBTQ+ individual pursuing adoption and that inclusivity is an important value to them.
- selective_decision: `{'selected': 'category', 'reason': 'profile_or_default_category_priority', 'question_kind': 'profile', 'top_category_score': 0.3476, 'top_turn_score': 0.0427, 'top_turn_similarity': 0.2078}`
- current: correct=`True`, anchor_rank=`None`, answer_seconds=`20.343`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.3476, 0.1891, 0.1605, 0.1404, 0.1389]`
  - answer: Based on what I know about Caroline, she'd most likely lean progressive or left-leaning politically. Here's why:

- She's transgender and values LGBTQ rights, which tend to align with progressive political platforms that advocate for trans rights and protections
- She's passionate about mental healt
- category_only: correct=`True`, anchor_rank=`None`, answer_seconds=`27.863`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.3476, 0.1891, 0.1605, 0.1404, 0.1389]`
  - answer: Based on what I know about Caroline, she would most likely lean progressive or left-leaning politically. Here's why:

- She's transgender and actively interested in LGBTQ rights, which generally aligns with progressive political platforms that advocate for trans rights and protections.
- She's explo
- turnmemory_only: correct=`True`, anchor_rank=`None`, answer_seconds=`27.411`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.0427, 0.0367, 0.0362, 0.0336, 0.0303]`
  - answer: Based on what I know about Caroline, she'd likely lean progressive or left-leaning politically. Her active involvement in LGBTQ activism — joining "Connected LGBTQ Activists," planning an LGBTQ art show, and specifically choosing adoption agencies for their inclusivity — all strongly align with prog
- category_turn_resource_hybrid: correct=`True`, anchor_rank=`None`, answer_seconds=`15.321`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.3476, 0.1891, 0.1605, 0.1404, 0.1389]`
  - answer: Based on what I know about Caroline, she'd most likely lean progressive/left-leaning politically. She's actively involved in LGBTQ activism through her group "Connected LGBTQ Activists," she chose her adoption agency specifically because of its LGBTQ+ inclusivity, and she's passionate about rights a
- category_turn_resource_selective: correct=`True`, anchor_rank=`None`, answer_seconds=`22.37`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.3476, 0.1891, 0.1605, 0.1404, 0.1389]`
  - answer: Based on what I know about Caroline, she would likely lean progressive or left-leaning politically. Here's why:

- **She's transgender** and has a strong interest in **LGBTQ rights**, which aligns with progressive platforms that advocate for trans protections, healthcare access, and anti-discriminat

### What did Caroline realize after her charity race?

- standard_answer: ``
- question_kind: `exact_fact`
- classified_categories: `['Timeline', 'Core Self']`
- retrieval_seconds: `57.602`
- top_category: The user's name is Caroline.
- top_turnmemory: That charity race sounds great, Mel! Making a difference & raising awareness for mental health is super rewarding - I'm really proud of you for taking part!
- top_expanded_resource: [ResourceSummary] The user expressed appreciation for their support system of friends and family who are supporting them through a transition, highlighting how much friendship and compassion matter. They noted that their loved ones' encouragement has been instrumental in helping them accept and grow
- selective_decision: `{'selected': 'turnmemory', 'reason': 'exact_fact_turnmemory_competitive', 'question_kind': 'exact_fact', 'top_category_score': 0.3216, 'top_turn_score': 0.0632, 'top_turn_similarity': 0.426}`
- current: correct=`False`, anchor_rank=`None`, answer_seconds=`24.543`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.3216, 0.2235, 0.1793, 0.1719, 0.1427]`
  - answer: I don't actually have any memory of you participating in a charity race — it was Melanie who did one for mental health awareness. I might be mixing things up, or maybe you mentioned something about it that I didn't catch. Could you remind me what happened? I'd love to hear about it!
- category_only: correct=`True`, anchor_rank=`None`, answer_seconds=`13.117`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.3216, 0.2235, 0.1793, 0.1719, 0.1427]`
  - answer: Based on what I remember, it was actually Melanie who participated in a charity race for mental health awareness, not you (Caroline). I don't have any memory of you doing a charity race or having a realization from one.

Is it possible you're thinking of Melanie's experience, or is this something th
- turnmemory_only: correct=`False`, anchor_rank=`None`, answer_seconds=`21.297`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.0632, 0.0425, 0.0422, 0.0348, 0.0344]`
  - answer: Based on the memories I have, I don't actually have any record of Caroline doing a charity race — the charity race mentioned was something Mel was doing. Caroline was cheering Mel on for it!

So I wouldn't want to make something up. If you're thinking of a different conversation, feel free to remind
- category_turn_resource_hybrid: correct=`False`, anchor_rank=`None`, answer_seconds=`47.736`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.3216, 0.2235, 0.1793, 0.1719, 0.1427]`
  - answer: I don't have any memory of Caroline doing a charity race or realizing something after one. The charity race I recall was actually something Mel was participating in — for mental health awareness. If there's something specific you're thinking of, I'd love to hear about it!
- category_turn_resource_selective: correct=`True`, anchor_rank=`None`, answer_seconds=`24.875`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.0632, 0.0425, 0.0422, 0.0348, 0.0344]`
  - answer: Based on the memories I have, there's no record of Caroline doing a charity race herself — the charity race mentioned was actually something Melanie did, and Caroline was cheering her on for it. So I don't have any information about a realization Caroline had after a charity race.

If you're thinkin

### What are the new shoes that Caroline got used for?

- standard_answer: ``
- question_kind: `exact_fact`
- classified_categories: `['Timeline', 'Social Graph']`
- retrieval_seconds: `30.464`
- top_category: Melanie has a spouse (got married recently)
- top_turnmemory: Hey Mel! Good to see you! How have you been?
- top_expanded_resource: [ResourceSummary] The user shared that they have a hand-painted bowl with sentimental value. A friend made the bowl for their 18th birthday, which was ten years ago, meaning the user is currently around 28 years old. The user appreciates the bowl's pattern and colors and associates it with art and s
- selective_decision: `{'selected': 'turnmemory', 'reason': 'exact_fact_turnmemory_competitive', 'question_kind': 'exact_fact', 'top_category_score': 0.206, 'top_turn_score': 0.0915, 'top_turn_similarity': 0.345}`
- current: correct=`True`, anchor_rank=`None`, answer_seconds=`42.647`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.4282, 0.3297, 0.2023, 0.19, 0.1668]`
  - answer: I honestly don't remember anything about new shoes! I don't think you've mentioned them to me before, or if you did, I'm drawing a blank. What kind did you get?
- category_only: correct=`False`, anchor_rank=`None`, answer_seconds=`26.847`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.206, 0.1668, 0.1418, 0.0962, 0.094]`
  - answer: I don't actually have any memory of you getting new shoes! Did I miss something, or is this something new you haven't mentioned yet? I'm curious now 😄
- turnmemory_only: correct=`True`, anchor_rank=`None`, answer_seconds=`58.082`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.0915, 0.0519, 0.0422, 0.0403, 0.0339]`
  - answer: I don't actually have any memory of you mentioning new shoes! Did you tell me about them in a conversation I might not have saved? I'd love to hear about them though — what kind did you get?
- category_turn_resource_hybrid: correct=`True`, anchor_rank=`None`, answer_seconds=`16.296`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.206, 0.1668, 0.1418, 0.0962, 0.094]`
  - answer: I don't actually have any information about Caroline getting new shoes or what they're used for. Nothing about that has come up in our conversations before! Did I miss something, or is this about someone else?
- category_turn_resource_selective: correct=`True`, anchor_rank=`None`, answer_seconds=`23.788`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.0915, 0.0519, 0.0422, 0.0403, 0.0339]`
  - answer: I don't have any memory of you getting new shoes! Did I miss something, or maybe you're thinking of a different conversation? Fill me in! 😊

### What is Caroline's reason for getting into running?

- standard_answer: ``
- question_kind: `exact_fact`
- classified_categories: `['Core Self', 'Timeline']`
- retrieval_seconds: `28.013`
- top_category: The user's name is Caroline.
- top_turnmemory: That charity race sounds great, Mel! Making a difference & raising awareness for mental health is super rewarding - I'm really proud of you for taking part!
- top_expanded_resource: [ResourceSummary] The user shared personal reflections on life lessons they've learned, emphasizing self-acceptance, the importance of finding support, and the belief that hope and love persist through difficult times. They also expressed appreciation for the joy pets bring. The AI responded with a 
- selective_decision: `{'selected': 'turnmemory', 'reason': 'exact_fact_turnmemory_competitive', 'question_kind': 'exact_fact', 'top_category_score': 0.4748, 'top_turn_score': 0.185, 'top_turn_similarity': 0.3851}`
- current: correct=`True`, anchor_rank=`None`, answer_seconds=`15.472`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.4748, 0.2973, 0.2544, 0.2433, 0.2363]`
  - answer: I don't actually have any memory of you telling me why you got into running! I know Melanie did a charity race for mental health awareness, but that's about her, not you. If you've shared your reason before, I'm sorry I don't remember it — but I'd love to hear about it if you want to share!
- category_only: correct=`True`, anchor_rank=`None`, answer_seconds=`10.612`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.4748, 0.2973, 0.2544, 0.2433, 0.2363]`
  - answer: I don't actually have any memory of you sharing why you got into running! I know your friend Mel did a charity race for mental health awareness, but I don't have anything on your own reasons. 

I'd love to hear about it though — what got you started?
- turnmemory_only: correct=`True`, anchor_rank=`None`, answer_seconds=`38.423`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.185, 0.1816, 0.1034, 0.066, 0.0655]`
  - answer: Based on the memories I have, I don't actually have a specific reason Caroline shared for getting into running herself. The conversations I can see are mostly about encouraging Melanie with running and discussing a charity race for mental health awareness.

I wouldn't want to make up an answer — do 
- category_turn_resource_hybrid: correct=`True`, anchor_rank=`None`, answer_seconds=`20.629`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.4748, 0.2973, 0.2544, 0.2433, 0.2363]`
  - answer: Based on what I know, I don't have a clear, specific memory of Caroline sharing her exact reason for getting into running. I do know she participated in a charity race that raised awareness for mental health, and running has mood-boosting benefits — but I couldn't say for sure what initially motivat
- category_turn_resource_selective: correct=`True`, anchor_rank=`None`, answer_seconds=`14.531`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.185, 0.1816, 0.1034, 0.066, 0.0655]`
  - answer: Based on the memories I have, there's actually no information about Caroline getting into running herself. The memories show Caroline encouraging and supporting Melanie about running — like cheering her on for a charity race and mentioning that running can boost your mood — but there's no record of 

### Which classical musicians does Caroline enjoy listening to?

- standard_answer: ``
- question_kind: `exact_fact`
- classified_categories: `['Core Self', 'Knowledge Base']`
- retrieval_seconds: `41.836`
- top_category: The user's name is Caroline.
- top_turnmemory: Hey Mel! Good to see you! How have you been?
- top_expanded_resource: [ResourceSummary] The user shared that they loved reading "Becoming Nicole" by Amy Ellis Nutt, a book about a trans girl and her family. The user found the story deeply inspiring, felt personally connected to it, and said it gave them hope for their own path. They highly recommend the book. The AI a
- selective_decision: `{'selected': 'turnmemory', 'reason': 'exact_fact_turnmemory_competitive', 'question_kind': 'exact_fact', 'top_category_score': 0.447, 'top_turn_score': 0.0931, 'top_turn_similarity': 0.2875}`
- current: correct=`True`, anchor_rank=`None`, answer_seconds=`25.418`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.447, 0.2888, 0.2204, 0.211, 0.1645]`
  - answer: I actually don't have any info from our conversations about which classical musicians you enjoy listening to! I know you've been learning piano, but we haven't talked about specific composers or performers you like yet. I'd love to hear about them though — do you have any favorites?
- category_only: correct=`True`, anchor_rank=`None`, answer_seconds=`24.541`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.447, 0.2888, 0.2204, 0.211, 0.1645]`
  - answer: I actually don't have any memories of us talking about specific classical musicians you enjoy listening to! I know you've been learning piano, but we haven't gotten into which composers or performers you gravitate toward yet.

I'd love to hear about it though — do you have any favorites?
- turnmemory_only: correct=`True`, anchor_rank=`None`, answer_seconds=`20.097`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.0931, 0.0572, 0.0441, 0.0405, 0.0337]`
  - answer: Honestly, I don't have that info about you! I know you're learning piano and you're into guitar too, but I haven't heard you mention any specific classical musicians you enjoy listening to. Who do you like? I'd love to hear your favorites!
- category_turn_resource_hybrid: correct=`True`, anchor_rank=`None`, answer_seconds=`22.663`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.447, 0.2888, 0.2204, 0.211, 0.1645]`
  - answer: I honestly don't have that information about you! I know you've been learning piano, but we haven't talked about which classical musicians you enjoy listening to. I'd love to know though — do you have any favorites?
- category_turn_resource_selective: correct=`True`, anchor_rank=`None`, answer_seconds=`35.33`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.0931, 0.0572, 0.0441, 0.0405, 0.0337]`
  - answer: I don't actually have that info! I know you've been learning piano, but I don't recall you ever mentioning specific classical musicians you enjoy listening to. Who are your favorites? I'd love to know!

### What setback did Caroline face recently?

- standard_answer: ``
- question_kind: `exact_fact`
- classified_categories: `['Timeline', 'Knowledge Base']`
- retrieval_seconds: `47.824`
- top_category: Melanie is in the process of moving.
- top_turnmemory: That charity race sounds great, Mel! Making a difference & raising awareness for mental health is super rewarding - I'm really proud of you for taking part!
- top_expanded_resource: [ResourceSummary] The user has a strong connection to pride events and is a passionate supporter of equality, inclusivity, and the LGBTQ+ community. They attended an LGBTQ+ pride parade around January 19-25, 2026, describing it as an amazing experience where they felt a strong sense of belonging and
- selective_decision: `{'selected': 'turnmemory', 'reason': 'exact_fact_turnmemory_competitive', 'question_kind': 'exact_fact', 'top_category_score': 0.2154, 'top_turn_score': 0.0788, 'top_turn_similarity': 0.221}`
- current: correct=`True`, anchor_rank=`None`, answer_seconds=`20.145`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'resource_vector']`
  - scores: `[0.2154, 0.1512, 0.1067, 0.094, 0.0892]`
  - answer: I don't have any information about a recent setback you faced. The memories I have don't mention anything like that — they mostly cover positive things like joining your LGBTQ activist group, planning your art show, exploring counseling as a career path, and feeling motivated after speaking with a c
- category_only: correct=`True`, anchor_rank=`None`, answer_seconds=`29.586`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.2154, 0.1512, 0.1067, 0.094, 0.0839]`
  - answer: I don't have any information in my memories about a recent setback you've faced. The things I remember are more about your activities and plans — like moving, the LGBTQ art show coming up, the charity race, joining the activist group, and some nice moments like the camping trip and pottery workshop 
- turnmemory_only: correct=`True`, anchor_rank=`None`, answer_seconds=`24.353`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.0788, 0.0702, 0.0659, 0.0483, 0.0356]`
  - answer: Based on the memories I have, there's no mention of any recent setback Caroline faced. The conversations mostly highlight positive experiences — joining an LGBTQ activist group, attending a pride parade and conference, planning an art show, going to an adoption council meeting, and feeling supported
- category_turn_resource_hybrid: correct=`True`, anchor_rank=`None`, answer_seconds=`21.641`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.2154, 0.1512, 0.1067, 0.094, 0.0839]`
  - answer: Based on our conversations, I don't recall you mentioning any recent setback, Caroline. Everything you've shared lately has been pretty positive — joining the LGBTQ activist group, attending that conference, the charity race, and feeling really motivated and connected. 

Did something happen that yo
- category_turn_resource_selective: correct=`True`, anchor_rank=`None`, answer_seconds=`34.381`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.0788, 0.0702, 0.0659, 0.0483, 0.0356]`
  - answer: Based on the conversations I have with Caroline, I don't see any mention of a recent setback. The updates I've heard from her have been mostly positive — like joining a new LGBTQ activist group, attending a pride parade, planning an LGBTQ art show, and feeling supported by friends and family during 

### What was grandpa's gift to Caroline?

- standard_answer: ``
- question_kind: `exact_fact`
- classified_categories: `['Timeline', 'Social Graph']`
- retrieval_seconds: `35.966`
- top_category: Melanie is in the process of moving.
- top_turnmemory: Hey Mel! Good to see you! How have you been?
- top_expanded_resource: [ResourceSummary] The user is casually chatting with their friend named Mel about family activities. Mel shared that their family enjoys hiking in the mountains and exploring forests as a way to connect with nature and each other. Recently, they went on a family camping trip where they explored natu
- selective_decision: `{'selected': 'turnmemory', 'reason': 'exact_fact_turnmemory_competitive', 'question_kind': 'exact_fact', 'top_category_score': 0.1373, 'top_turn_score': 0.1012, 'top_turn_similarity': 0.2841}`
- current: correct=`True`, anchor_rank=`None`, answer_seconds=`21.241`
  - strategies: `['resource_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.1447, 0.1373, 0.1325, 0.1264, 0.0829]`
  - answer: I don't have any memory of a gift from your grandpa! I do remember that your grandmother in Sweden gave you a meaningful necklace when you were young, but nothing about a grandfather's gift. Did you want to tell me about it?
- category_only: correct=`True`, anchor_rank=`None`, answer_seconds=`62.383`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.1373, 0.1325, 0.1264, 0.0829, 0.0787]`
  - answer: I don't have any memory of a gift from Caroline's grandpa. The only family gift I recall is that Caroline's grandmother in Sweden gave them a meaningful necklace when they were young. Is there something specific you're thinking of?
- turnmemory_only: correct=`True`, anchor_rank=`None`, answer_seconds=`28.546`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.1012, 0.073, 0.0533, 0.0365, 0.0314]`
  - answer: I don't have any memory of a gift from a grandpa to Caroline. The only grandparent-related gift I recall is a necklace from Caroline's grandma in Sweden, which symbolizes love, faith, and strength.
- category_turn_resource_hybrid: correct=`True`, anchor_rank=`None`, answer_seconds=`11.174`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.1373, 0.1325, 0.1264, 0.0829, 0.0787]`
  - answer: I don't have any memory of a gift from grandpa to Caroline! The only grandparent-related gift I recall is a necklace from Caroline's grandma from Sweden, which represents love, faith, and strength. If there's something else you're thinking of, I might not have heard about it yet!
- category_turn_resource_selective: correct=`False`, anchor_rank=`None`, answer_seconds=`17.733`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.1012, 0.073, 0.0533, 0.0365, 0.0314]`
  - answer: Based on what I remember, I don't have any record of a gift from grandpa. The special gift I do remember is a necklace from my grandma in Sweden - it represents love, faith, and strength, and it's really meaningful to me as a reminder of my roots.

Did I mention something about a gift from grandpa t

### What did Caroline and her family see during their camping trip last year?

- standard_answer: ``
- question_kind: `exact_fact`
- classified_categories: `['Timeline', 'Social Graph']`
- retrieval_seconds: `36.887`
- top_category: Mel recently went on a family camping trip involving nature exploration, campfire marshmallow roasting, and a hike.
- top_turnmemory: Hey Mel! Good to see you! How have you been?
- top_expanded_resource: [ResourceSummary] The user expressed admiration for a photo and mentioned bonding over a shared love of nature. They shared that they attended a council meeting for adoption last Friday (January 30, 2026), describing it as inspiring and emotional. The experience reinforced their determination to ado
- selective_decision: `{'selected': 'turnmemory', 'reason': 'exact_fact_turnmemory_competitive', 'question_kind': 'exact_fact', 'top_category_score': 0.3082, 'top_turn_score': 0.1553, 'top_turn_similarity': 0.3377}`
- current: correct=`True`, anchor_rank=`None`, answer_seconds=`61.333`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.3082, 0.2181, 0.1882, 0.185, 0.1804]`
  - answer: Based on what I remember, the details I have about a family camping trip mention nature exploration, campfire marshmallow roasting, and a hike — but I don't have specific details about what was *seen* during that trip. Also, the memory I have references it as a recent trip rather than one from last 
- category_only: correct=`False`, anchor_rank=`None`, answer_seconds=`21.07`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.3082, 0.3075, 0.2322, 0.2181, 0.1882]`
  - answer: I don't actually have any memory of you going on a camping trip last year! The camping trip I do know about was your friend Mel's — and all I remember about that one is that it involved nature exploration, campfire marshmallow roasting, and a hike. But I don't have details about what they specifical
- turnmemory_only: correct=`True`, anchor_rank=`None`, answer_seconds=`15.95`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.1553, 0.119, 0.0791, 0.0767, 0.0636]`
  - answer: I don't have any memory of a camping trip from last year! It's possible we haven't talked about that yet, or maybe it slipped by in conversation. I'd love to hear about it though — what did you and your family see? 🏕️
- category_turn_resource_hybrid: correct=`True`, anchor_rank=`None`, answer_seconds=`21.152`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.3082, 0.3075, 0.2322, 0.2181, 0.1882]`
  - answer: I don't have any information about Caroline going on a camping trip with her family. The camping trip I do know about was actually Mel's family trip — and even then, I don't have details about what they specifically saw, just that it involved nature exploration, a hike, and campfire marshmallow roas
- category_turn_resource_selective: correct=`True`, anchor_rank=`None`, answer_seconds=`34.484`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.1553, 0.119, 0.0791, 0.0767, 0.0636]`
  - answer: I don't have any memory of a camping trip from last year, sorry! It's possible we haven't talked about that yet, or it might have slipped by in conversation. I'd love to hear about it though — what did you all see? 🏕️

### What precautionary sign did Caroline see at the café?

- standard_answer: ``
- question_kind: `exact_fact`
- classified_categories: `['Timeline', 'Knowledge Base']`
- retrieval_seconds: `61.775`
- top_category: Melanie is in the process of moving.
- top_turnmemory: That charity race sounds great, Mel! Making a difference & raising awareness for mental health is super rewarding - I'm really proud of you for taking part!
- top_expanded_resource: [ResourceSummary] The user shared an exciting life update with the AI, mentioning they joined a new LGBTQ activist group last Tuesday (February 3, 2026). They expressed enthusiasm about meeting passionate people who share their commitment to rights and community support. They described the experienc
- selective_decision: `{'selected': 'category', 'reason': 'exact_fact_category_stronger', 'question_kind': 'exact_fact', 'top_category_score': 0.1826, 'top_turn_score': 0.0603, 'top_turn_similarity': 0.1746}`
- current: correct=`True`, anchor_rank=`None`, answer_seconds=`15.783`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.1826, 0.1408, 0.1139, 0.1125, 0.112]`
  - answer: I don't have any memory of Caroline seeing a precautionary sign at a café. I don't think that's something that's come up in our conversations before — could you fill me in on what happened?
- category_only: correct=`True`, anchor_rank=`None`, answer_seconds=`16.002`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.1826, 0.1408, 0.1139, 0.1125, 0.112]`
  - answer: I don't have any memory of Caroline mentioning a precautionary sign at a café. This might be something from a conversation I don't have record of, or it could be from outside our chats. Could you remind me what sign you're referring to?
- turnmemory_only: correct=`True`, anchor_rank=`None`, answer_seconds=`22.441`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.0603, 0.052, 0.0489, 0.046, 0.044]`
  - answer: I don't have any memory of Caroline mentioning a precautionary sign at a café. I'm not sure what you're referring to — could you share more context?
- category_turn_resource_hybrid: correct=`True`, anchor_rank=`None`, answer_seconds=`25.485`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.1826, 0.1408, 0.1139, 0.1125, 0.112]`
  - answer: I don't have any memory of Caroline mentioning a precautionary sign at a café. I might have missed that detail, or it could be from a conversation that didn't get saved. Could you remind me what it said?
- category_turn_resource_selective: correct=`False`, anchor_rank=`None`, answer_seconds=`30.562`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.1826, 0.1408, 0.1139, 0.1125, 0.112]`
  - answer: I don't have any memory of Caroline seeing a precautionary sign at a café. That detail isn't something I have information about — could you fill me in on what happened?

### What did Caroline research?

- standard_answer: `Adoption agencies`
- question_kind: `exact_fact`
- classified_categories: `['Timeline', 'Knowledge Base']`
- retrieval_seconds: `34.076`
- top_category: Melanie is in the process of moving.
- top_turnmemory: I'm keen on counseling or working in mental health - I'd love to support those with similar issues.
- top_expanded_resource: [ResourceSummary] The user expressed appreciation for their support system of friends and family who are supporting them through a transition, highlighting how much friendship and compassion matter. They noted that their loved ones' encouragement has been instrumental in helping them accept and grow
- selective_decision: `{'selected': 'turnmemory', 'reason': 'exact_fact_turnmemory_competitive', 'question_kind': 'exact_fact', 'top_category_score': 0.2262, 'top_turn_score': 0.1466, 'top_turn_similarity': 0.2893}`
- current: correct=`False`, anchor_rank=`None`, answer_seconds=`10.102`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.2262, 0.1618, 0.1205, 0.1136, 0.1122]`
  - answer: I don't have any memory of Caroline researching something specific. Could you remind me what you're referring to?
- category_only: correct=`False`, anchor_rank=`None`, answer_seconds=`26.458`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.2262, 0.1618, 0.1205, 0.1136, 0.1122]`
  - answer: I don't have any information about what Caroline researched — there's nothing in my memories that mentions that. Could you give me a little more context? I'd love to help if I can!
- turnmemory_only: correct=`True`, anchor_rank=`13`, answer_seconds=`14.633`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.1466, 0.1053, 0.0679, 0.0636, 0.0525]`
  - answer: Based on what was shared before, Caroline was researching adoption agencies — it's been a dream of hers to have a family and give a loving home to kids who need one.
- category_turn_resource_hybrid: correct=`False`, anchor_rank=`None`, answer_seconds=`8.368`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.2262, 0.1618, 0.1205, 0.1136, 0.1122]`
  - answer: I don't have any memory of Caroline researching something specific. Could you remind me what you're referring to? I'd love to help if I can!
- category_turn_resource_selective: correct=`True`, anchor_rank=`13`, answer_seconds=`17.314`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.1466, 0.1053, 0.0679, 0.0636, 0.0525]`
  - answer: Caroline researched adoption agencies — it's been a dream of hers to have a family and give a loving home to kids who need one.

### What advice does Caroline give for getting started with adoption?

- standard_answer: `Do research, find an adoption agency or lawyer, gather necessary documents, and prepare emotionally.`
- question_kind: `exact_fact`
- classified_categories: `['Knowledge Base', 'Social Graph']`
- retrieval_seconds: `30.54`
- top_category: Melanie has a spouse (got married recently)
- top_turnmemory: That photo is stunning! So glad you bonded over our love of nature. Last Friday I went to a council meeting for adoption. It was inspiring and emotional - so many people wanted to create loving homes for children in need. It made me even more determined to adopt.
- top_expanded_resource: [ResourceSummary] The user expressed appreciation to Melanie about having their own platform and shared details about their LGBTQ activist group called "Connected LGBTQ Activists". The group consists of diverse members who invest in positive changes, hold regular meetings, and plan events and campai
- selective_decision: `{'selected': 'turnmemory', 'reason': 'exact_fact_turnmemory_competitive', 'question_kind': 'exact_fact', 'top_category_score': 0.202, 'top_turn_score': 0.1746, 'top_turn_similarity': 0.3473}`
- current: correct=`False`, anchor_rank=`None`, answer_seconds=`44.353`
  - strategies: `['resource_vector', 'resource_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.21, 0.2042, 0.202, 0.178, 0.1598]`
  - answer: Based on what I know from our conversations, Caroline hasn't laid out a formal list of advice, but from her own experience getting started with adoption, here's what she'd likely share:

1. **Attend council meetings or informational sessions** — Caroline went to one in late January and found it incr
- category_only: correct=`False`, anchor_rank=`None`, answer_seconds=`19.854`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.202, 0.178, 0.1598, 0.0957, 0.0799]`
  - answer: Honestly, I don't have a detailed record of specific adoption advice from Caroline. What I do know is that she attended an adoption council meeting and found it really inspiring and emotional — she mentioned that many people there were motivated by a genuine desire to create loving homes for childre
- turnmemory_only: correct=`False`, anchor_rank=`None`, answer_seconds=`19.664`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.1746, 0.1569, 0.1475, 0.127, 0.1115]`
  - answer: Based on what I know from our conversations, Caroline hasn't really shared specific advice about getting started with adoption — she's actually on her own adoption journey right now! What she has mentioned is that she's been researching adoption agencies, and she attended a council meeting for adopt
- category_turn_resource_hybrid: correct=`False`, anchor_rank=`None`, answer_seconds=`22.254`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.202, 0.178, 0.1598, 0.0957, 0.0799]`
  - answer: Based on what I know from our conversations, Caroline has shared a few things about her adoption journey, though she hasn't laid out a full step-by-step guide. Here's what she's mentioned:

- **Research adoption agencies** — She's been actively looking into different agencies, which seems like her s
- category_turn_resource_selective: correct=`False`, anchor_rank=`None`, answer_seconds=`40.841`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.1746, 0.1569, 0.1475, 0.127, 0.1115]`
  - answer: Based on what Caroline has shared about her adoption journey, here's what she's mentioned about getting started:

1. **Research adoption agencies** — She's been actively looking into different agencies as a key step in the process.

2. **Attend council meetings** — She went to an adoption council me

### What was the poetry reading that Caroline attended about?

- standard_answer: `It was a transgender poetry reading where transgender people shared their stories.`
- question_kind: `exact_fact`
- classified_categories: `['Timeline', 'Knowledge Base']`
- retrieval_seconds: `31.815`
- top_category: Mel participated in a charity race for mental health awareness.
- top_turnmemory: That charity race sounds great, Mel! Making a difference & raising awareness for mental health is super rewarding - I'm really proud of you for taking part!
- top_expanded_resource: [ResourceSummary] The user is casually chatting with their friend named Mel about family activities. Mel shared that their family enjoys hiking in the mountains and exploring forests as a way to connect with nature and each other. Recently, they went on a family camping trip where they explored natu
- selective_decision: `{'selected': 'turnmemory', 'reason': 'exact_fact_turnmemory_competitive', 'question_kind': 'exact_fact', 'top_category_score': 0.2035, 'top_turn_score': 0.1297, 'top_turn_similarity': 0.2452}`
- current: correct=`False`, anchor_rank=`None`, answer_seconds=`9.895`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.2035, 0.1921, 0.1785, 0.1759, 0.1756]`
  - answer: I don't have any memory of a poetry reading that Caroline attended. It's possible I missed that conversation, or it might not have come up in our chats. Could you tell me more about it? I'd love to hear what it was about!
- category_only: correct=`False`, anchor_rank=`None`, answer_seconds=`5.525`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.2035, 0.1921, 0.1785, 0.1756, 0.1656]`
  - answer: I don't actually have any memory of a poetry reading that Caroline attended! None of my notes mention that event. Could you tell me more about it? I'd love to hear what it was about. 😊
- turnmemory_only: correct=`False`, anchor_rank=`None`, answer_seconds=`14.142`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.1297, 0.1112, 0.1096, 0.1011, 0.0994]`
  - answer: I don't actually have any memory of Caroline attending a poetry reading! Nothing like that has come up in our conversations before. Maybe you're thinking of something else, or it might be from a chat I don't have context for?
- category_turn_resource_hybrid: correct=`False`, anchor_rank=`None`, answer_seconds=`8.122`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.2035, 0.1921, 0.1785, 0.1756, 0.1656]`
  - answer: I don't have any memory of Caroline attending a poetry reading, so I'm not sure what you're referring to! Could you share more about it? I'd love to hear about it. 😊
- category_turn_resource_selective: correct=`False`, anchor_rank=`None`, answer_seconds=`13.449`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.1297, 0.1112, 0.1096, 0.1011, 0.0994]`
  - answer: I don't actually have any memory of Caroline attending a poetry reading! The conversations I remember involve things like a pride parade, an LGBTQ counseling workshop, an adoption council meeting, and an activist group meeting - but no poetry reading comes to mind.

Maybe you're thinking of a differ

### Did Caroline make the black and white bowl in the photo?

- standard_answer: `No`
- question_kind: `exact_fact`
- classified_categories: `['Timeline', 'Knowledge Base']`
- retrieval_seconds: `30.549`
- top_category: Melanie is in the process of moving.
- top_turnmemory: That photo is stunning! So glad you bonded over our love of nature. Last Friday I went to a council meeting for adoption. It was inspiring and emotional - so many people wanted to create loving homes for children in need. It made me even more determined to adopt.
- top_expanded_resource: [ResourceSummary] The user is currently researching adoption agencies, driven by a long-held dream of having a family and providing a loving home to children in need. They have expressed gratitude for the support received from friends and mentors during this process. They are now beginning the hard 
- selective_decision: `{'selected': 'turnmemory', 'reason': 'exact_fact_turnmemory_competitive', 'question_kind': 'exact_fact', 'top_category_score': 0.2697, 'top_turn_score': 0.2245, 'top_turn_similarity': 0.3581}`
- current: correct=`False`, anchor_rank=`None`, answer_seconds=`34.509`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.2697, 0.216, 0.197, 0.1901, 0.1846]`
  - answer: I don't have any memory of a black and white bowl or a photo like that, so I can't say for sure! Do you want to tell me about it?
- category_only: correct=`True`, anchor_rank=`None`, answer_seconds=`34.417`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.2697, 0.216, 0.197, 0.1901, 0.1846]`
  - answer: No, that was actually my bowl! I made it in a pottery class and was pretty proud of how it turned out. Caroline's pottery from that workshop with the kids was different — they each made their own pots but none of them were that black and white one.
- turnmemory_only: correct=`True`, anchor_rank=`10`, answer_seconds=`21.183`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.2245, 0.1632, 0.1509, 0.1389, 0.1294]`
  - answer: No, Caroline didn't make the black and white bowl. Based on the conversation, she was actually asking someone else if *they* made it after seeing their photo of it!
- category_turn_resource_hybrid: correct=`True`, anchor_rank=`14`, answer_seconds=`20.196`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.2697, 0.216, 0.197, 0.1901, 0.1846]`
  - answer: No, Caroline didn't make it — they were actually the one asking about that bowl! It looks like Mel or one of Mel's kids made it during the pottery workshop they went to on January 30th. Caroline just admired it and asked if Mel had made it.
- category_turn_resource_selective: correct=`True`, anchor_rank=`10`, answer_seconds=`31.384`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.2245, 0.1632, 0.1509, 0.1389, 0.1294]`
  - answer: No, Caroline didn't make the black and white bowl. She was actually admiring it and asking someone else if they made it!

### When is Caroline going to the transgender conference?

- standard_answer: `February 2026`
- question_kind: `exact_fact`
- classified_categories: `['Timeline', 'Social Graph']`
- retrieval_seconds: `55.383`
- top_category: The user plans to attend a transgender conference in January 2026.
- top_turnmemory: Hey Mel! A lot's happened since we last chatted - I just joined a new LGBTQ activist group last Tues. I'm meeting so many cool people who are as passionate as I am about rights and community support. I'm giving my voice and making a real difference, plus it's fulfilling in so many ways. It's just gr
- top_expanded_resource: [ResourceSummary] The user is exploring counseling and mental health as a potential career path, motivated by a desire to help people who have experienced similar life situations as themselves. Talking to a community reinforced this interest, and they are excited about giving back and using their pe
- selective_decision: `{'selected': 'turnmemory', 'reason': 'exact_fact_turnmemory_competitive', 'question_kind': 'exact_fact', 'top_category_score': 0.5794, 'top_turn_score': 0.2279, 'top_turn_similarity': 0.3395}`
- current: correct=`False`, anchor_rank=`None`, answer_seconds=`12.464`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.5794, 0.3824, 0.3393, 0.3208, 0.3175]`
  - answer: Based on what you've shared before, you're planning to attend the transgender conference in January 2026.
- category_only: correct=`False`, anchor_rank=`None`, answer_seconds=`12.677`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.5794, 0.3824, 0.3393, 0.3208, 0.3175]`
  - answer: Based on what you've shared, the transgender conference is planned for January 2026.
- turnmemory_only: correct=`False`, anchor_rank=`None`, answer_seconds=`26.629`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.2279, 0.2213, 0.2077, 0.1914, 0.1857]`
  - answer: Based on what you mentioned before, you said you were going to the transgender conference "this month" — but there wasn't a specific date mentioned. Do you remember the exact date, or has it already passed?
- category_turn_resource_hybrid: correct=`False`, anchor_rank=`None`, answer_seconds=`10.701`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.5794, 0.3824, 0.3393, 0.3208, 0.3175]`
  - answer: Caroline is planning to attend the transgender conference in January 2026.
- category_turn_resource_selective: correct=`False`, anchor_rank=`None`, answer_seconds=`13.359`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.2279, 0.2213, 0.2077, 0.1914, 0.1857]`
  - answer: Based on what was shared, Caroline mentioned going to a transgender conference "this month," but no specific date was given — just that it was coming up soon!

### When did Caroline attend a pride parade in August?

- standard_answer: `The Friday before 20 February 2026`
- question_kind: `exact_fact`
- classified_categories: `['Timeline', 'Knowledge Base']`
- retrieval_seconds: `30.002`
- top_category: The user and the transgender teen they mentor attended an LGBTQ+ pride parade/event together in January 2026 (approximately January 19-25, 2026).
- top_turnmemory: Wow, nice pic! You both looked amazing. One special memory for me was this pride parade I went to a few weeks ago.
- top_expanded_resource: [ResourceSummary] The user asked Melanie about her family's support during her move. Melanie responded positively, saying her family has been awesome, helpful, and very loving and supportive throughout the process.
- selective_decision: `{'selected': 'turnmemory', 'reason': 'exact_fact_turnmemory_competitive', 'question_kind': 'exact_fact', 'top_category_score': 0.3476, 'top_turn_score': 0.2746, 'top_turn_similarity': 0.42}`
- current: correct=`False`, anchor_rank=`None`, answer_seconds=`16.852`
  - strategies: `['resource_vector', 'category_vector', 'resource_vector', 'category_vector', 'category_vector']`
  - scores: `[0.3518, 0.3476, 0.3197, 0.3077, 0.3034]`
  - answer: Based on what I know, there's no record of Caroline attending a pride parade in August. The pride parade I'm aware of was in January 2026 — Caroline attended one around January 19-25 and also saw another one in their city around January 31 - February 1. No August pride events are mentioned in anythi
- category_only: correct=`False`, anchor_rank=`None`, answer_seconds=`16.403`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.3476, 0.3077, 0.3034, 0.2875, 0.2542]`
  - answer: Based on what I remember, there's no record of a pride parade in August. The pride event I know about was in January 2026 — you attended it with the transgender teen you mentor. 

Are you maybe thinking of a different event, or mixing it up with the January one?
- turnmemory_only: correct=`False`, anchor_rank=`None`, answer_seconds=`13.329`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.2746, 0.2705, 0.1648, 0.1607, 0.1414]`
  - answer: I don't have a specific memory of Caroline attending a pride parade in August. The memories I have mention going to a pride parade "a few weeks ago" and "last week," but no specific date or month is tied to those events. Sorry I can't help with that detail!
- category_turn_resource_hybrid: correct=`False`, anchor_rank=`None`, answer_seconds=`13.655`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.3476, 0.3077, 0.3034, 0.2875, 0.2542]`
  - answer: Based on what I know, there's no record of Caroline attending a pride parade in August. The pride parade I remember happened in January 2026, around January 19-25. That's the one where you and the transgender teen you mentor went together!
- category_turn_resource_selective: correct=`False`, anchor_rank=`None`, answer_seconds=`38.527`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.2746, 0.2705, 0.1648, 0.1607, 0.1414]`
  - answer: Hey! Looking through what I remember from our conversations, I don't actually have a record of you attending a pride parade specifically in August. You've mentioned going to pride parades and events before, but the timing wasn't tied to August in what you shared with me. 

Did I miss something, or m

### What does Caroline's drawing symbolize for her?

- standard_answer: `Freedom and being true to herself.`
- question_kind: `exact_fact`
- classified_categories: `['Core Self', 'Knowledge Base']`
- retrieval_seconds: `38.632`
- top_category: The user's name is Caroline.
- top_turnmemory: Thanks, Melanie! This necklace is super special to me - a gift from my grandma in my home country, Sweden. She gave it to me when I was young, and it stands for love, faith and strength. It's like a reminder of my roots and all the love and support I get from my family.
- top_expanded_resource: [ResourceSummary] The user is currently researching adoption agencies, driven by a long-held dream of having a family and providing a loving home to children in need. They have expressed gratitude for the support received from friends and mentors during this process. They are now beginning the hard 
- selective_decision: `{'selected': 'turnmemory', 'reason': 'exact_fact_turnmemory_competitive', 'question_kind': 'exact_fact', 'top_category_score': 0.5268, 'top_turn_score': 0.1878, 'top_turn_similarity': 0.3413}`
- current: correct=`False`, anchor_rank=`None`, answer_seconds=`8.171`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.5268, 0.3864, 0.3297, 0.2859, 0.2799]`
  - answer: Based on what I know, I don't have a specific memory of a particular drawing and what it symbolized for you. I do know that painting is something meaningful to you — you bonded with Melanie over painting together and chatting about nature, and it seems like it's been a way to connect with others and
- category_only: correct=`False`, anchor_rank=`None`, answer_seconds=`10.118`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.5268, 0.3864, 0.3297, 0.2859, 0.2799]`
  - answer: Honestly, I don't have a specific memory of a particular drawing or what it symbolized for you. I know that painting is something meaningful to you — you and Mel bonded over painting together and chatting about nature — but I don't want to guess at the meaning behind a specific piece if I don't actu
- turnmemory_only: correct=`False`, anchor_rank=`None`, answer_seconds=`11.733`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.1878, 0.1609, 0.1315, 0.1304, 0.13]`
  - answer: Based on the memories I have, I don't actually have specific details about what Caroline's drawing symbolizes for her. I know she's shared a painting for an art show and has an upcoming LGBTQ art show featuring her paintings, but the meaning behind a particular drawing wasn't mentioned in what I can
- category_turn_resource_hybrid: correct=`False`, anchor_rank=`None`, answer_seconds=`15.652`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.5268, 0.3864, 0.3297, 0.2859, 0.2799]`
  - answer: Based on what I know from our conversations, I don't actually have details about the specific symbolism behind your drawing. I remember you shared a painting for an art show, and that we've talked about painting and nature before, but you didn't go into what that particular piece meant to you.

I'd 
- category_turn_resource_selective: correct=`False`, anchor_rank=`None`, answer_seconds=`14.162`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.1878, 0.1609, 0.1315, 0.1304, 0.13]`
  - answer: Based on the memories I have, I don't actually have details about what a specific drawing symbolizes for Caroline. I know she's passionate about painting — she's had pieces in an art show and even planned an LGBTQ art show — but the deeper meaning or symbolism behind any particular drawing wasn't so

### What did Caroline and her family do while camping?

- standard_answer: ``
- question_kind: `exact_fact`
- classified_categories: `['Timeline', 'Social Graph']`
- retrieval_seconds: `27.145`
- top_category: Mel recently went on a family camping trip involving nature exploration, campfire marshmallow roasting, and a hike.
- top_turnmemory: Sounds great, Mel. Glad you made some new family mems. How was it? Anything fun?
- top_expanded_resource: [ResourceSummary] The user has a strong connection to pride events and is a passionate supporter of equality, inclusivity, and the LGBTQ+ community. They attended an LGBTQ+ pride parade around January 19-25, 2026, describing it as an amazing experience where they felt a strong sense of belonging and
- selective_decision: `{'selected': 'turnmemory', 'reason': 'exact_fact_turnmemory_competitive', 'question_kind': 'exact_fact', 'top_category_score': 0.4828, 'top_turn_score': 0.2406, 'top_turn_similarity': 0.3803}`
- current: correct=`False`, anchor_rank=`None`, answer_seconds=`29.977`
  - strategies: `['category_vector', 'resource_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.4828, 0.3343, 0.3009, 0.269, 0.233]`
  - answer: Based on what I remember, the camping trip was actually Mel's family, not yours! Mel shared that during their camping trip, they explored nature, roasted marshmallows around a campfire, and went on a hike with amazing views. Mel mentioned that the two younger kids really love nature, and the whole e
- category_only: correct=`False`, anchor_rank=`None`, answer_seconds=`20.524`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.4828, 0.4006, 0.3009, 0.2906, 0.2902]`
  - answer: Based on what I remember, the camping trip was actually Mel's family — not yours! Mel went camping with their family and they did nature exploration, roasted marshmallows by the campfire, and went on a hike.

I don't have any record of you going camping recently. Did you go on one too, or are you th
- turnmemory_only: correct=`True`, anchor_rank=`None`, answer_seconds=`21.389`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.2406, 0.2183, 0.1669, 0.1613, 0.1295]`
  - answer: I don't actually have any memory of Caroline going camping with her family! The closest thing I can recall is that she mentioned having a picnic with family and friends, but no camping trip comes to mind. Maybe you're thinking of a different conversation?
- category_turn_resource_hybrid: correct=`False`, anchor_rank=`None`, answer_seconds=`19.987`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.4828, 0.4006, 0.3009, 0.2906, 0.2902]`
  - answer: Hey, just a quick clarification — it was actually Mel who went on the camping trip, not you! From what I remember, Mel's family camping trip involved nature exploration, roasting marshmallows over a campfire, and going on a hike. You had asked Mel about how it went, so it sounds like you were hearin
- category_turn_resource_selective: correct=`True`, anchor_rank=`None`, answer_seconds=`48.281`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.2406, 0.2183, 0.1669, 0.1613, 0.1295]`
  - answer: I don't actually have any memory of Caroline going camping with her family! I know they had a picnic together recently, and her family has been supportive during her move, but there's no mention of a camping trip in what I remember from our conversations.

Maybe you're thinking of something else, or

### What does Caroline say running has been great for?

- standard_answer: ``
- question_kind: `exact_fact`
- classified_categories: `['Core Self', 'Timeline']`
- retrieval_seconds: `31.99`
- top_category: The user's name is Caroline.
- top_turnmemory: That charity race sounds great, Mel! Making a difference & raising awareness for mental health is super rewarding - I'm really proud of you for taking part!
- top_expanded_resource: [ResourceSummary] The user has a strong connection to pride events and is a passionate supporter of equality, inclusivity, and the LGBTQ+ community. They attended an LGBTQ+ pride parade around January 19-25, 2026, describing it as an amazing experience where they felt a strong sense of belonging and
- selective_decision: `{'selected': 'turnmemory', 'reason': 'exact_fact_turnmemory_competitive', 'question_kind': 'exact_fact', 'top_category_score': 0.5144, 'top_turn_score': 0.2662, 'top_turn_similarity': 0.3231}`
- current: correct=`False`, anchor_rank=`None`, answer_seconds=`25.947`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'resource_vector', 'category_vector']`
  - scores: `[0.5144, 0.2431, 0.2186, 0.218, 0.2129]`
  - answer: Based on what you mentioned before, you said running can boost mood. 😊
- category_only: correct=`True`, anchor_rank=`None`, answer_seconds=`23.625`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.5144, 0.2908, 0.2431, 0.2355, 0.2186]`
  - answer: I don't actually have a memory of you specifically talking about what running has been great for! I know your friend Mel did a charity race for mental health awareness, but I don't have a record of you sharing your own thoughts on running.

Do you want to tell me about it? I'd love to hear!
- turnmemory_only: correct=`False`, anchor_rank=`None`, answer_seconds=`20.14`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.2662, 0.2245, 0.2103, 0.2085, 0.1724]`
  - answer: Based on what Caroline has shared, she said running can really boost your mood!
- category_turn_resource_hybrid: correct=`False`, anchor_rank=`None`, answer_seconds=`22.41`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.5144, 0.2908, 0.2431, 0.2355, 0.2186]`
  - answer: Based on what you've shared, you mentioned that running can really **boost your mood**!
- category_turn_resource_selective: correct=`False`, anchor_rank=`None`, answer_seconds=`35.651`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.2662, 0.2245, 0.2103, 0.2085, 0.1724]`
  - answer: Based on what Caroline has shared, she said running can really boost your mood.

### How did Caroline feel about her family after the accident?

- standard_answer: ``
- question_kind: `exact_fact`
- classified_categories: `['Core Self', 'Timeline']`
- retrieval_seconds: `35.76`
- top_category: The user's name is Caroline.
- top_turnmemory: That's awesome, Melanie! How have your family been supportive during your move?
- top_expanded_resource: [ResourceSummary] The user praised Mel (the AI) for participating in a charity race that raises awareness for mental health. Mel responded that the event was thought-provoking and shared a personal insight about the importance of self-care, describing it as a journey. Mel expressed that taking care 
- selective_decision: `{'selected': 'turnmemory', 'reason': 'exact_fact_turnmemory_competitive', 'question_kind': 'exact_fact', 'top_category_score': 0.539, 'top_turn_score': 0.2818, 'top_turn_similarity': 0.3912}`
- current: correct=`False`, anchor_rank=`None`, answer_seconds=`11.344`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'resource_vector', 'category_vector']`
  - scores: `[0.539, 0.3828, 0.3264, 0.2847, 0.2692]`
  - answer: I don't have any memory of an accident being mentioned in our conversations. I know your family has been really supportive through your life transition and during a move, and that you value their love and encouragement a lot — but I don't recall anything about an accident. Could you tell me more abo
- category_only: correct=`False`, anchor_rank=`None`, answer_seconds=`8.607`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.539, 0.3828, 0.2829, 0.2692, 0.2463]`
  - answer: Hey, I don't actually have any memory of an accident in your life — nothing like that has come up in our conversations before. I don't want to guess or make something up about something so personal.

If you're comfortable sharing, I'm here to listen. ❤️
- turnmemory_only: correct=`False`, anchor_rank=`None`, answer_seconds=`16.415`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.2818, 0.2233, 0.217, 0.1745, 0.1522]`
  - answer: I don't have any memory of Caroline mentioning an accident — that doesn't come up in anything we've talked about. I wouldn't want to guess or make something up about something that important.

Is this something you're curious about, or maybe mixing up with someone else's story? I'm happy to chat abo
- category_turn_resource_hybrid: correct=`False`, anchor_rank=`None`, answer_seconds=`8.248`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.539, 0.3828, 0.2829, 0.2692, 0.2463]`
  - answer: Hey, I don't actually have any memory of an accident in our conversations — I'm not sure what you're referring to. Could you fill me in on what happened? I'd love to listen if you want to talk about it. 💛
- category_turn_resource_selective: correct=`False`, anchor_rank=`None`, answer_seconds=`13.526`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.2818, 0.2233, 0.217, 0.1745, 0.1522]`
  - answer: I don't actually have any memory of Caroline mentioning an accident — none of our conversations touched on that. I wouldn't want to guess or make something up about something so personal. If you're thinking of a specific moment, maybe you could share a bit more context? I'm happy to talk through wha

### What does Caroline love most about camping with her family?

- standard_answer: ``
- question_kind: `exact_fact`
- classified_categories: `['Core Self', 'Social Graph']`
- retrieval_seconds: `53.538`
- top_category: The user's name is Caroline.
- top_turnmemory: That's awesome, Melanie! How have your family been supportive during your move?
- top_expanded_resource: [ResourceSummary] The user has a strong connection to pride events and is a passionate supporter of equality, inclusivity, and the LGBTQ+ community. They attended an LGBTQ+ pride parade around January 19-25, 2026, describing it as an amazing experience where they felt a strong sense of belonging and
- selective_decision: `{'selected': 'turnmemory', 'reason': 'exact_fact_turnmemory_competitive', 'question_kind': 'exact_fact', 'top_category_score': 0.4171, 'top_turn_score': 0.2623, 'top_turn_similarity': 0.3698}`
- current: correct=`False`, anchor_rank=`None`, answer_seconds=`73.459`
  - strategies: `['resource_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.5197, 0.473, 0.4171, 0.3185, 0.2976]`
  - answer: Honestly, I don't have a specific memory of you telling me what you love most about camping with your family. I know you enjoy hiking and nature from our chats, and you've mentioned bonding over nature-related things with Mel — but I don't want to assume that's the same thing.

What *do* you love mo
- category_only: correct=`False`, anchor_rank=`None`, answer_seconds=`26.242`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.4171, 0.3464, 0.3185, 0.3164, 0.2976]`
  - answer: Honestly, I don't have a specific memory of you telling me what you love most about camping with your family! I know your friend Mel recently went on a family camping trip, and that you and Mel bonded over painting and chatting about nature — but I don't want to assume that's the same thing.

So... 
- turnmemory_only: correct=`True`, anchor_rank=`None`, answer_seconds=`24.23`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.2623, 0.2606, 0.2372, 0.2046, 0.1868]`
  - answer: I don't actually have any memories of Caroline talking about camping with her family! The closest thing I can recall is a mention of a picnic they had together, and that Caroline loves nature and hiking. But specifics about camping aren't something that's come up in our conversations.
- category_turn_resource_hybrid: correct=`True`, anchor_rank=`None`, answer_seconds=`15.459`
  - strategies: `['category_vector', 'category_vector', 'category_vector', 'category_vector', 'category_vector']`
  - scores: `[0.4171, 0.3464, 0.3185, 0.3164, 0.2976]`
  - answer: I don't have a specific memory of you telling me what you love most about camping with family. I know you and Mel bonded over nature and painting, and that family memories mean a lot to you — but I don't want to guess and put words in your mouth!

What *do* you love most about it? I'd love to hear!
- category_turn_resource_selective: correct=`True`, anchor_rank=`None`, answer_seconds=`19.138`
  - strategies: `['turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector', 'turnmemory_vector']`
  - scores: `[0.2623, 0.2606, 0.2372, 0.2046, 0.1868]`
  - answer: I don't actually have any memories of Caroline talking about camping with her family, so I can't say what she loves most about it. The memories I do have mention things like a family picnic, bonding over nature, and how much she values her family's support — but nothing specifically about camping. M
