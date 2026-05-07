# Retrieval Tuning A/B Validation

- character: `caroline`
- sample: `0`
- data_dir: `data\converted_data_recent_2026q1_name_trimmed`
- user_id: `dbafc7e4-5d73-4acd-b3aa-7d7fd7d79c92`
- generated_at_utc: `2026-04-22T10:22:52.071192+00:00`

## Summary

- overall_judgement: `partial benefit`
- scoring_help_count: `1`
- top_k_help_count: `1`
- both_help_count: `0`
- route_blocked_count: `0`
- unresolved_count: `3`

## Question Matrix

| Question | Conclusion | A | B | C | D |
| --- | --- | --- | --- | --- | --- |
| When did Caroline go to the LGBTQ support group? | scoring helps | category+resource<br>hit=False<br>rank=None<br>shadow=None | category_only<br>hit=True<br>rank=4<br>shadow=3 | category+resource<br>hit=False<br>rank=None<br>shadow=8 | category+resource<br>hit=True<br>rank=3<br>shadow=3 |
| When did Caroline meet up with her friends, family, and mentors? | neither helps | category_only<br>hit=True<br>rank=1<br>shadow=5 | category_only<br>hit=True<br>rank=1<br>shadow=3 | category+resource<br>hit=True<br>rank=1<br>shadow=5 | category+resource<br>hit=True<br>rank=1<br>shadow=3 |
| How long has Caroline had her current group of friends for? | neither helps | category_only<br>hit=True<br>rank=1<br>shadow=None | category_only<br>hit=True<br>rank=1<br>shadow=None | category_only<br>hit=True<br>rank=1<br>shadow=None | category_only<br>hit=True<br>rank=1<br>shadow=None |
| Who supports Caroline when she has a negative experience? | top_k helps | category+resource<br>hit=False<br>rank=None<br>shadow=None | category_only<br>hit=False<br>rank=None<br>shadow=None | category+resource<br>hit=True<br>rank=8<br>shadow=None | category+resource<br>hit=True<br>rank=10<br>shadow=None |
| What workshop did Caroline attend recently? | neither helps | category_only<br>hit=True<br>rank=3<br>shadow=1 | category_only<br>hit=True<br>rank=3<br>shadow=1 | category_only<br>hit=True<br>rank=3<br>shadow=1 | category_only<br>hit=True<br>rank=2<br>shadow=1 |

## Per Question

### When did Caroline go to the LGBTQ support group?

- expected_answer: `4 January 2026`
- conclusion: `scoring helps`
- db_evidence: `resource` | anchors=['attended an LGBTQ support group yesterday (2026-01-04)'] | text=The user shared that they attended an LGBTQ support group yesterday (2026-01-04) and described the experience as powerful and impactful. The AI responded with enthusiasm and asked for more details about what made the exp
- target_factor_breakdown: similarity=0.1650, access=0.6931, recency=0.5395, importance=0.9000, total=0.0556
- shadow_top_factor_breakdown: similarity=0.1457, access=0.6931, recency=0.6420, importance=0.9000, total=0.0583
- variants:
  - A: layer=category+resource, hit=False, rank=None, shadow_rank=None, top1=The user joined a new LGBTQ activist group on Tuesday, February 3, 2026.
  - B: layer=category_only, hit=True, rank=4, shadow_rank=3, top1=The user joined a new LGBTQ activist group on Tuesday, February 3, 2026.
  - C: layer=category+resource, hit=False, rank=None, shadow_rank=8, top1=The user joined a new LGBTQ activist group on Tuesday, February 3, 2026.
  - D: layer=category+resource, hit=True, rank=3, shadow_rank=3, top1=The user joined a new LGBTQ activist group on Tuesday, February 3, 2026.

### When did Caroline meet up with her friends, family, and mentors?

- expected_answer: `The week before 20 January 2026`
- conclusion: `neither helps`
- db_evidence: `resource` | anchors=['shared a photo from a meetup with their support circle that took place around January 13, 2026', 'meetup with their support circle that took place around January 13, 2026'] | text=The user expressed deep appreciation for their friends, family, and mentors, describing them as their "rocks" who motivate them and give them strength. They shared a photo from a meetup with their support circle that too
- target_factor_breakdown: similarity=0.1505, access=0.6931, recency=0.5892, importance=0.8000, total=0.0492
- shadow_top_factor_breakdown: similarity=0.1528, access=0.6931, recency=0.6352, importance=0.9000, total=0.0605
- variants:
  - A: layer=category_only, hit=True, rank=1, shadow_rank=5, top1=The user met up with their friends, family, and/or mentors around January 13, 2026 (last week).
  - B: layer=category_only, hit=True, rank=1, shadow_rank=3, top1=The user met up with their friends, family, and/or mentors around January 13, 2026 (last week).
  - C: layer=category+resource, hit=True, rank=1, shadow_rank=5, top1=The user met up with their friends, family, and/or mentors around January 13, 2026 (last week).
  - D: layer=category+resource, hit=True, rank=1, shadow_rank=3, top1=The user met up with their friends, family, and/or mentors around January 13, 2026 (last week).

