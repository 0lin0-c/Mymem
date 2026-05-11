# PersonaMem-v2 Candidate View Projection Plan

## Summary

第一版目标是验证“同一轮对话生成多个候选视图”是否能改善 PersonaMem-v2 中隐藏个人事实、forget 后存活需求、第三方叙事归属等问题。

本阶段仍然不改变现有 `MemoryWriter -> MemoryRetriever -> ChatOrchestrator` 主链路，不新增数据库表，不替换现有 `personamem_v2` 评估逻辑。candidate views 只在新增的独立实验链路中参与写库，并固定使用 PersonaMem-v2 `persona_id=66` 的题集做验证。

核心变化是：candidate view 不再只是旁路 trace；它会通过测试专用 projection writer 影响最终写入的 `Category`。也就是说：

```text
CandidateView 不是最终落库层
CandidateView -> CandidateCategoryProjection -> Category
Category 仍然使用现有数据库表
```

## Hard Boundaries

- 不修改 `services/memory/writer.py`。
- 不修改 `services/retrieval/retriever.py`。
- 不修改 `services/chat_orchestrator.py`。
- 不修改 `services/llm/*` 或 `services/prompts/*`。
- 不修改或删除原有 `tests/evals/personamem_v2/runner.py`、`models.py`、`reporting.py`、`analysis.py`、`loader.py`。
- 不新增数据库表。
- 不把 `candidate_view=...`、`forget_conflict=...` 等实验元数据写进自然语言输入。
- 不默认写入或 reset 正式 `personamem_v2_persona_66` 用户。
- candidate 实验只写隔离用户，例如 `personamem_v2_persona_66_candidate_views`。

## Input And Output Flow

### 1. 原始输入

输入仍然来自 PersonaMem-v2 的 `PersonaMemQuestion`：

```python
PersonaMemQuestion(
    persona_id="66",
    question="...",
    answer="...",
    preference="...",
    related_conversation_snippet="...",
    row_index=2038,
)
```

### 2. 一轮/一组原始对话生成一个 candidate set

`related_conversation_snippet` 会先被解析为原始 turn：

```text
Turn 1: user_input + assistant_response
Turn 2: user_input + assistant_response
...
```

实验链路按现有 resource 的写入节奏做窗口化：最多 5 个原始 turn 合成一个写入 window。每个 window 保留原始 user/assistant 文本，不注入 candidate 元数据。

```text
原始 turns[0:5] -> PlannedCandidateTurn #1
原始 turns[5:10] -> PlannedCandidateTurn #2
```

candidate 抽取以原始 `PersonaMemQuestion` 为上下文，产出同一个 candidate set。这个 candidate set 代表“这一条样本/这一组原始对话里可被考虑的多个候选视图”，而不是拆成多轮合成对话分别写入。

### 3. Candidate view 协议

候选类型包括：

- `task_event`
- `user_fact`
- `episodic_event`
- `artifact_fact`
- `constraint`
- `surviving_need`
- `advice_checklist`

每个 candidate 至少包含：

- `view_type`
- `content`
- `subject`
- `source_segment`
- `confidence`
- `attribution_risk`
- `sensitivity`
- `forget_conflict`

### 4. Projection 决策

新增测试专用 `CandidateViewWritePolicy` 将 candidate set 投影成 `CandidateCategoryProjection[]`。

示例规则：

- `user_fact` 可以写为 `Core Self` category。
- `surviving_need`、低风险 `episodic_event`、安全 `artifact_fact` 可以写为 episodic category。
- `task_event` 默认跳过，因为它通常只是对话任务外壳。
- `constraint` 默认跳过，避免 forget constraint 被当作可检索记忆污染上下文。
- 高敏感、高归属风险、forget 冲突 candidate 默认跳过。

这里的关键点是：`Category` 不是“直接无条件来自 candidate”；而是 candidate 经过 policy 过滤和投影后，只有 `written` projection 才会生成最终 `Category`。

```text
CandidateView[]
  -> CandidateViewWritePolicy
  -> CandidateCategoryProjection[]
  -> write_decision == written 的 projection
  -> Category
```

### 5. 写库

新增测试专用 `CandidateViewWriter` 负责写入现有三张表：

```text
Resource
Category
ResourceCategory
```

写入逻辑：

- 每个 5-turn window 写 1 条 `Resource`。
- 每个可写 projection 写 1 条 `Category`。
- 每个 `Resource` 和 `Category` 之间写 1 条 `ResourceCategory` 关联。
- `Resource.description_vector` 和 `Category.content_vector` 使用现有 LLM embedding 生成。
- 全部写入隔离 candidate 用户。

### 6. 检索和回答评估

写入完成后，仍然复用原有 `evaluate_sample()`：

```text
candidate DB user
  -> existing evaluate_sample()
  -> existing retrieval / assistant eval path
  -> report + delta
```

因此这个方案已经覆盖“提取后存储到库里，并后续进行检索回答”。区别是写库发生在新增实验模块里，不进入正式主链路。

## Baseline And Safety

- `baseline_results_path` 必填，避免 candidate 实验意外导入或 reset 正式 persona 66 DB。
- baseline 会校验题量和 persona_id。
- candidate 写入失败时默认 fail run，不继续产出看似可信的 delta。
- reuse candidate DB 时报告会标记 provenance warning，因为复用模式没有完整 row-level write trace。

## Output

实验输出独立 JSON/Markdown 报告，包含：

- baseline summary
- candidate structured projection summary
- delta
- candidate projection counts
- candidate write trace
- written/skipped projection reason

报告文件位于：

```text
test_results/personamem_v2_candidate_experiment/
```

## Implementation Scope

新增：

- `tests/evals/personamem_v2/candidate_view_writer.py`

修改 candidate 专用测试/实验模块：

- `tests/evals/personamem_v2/candidate_view_experiment.py`
- `tests/unit/test_personamem_v2_candidate_views.py`

保留不动：

- 原 `personamem_v2` runner/model/reporting/loader/analysis
- 正式 memory writer/retriever/orchestrator 主链路
