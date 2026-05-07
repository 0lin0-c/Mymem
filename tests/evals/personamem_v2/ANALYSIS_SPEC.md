# PersonaMem-v2 Analysis Specification

This document defines the analysis contract for the PersonaMem-v2 harness.
It exists because PersonaMem-v2 cannot be judged safely by loose
`retrieval_hit` / `recall@k` alone.

The harness must continue to use the real project chain:

- Import/write path: `MemoryWriter`
- Retrieval path: `MemoryRetriever`
- Assistant answer path: `ChatOrchestrator`

Test-owned code may load dataset rows, compute oracle metrics, write reports,
and diagnose failures. It must not replace product storage, retrieval, or chat
business logic.

## Why Loose Recall Is Not Enough

`retrieval_hit_loose` means that a DB candidate related to the expected answer
appeared somewhere in retrieved top-k. It does not guarantee that the retrieved
context can answer the question.

PersonaMem-v2 has cases where a broad related memory is retrieved but the
target evidence is missing. For example:

- Target preference: `Had an appendectomy at age 6`
- Question: whether intense core workouts need precautions
- Wrong retrieved top1: a forgotten asthma preference

That is a health-related hit, but not an answerable hit. Reports must therefore
separate broad related recall from target-evidence recall.

## Required Per-Question Fields

Each PersonaMem-v2 `qa_result` should include the fields below in addition to
the existing common fields.

### Existing Dataset Fields

- `persona_id`
- `source_split`
- `row_index`
- `pref_type`
- `updated`
- `who`
- `correct_answer`
- `incorrect_answers`
- `supporting_preference`
- `related_conversation_snippet`

### Retrieval Evidence Fields

- `retrieval_hit_loose`: bool
  - Existing broad hit semantics. This should preserve historical
    comparability with `retrieval_hit`.
- `loose_rank_position`: int or null
  - Existing broad first-hit rank.
- `target_preference_hit`: bool
  - Whether `supporting_preference` is explicitly represented in retrieved
    context.
- `target_preference_rank`: int or null
  - First rank where the supporting preference is clearly represented.
- `target_snippet_hit`: bool
  - Whether the answer-bearing fact from `related_conversation_snippet` is
    represented in retrieved context.
- `target_snippet_rank`: int or null
  - First rank where snippet-derived target evidence is represented.
- `target_answer_anchor_hit`: bool
  - Whether a context contains the key anchors needed to support
    `correct_answer`.
- `target_answer_anchor_rank`: int or null
  - First rank where answer anchors are represented.
- `answerable_context_hit`: bool
  - Whether the retrieved context is sufficient to answer the gold answer
    directly, not merely topically related.
- `answerable_context_rank`: int or null
  - First rank at which the context becomes answerable.
- `target_evidence_source`: string
  - One of: `preference`, `snippet`, `persona_profile`, `answer_anchor`,
    `mixed`, `unknown`.

## Hit Definitions

### `retrieval_hit_loose`

Broad compatibility metric. A hit may be counted when a DB candidate related to
the expected answer appears in top-k.

This field is useful for old comparisons, but it must not be used alone to
claim the system retrieved answerable evidence.

### `target_preference_hit@k`

Whether `supporting_preference` is clearly present in the first k retrieved
contexts.

Examples:

- Preference: `Had an appendectomy at age 6`
  - Hit: a context explicitly mentions appendectomy or equivalent surgery
    detail plus age 6.
  - Not hit: a context mentions a different health condition such as asthma.
- Preference: `Do not remember 'Enjoys gardening with his grandmother'`
  - Hit: a context explicitly represents the forget/retraction of gardening
    with grandmother.
  - Not hit: a context merely mentions grandmother or nature activities.

### `target_snippet_hit@k`

Whether answer-bearing facts from `related_conversation_snippet` appear in the
first k retrieved contexts.

This should be used when the preference is too abstract, negative, or does not
contain the replacement answer.

### `target_answer_anchor_hit@k`

Whether the first k contexts contain facts that can directly support the gold
answer.

Examples:

- Gold answer requires `cardboard cut-outs` and `community collage`.
  - A pottery memory alone is not a hit.
- Gold answer requires `MFA` and `secure payment gateway`.
  - A generic sensitive-info warning is only partial.

### `answerable_context_hit@k`

Whether the retrieved context is enough for a reasonable assistant to answer
the question correctly without guessing.

This is stricter than all other retrieval metrics. It should be false for:

- Same-domain but wrong evidence
- Same-emotion but wrong event
- Negative constraint only, where the replacement answer is missing
- Partial evidence that omits a required gold detail

## Answer Support Types

PersonaMem-v2 should reuse the converted-data support-type idea, but extend it
for preference and snippet evidence.

