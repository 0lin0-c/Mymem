## 1. 总览
- 结果文件: mymem_test_results_20260428_165238.json
- 题目数: 1
- Recall@K: 100.00%
- Top1/Top3/Top5: 0.00% / 100.00% / 100.00%
- 命中检索题数: 1
- 漏召回题数: 0
- 统计口径风险: 当前结果里没有额外高风险提示。

## 2. 失败原因
- 没有 retrieval_hit=False 的失败样本。

### 检索失败类型拆解
- 当前没有可拆解的 retrieval failure 样本。

## 3. 成功模式
- 成功召回题数: 1。
- 其中 Top1 直接命中的题数: 0。
- 这些题通常表现为 retrieved_contexts 前几条就已经包含答案核心事实，后续回答层更容易答对。

## 4. 代表性案例
- 案例1: When did Caroline go to the LGBTQ support group?
  - category: Category 2 - 时间相关（when/how long）
  - standard_answer: 7 May 2023
  - storage_hit=True | retrieval_hit=True | rank=3 | layer=category+resource
  - answer_support_type: direct_fact
  - diagnosis: none
  - top1_context: User has a dedicated dynamic category "Emotional Wellness Journey" for related memories
  - reason: 检索结果里已经带回了支持答案的上下文，回答大概率是在使用检索证据。

## 5. 建议动作
- P0: 对 retrieval_hit=False 的题，对比 missed evidence 和 Top1 噪声，定位是召回缺失还是排序压制。
- P0: 输出 similarity / importance / recency 分项分数，确认是哪个因子把目标 evidence 压下去了。
- P1: 按 resolved_layer 统计 recall 差异，确认 category_only 是否过早截断了 resource 检索。