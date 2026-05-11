# PersonaMem-v2 Candidate View Structured Projection Comparison - persona 66

- eval_mode: assistant_eval
- top_k: 10
- projection_mode: candidate_structured_db_writes

## Delta
- storage_hits_delta: 0
- non_forget_storage_hits_delta: 0
- forget_safe_delta: 0
- retrieval_hits_delta: -18
- correct_answers_delta: 1
- total_memories_delta: -22
- errors_delta: 0
- total_questions: 42

## Baseline
- total_questions: 42
- total_memories: 64
- storage_hits: 42
- non_forget_storage_hits: 35
- forget_total: 7
- forget_safe: 0
- retrieval_hits: 28
- correct_answers: 20
- errors: 0

## Candidate Structured Projection
- total_questions: 42
- total_memories: 42
- storage_hits: 42
- non_forget_storage_hits: 35
- forget_total: 7
- forget_safe: 0
- retrieval_hits: 10
- correct_answers: 21
- errors: 0

## Candidate Projection
- original_turn_count: 42
- candidate_count: 104
- written_candidate_count: 46
- skipped_candidate_count: 58
- written_artifact_fact: 8
- written_episodic_event: 5
- written_surviving_need: 7
- written_user_fact: 26
- skipped_assistant_advice_not_user_memory: 11
- skipped_constraint_is_policy_not_retrievable_memory: 8
- skipped_forget_conflict: 2
- skipped_high_sensitivity: 3
- skipped_task_event_is_conversation_wrapper: 34