Allowed values:

- `direct_preference`
  - The answer is supported by the target `supporting_preference`.
- `direct_snippet`
  - The answer is supported by a retrieved conversation snippet fact.
- `answer_anchor`
  - The answer is supported by explicit answer-bearing anchors, even if the
    exact preference string is not present.
- `persona_profile_inference`
  - The answer is plausible from onboarding/profile context, but not directly
    supported by target PersonaMem evidence.
- `partial_context`
  - The retrieved context supports part of the answer but misses key details.
- `negative_constraint_only`
  - A forget/update/retraction constraint is present, but the replacement
    answer is not.
- `unsupported`
  - The answer is correct but the retrieved trace does not explain why.
- `wrong`
  - The answer is wrong.
- `unknown`
  - The report cannot classify the support.

## Retrieval Failure Subtypes

Reports should classify failed or suspicious cases with these labels.

- `preference_not_stored`
  - The supporting preference cannot be found in stored memories.
- `snippet_not_stored`
  - The answer-bearing snippet detail was not stored or summarized.
- `target_evidence_not_retrieved`
  - Target evidence exists in storage but did not enter top-k.
- `loose_hit_false_positive`
  - `retrieval_hit_loose=true`, but target evidence is absent.
- `wrong_neighbor_substitution`
  - Retrieved context is same topic/emotion/domain but the wrong fact.
- `noise_outrank_target`
  - Target evidence exists but lower-ranked noise dominates the answer context.
- `negative_constraint_only`
  - Forget/update evidence is present, but no replacement answer is available.
- `generation_missed_key_detail`
  - Answerable context exists, but the assistant omitted required details.
- `distractor_answer_leak`
  - The generated answer matches or moves toward an `incorrect_answers` option.
- `sensitive_policy_gap`
  - Sensitive-info answer fails to redact/mask or misses required security
    guidance.
- `eval_oracle_strictness`
  - The generated answer is reasonable but the gold answer requires very
    specific details.

## Required Aggregate Metrics

PersonaMem-v2 reports should include:

- `loose_recall_at_k`
- `target_preference_hit_at_1`
- `target_preference_hit_at_3`
- `target_preference_hit_at_5`
- `target_preference_hit_at_k`
- `target_snippet_hit_at_k`
- `target_answer_anchor_hit_at_k`
- `answerable_context_hit_at_k`
- `loose_vs_answerable_gap`
  - `loose_recall_at_k - answerable_context_hit_at_k`
- `answer_support_type_counts`
- `retrieval_failure_subtype_counts`
- `distractor_answer_leak_count`

Each metric should also be broken down by:

- `pref_type`
- `updated`
- `who`
- retrieval layer / strategy, when available

## Required Markdown Report Sections

Generated analysis Markdown should include these sections:

1. `Overall Summary`
   - Answer accuracy, loose recall, target-evidence hit, answerable-context
     hit.
2. `Loose Recall vs Answerable Evidence`
   - Explicitly warn when loose recall is high but target evidence hit is low.
3. `Target Evidence Top-K Analysis`
   - Rank distributions for preference, snippet, and answer anchors.
4. `Answer Support Types`
   - Counts and representative examples for each support type.
5. `False-Positive Retrieval Hits`
   - Cases where `retrieval_hit_loose=true` but `answerable_context_hit=false`.
6. `Top1/Top3 But Wrong`
   - Cases where a broad hit is ranked highly but is not the target evidence.
7. `PersonaMem-Specific Risks`
   - Forget/update handling, sensitive-info handling, incorrect-answer leaks,
     and persona/profile overreach.
8. `Representative Bad Cases`
   - Include question, gold answer, generated answer, supporting preference,
     top contexts, and diagnosis subtype.
9. `Recommended Next Actions`
   - Separate storage extraction fixes, retrieval ranking fixes, context
     formatting fixes, and generation prompt fixes.

## Reporting Rules

- Do not describe `retrieval_hit_loose=true` as proof that the correct evidence
  was retrieved.
- Do not count a same-domain memory as answerable unless it contains the target
  preference, snippet fact, or answer anchor.
- Do not treat a negative constraint as sufficient when the gold answer requires
  a replacement recommendation.
- Keep `retrieval_hit_loose` for comparability, but make
  `answerable_context_hit` the primary diagnostic metric for PersonaMem-v2.
- Always include representative false positives when loose recall and answer
  accuracy diverge.

## Implementation Notes

The first implementation can use deterministic matching:

- normalized substring matching for concise preferences
- token-overlap matching for longer snippets
- manually derived or LLM-derived answer anchors stored in the report trace

If LLM-based classification is added later, it should be an optional diagnostic
oracle, not part of the production retrieval or answer path.

