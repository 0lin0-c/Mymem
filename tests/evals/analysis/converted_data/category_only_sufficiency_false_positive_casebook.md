# Category-only Sufficiency False Positive Casebook

## 这类问题为什么失败

这类问题的共同链路是：

1. 正确答案其实在数据库里。
2. 检索先进入 `category` 层。
3. `category` top-k 没把正确证据排上来，或者只排上了很弱的近邻证据。
4. `is_sufficient_at_category = true` 过早判定“够用了”。
5. `resource` 兜底检索被跳过。
6. assistant 只能基于错误近邻、局部证据或噪声回答。

因此它不是单纯的“LLM 不会答”，而是：

`Category 检索漏召回 -> Sufficiency 误判足够 -> Resource 兜底被阻断 -> 回答层被错误上下文带偏`

## 失败原因分类

| 编号 | 原因 | 简单解释 |
| --- | --- | --- |
| C1 | `category_miss` | 正确 category 记忆存在，但没有进入最终 top-k。 |
| C2 | `sufficiency_false_positive` | 当前 category 结果只是“像”，但不足以回答；LLM 却判定足够。 |
| C3 | `resource_fallback_blocked` | 因为 category 层被判足够，resource 层没有机会召回更完整证据。 |
| C4 | `wrong_neighbor_substitution` | 回答层使用了同主题但事实错误的近邻记忆。 |
| C5 | `partial_evidence_overtrust` | 只拿到局部相关证据，却被当成完整答案依据。 |
| C6 | `old_db_evidence_underchecked` | 旧分析时对数据库证据状态判断过于保守，后来确认库里有证据。 |

## 历史样本总览

旧基线来源：

- `test_results/converted_data/legacy/mymem_test_results_20260422_010054.json`

当前默认值复验来源：

- `test_results/converted_data/legacy/assistant_5q_readonly_eval_20260422.json`

当前默认值：

- `top_k = 10`
- `similarity_power = 2.0`
- `recency_power = 0.5`

这 5 题在旧基线里属于 `category_only + sufficiency false positive` 风险样本；在当前默认值下，assistant 层复验结果已经是 `5/5` 正确。

## 题目归因表

| 题目 | 标准答案 | 旧失败原因 | 简单解释 | 当前状态 |
| --- | --- | --- | --- | --- |
| `When did Caroline go to the LGBTQ support group?` | `4 January 2026` | C1, C2, C3, C4 | 库里有 `2026-01-04 support group`，但旧 top-k 拿到 `2026-02-03 activist group` 这类错误近邻，resource 兜底又被阻断。 | 已修复，当前回答 `January 4, 2026`。 |
| `When did Caroline meet up with her friends, family, and mentors?` | `The week before 20 January 2026` | C1, C2, C3, C4 | 正确资源里有 `around January 13, 2026` 和 `friends, family, and mentors`，旧检索却被 mentorship/program 近邻带偏。 | 已修复，当前回答 `around January 13, 2026`。 |
| `How long has Caroline had her current group of friends for?` | `4 years` | C1, C2, C3 | 库里有 `close group of friends they've known for 4 years`，旧 category top-k 没拿到关键 `4 years`。 | 已修复，当前回答 `about 4 years`。 |
| `Who supports Caroline when she has a negative experience?` | `Her mentors, family, and friends` | C2, C3, C5 | 旧结果只抓到 `Melanie` 这种单点支持关系，没组合出完整支持网络。 | 已修复，当前回答包含 `mentors, family, and friends`。 |
| `What workshop did Caroline attend recently?` | `LGBTQ+ counseling workshop` | C6, C1, C2 | 旧分析一度怀疑库里证据不足；后来确认 DB 中有 `LGBTQ+ counseling workshop on Friday, January 23, 2026`。 | 已修复，当前回答 `LGBTQ+ counseling workshop`。 |

## 现在怎么使用这份文档

这份文档现在不是“当前仍失败的 5 题列表”，而是一个历史失败模式样本库。

后续如果新改动导致这 5 题重新失败，优先检查：

1. category top-k 是否又把正确证据压下去了。
2. sufficiency 是否又把弱证据判成足够。
3. resource fallback 是否被提前阻断。
4. 回答是否又被同主题错误近邻带偏。