### How long has Caroline had her current group of friends for?

- expected_answer: `4 years`
- conclusion: `neither helps`
- db_evidence: `category` | anchors=["close group of friends they've known for 4 years", "group of friends they've known for 4 years"] | text=The user has a close group of friends they've known for 4 years, who have been a crucial support system through difficult times.
- variants:
  - A: layer=category_only, hit=True, rank=1, shadow_rank=None, top1=The user has a close group of friends they've known for 4 years, who have been a crucial support system through difficult times.
  - B: layer=category_only, hit=True, rank=1, shadow_rank=None, top1=The user has a close group of friends they've known for 4 years, who have been a crucial support system through difficult times.
  - C: layer=category_only, hit=True, rank=1, shadow_rank=None, top1=The user has a close group of friends they've known for 4 years, who have been a crucial support system through difficult times.
  - D: layer=category_only, hit=True, rank=1, shadow_rank=None, top1=The user has a close group of friends they've known for 4 years, who have been a crucial support system through difficult times.

### Who supports Caroline when she has a negative experience?

- expected_answer: `Her mentors, family, and friends`
- conclusion: `top_k helps`
- db_evidence: `resource` | anchors=['friends, family, and mentors, describing them as their "rocks"'] | text=The user expressed deep appreciation for their friends, family, and mentors, describing them as their "rocks" who motivate them and give them strength. They shared a photo from a meetup with their support circle that too
- target_factor_breakdown: similarity=0.0609, access=0.6931, recency=0.5892, importance=0.8000, total=0.0199
- shadow_top_factor_breakdown: similarity=0.1395, access=0.6931, recency=0.6490, importance=0.8000, total=0.0502
- variants:
  - A: layer=category+resource, hit=False, rank=None, shadow_rank=None, top1=The user has a supportive figure named Melanie who provided meaningful support during their personal journey.
  - B: layer=category_only, hit=False, rank=None, shadow_rank=None, top1=The user has a supportive figure named Melanie who provided meaningful support during their personal journey.
  - C: layer=category+resource, hit=True, rank=8, shadow_rank=None, top1=The user has a supportive figure named Melanie who provided meaningful support during their personal journey.
  - D: layer=category+resource, hit=True, rank=10, shadow_rank=None, top1=The user has a supportive figure named Melanie who provided meaningful support during their personal journey.

### What workshop did Caroline attend recently?

- expected_answer: `LGBTQ+ counseling workshop`
- conclusion: `neither helps`
- db_evidence: `resource` | anchors=['attended an LGBTQ+ counseling workshop on Friday, January 23, 2026', 'LGBTQ+ counseling workshop'] | text=The user, who is transgender, is considering a career path focused on counseling and supporting trans people with self-acceptance and mental health. They attended an LGBTQ+ counseling workshop on Friday, January 23, 2026
- target_factor_breakdown: similarity=0.0840, access=0.6931, recency=0.6157, importance=1.0000, total=0.0359
- shadow_top_factor_breakdown: similarity=0.0840, access=0.6931, recency=0.6157, importance=1.0000, total=0.0359
- variants:
  - A: layer=category_only, hit=True, rank=3, shadow_rank=1, top1=Mel took its kids to a pottery workshop on 2026-01-30 (last Friday); they all made their own pots and found it fun and therapeutic.
  - B: layer=category_only, hit=True, rank=3, shadow_rank=1, top1=Melanie has a spouse (got married recently)
  - C: layer=category_only, hit=True, rank=3, shadow_rank=1, top1=Mel took its kids to a pottery workshop on 2026-01-30 (last Friday); they all made their own pots and found it fun and therapeutic.
  - D: layer=category_only, hit=True, rank=2, shadow_rank=1, top1=Mel took its kids to a pottery workshop on 2026-01-30 (last Friday); they all made their own pots and found it fun and therapeutic.

