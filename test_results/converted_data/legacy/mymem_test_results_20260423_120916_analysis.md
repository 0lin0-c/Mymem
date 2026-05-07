## 1. 总览
- 结果文件: mymem_test_results_20260423_120916.json
- 评测模式: `assistant_eval`
- 题目数: 23
- 回答准确率: 52.17% (12/23)
- adjusted accuracy: 36.36%
- Recall@K: 43.48%
- 存储覆盖率: 100.00%
- 错误题数: 11
- 正确题数: 12
- 统计口径风险:
  - 存在标准答案为空但回答被判正确的样本，主准确率需要结合 adjusted accuracy 解读。
  - 错误样本没有 db_diagnosis，无法严格区分 storage/retrieval/generation 责任。

本报告只基于当前 JSON trace 可直接支撑的事实下结论，不额外假设数据库中一定已经存在“强证据”，也不把自动诊断标签直接等同于最终根因。

## 2. 这轮 trace 能直接证明什么
- 23 题中有 11 题回答错误，整体 assistant 侧表现较弱。
- 所有题目的 `storage_hit=True`，说明在 DB 诊断阶段，每题都找到了某种候选相关记忆。
- 有 10 题 `retrieval_hit=True`，其余题目未在 trace 中形成明确 retrieval 命中。
- 3 个答对样本属于 `profile_inference`，可视为画像推断成功，但不等同于直接事实召回。
- 8 个答对样本属于 `empty_gold`，主要说明回答保守，不应作为事实检索成功。
- 错误高度集中在时间相关题和精确事实定位题：
- Category 4 - 偏好态度: 3 题，正确 0 题，准确率 0.00%
- Category 2 - 时间相关（when/how long）: 3 题，正确 1 题，准确率 33.33%
- Category 1 - 事实回忆（单一事实）: 2 题，正确 1 题，准确率 50.00%

## 3. 失败原因
- retrieval_gap: 7
- answer_or_eval_gap: 4
- 当前 `statistics.answer_failure_patterns` 中，失败样本主要会被标记为 `retrieval_gap`。
- 这个标签在本轮里更适合解读为：
  - 回答层没有拿到足够直接、足够贴近问题核心的检索证据
  - 但不代表每一题都已经高置信证明“数据库里有强证据，只是 retrieval 漏召回了它”
- 更稳妥的总判断是：
  - 这轮 assistant 失败主要表现为“回答层缺少可用证据”
  - 其中一部分样本较像真实检索失配
  - 另一部分样本仍存在候选证据污染，暂时不能把责任完全坐实到 retrieval

### 3.1 较高置信的检索失配样本
- `What was the poetry reading that Caroline attended about?`
  - `top1_context` 是 `Melanie has a spouse (got married recently)`
  - `missed_in_retrieval` 里出现了 `attended / about / people / shared` 相关关键词
  - 这一题可以较高置信地判断为：回答层没有拿到贴近问题核心的检索证据
- `When is Caroline going to the transgender conference?`
  - `top1_context` 是 `The user plans to attend a transgender conference in January 2026.`
  - `missed_in_retrieval` 里出现了 `transgender / caroline / going` 相关关键词
  - 这一题可以较高置信地判断为：回答层没有拿到贴近问题核心的检索证据
- `What did Caroline and her family do while camping?`
  - `top1_context` 是 `Mel recently went on a family camping trip involving nature exploration, campfire marshmallow roasting, and a hike.`
  - `missed_in_retrieval` 里出现了 `family / caroline` 相关关键词
  - 这一题可以较高置信地判断为：回答层没有拿到贴近问题核心的检索证据

### 3.2 需要保守表述的样本
- 当前没有明显需要降级为保守表述的样本。

### 3.3 路由与回答行为层面的直接现象
- 多个失败样本的回答表现为保守拒答，或给出邻近但不等价的记忆。
  - 这说明回答层整体更像是在“证据不足时保守作答”，而不是无依据编造。

### 3.4 检索失败类型拆解
- 现有 trace 中，可观察到的失败现象主要有三类：
  - `route_miss_category_only`: 分类层结果不足，但流程停在 category 层
  - `noise_outrank_target`: top1/top-k 被明显弱相关或无关上下文占据
  - `low-confidence retrieval_gap`: DB 候选片段存在，但候选证据受弱关键词污染，不能高置信定性

基于当前失败样本，可按更保守的口径归纳为：
- 较高置信检索失配: 3 题
- category 层提前停止且未拿到可用证据: 0 题
- 候选证据污染、暂不能高置信定性的样本: 0 题

## 4. 成功模式
- 回答成功题数: 12。
- 回答支持类型分布: empty_gold=8, profile_inference=3, direct_fact=1。
- 有 3 题属于 profile-supported inference；这类题可以算答对，但应和直接事实召回分开。
- 有 8 题属于 empty gold 保守成功，分析价值较低。
- 一个典型成功模式是检索直接带回支持证据，例如“What fields would Caroline be likely to pursue in her educaton?”的 Top1/Top2 context 已经贴近标准答案。

## 5. 代表性案例
### 失败案例 1
- question: `What was the poetry reading that Caroline attended about?`
- standard_answer: `It was a transgender poetry reading where transgender people shared their stories.`
- generated_answer: `I don't have any memory of a poetry reading that Caroline attended. Nothing in what I recall mentions one — it's possible I just didn't hear about it, or maybe it hasn't come up...`
- storage_hit=True | retrieval_hit=False | layer=category+resource
- llm_classified_categories: `Social Graph / Timeline`
- top1_context: `Melanie has a spouse (got married recently)`
- 当前 trace 可直接支撑的结论:
  - top1 明显不贴题
  - 回答层没有拿到足够贴近问题核心的检索证据
  - 这题较高置信属于检索失配

### 失败案例 3
- question: `What did Caroline research?`
- standard_answer: `Adoption agencies`
- generated_answer: `Based on what I know, I don't have any specific information about research you've done. The memories I have mention you gained exposure to various therapeutic methods for workin...`
- storage_hit=True | retrieval_hit=False | layer=category+resource
- llm_classified_categories: `Knowledge Base / Social Graph`
- top1_context: `Melanie has a spouse (got married recently)`
- 当前 trace 可直接支撑的结论:
  - resource 层也未能把有效证据带到回答层
  - 当前 trace 只能证明回答层缺少可用证据
  - 若 DB 候选同时受到弱关键词污染，就不能直接把责任完全坐实到 retrieval

### 成功案例 1
- question: `What fields would Caroline be likely to pursue in her educaton?`
- standard_answer: `Psychology, counseling certification`
- generated_answer: `Based on what I know about Caroline, she'd most likely pursue fields related to:

- **Psychology / Mental Health Counseling** — She's been exploring this as a career direction a...`
- storage_hit=True | retrieval_hit=True | layer=category_only
- llm_classified_categories: `Core Self`
- top1_context: `User is exploring counseling or mental health work as a career direction, acknowledging it is tough but rewarding`
- 当前 trace 可直接支撑的结论:
  - 最终回答正确
  - trace 中存在 retrieval 命中，因此这题更接近 evidence-backed success

## 6. 建议动作
- 报告口径上，后续不要再把“`storage_hit=True` 且 `retrieval_hit=False`”自动翻译成“数据库里已有强证据但 retrieval 漏召回”。
- 对 assistant_eval，优先区分三种结论：回答层缺少可用证据、较高置信的检索失配、候选证据污染且暂不能高置信定性。
- 对成功样本，单独标注是否为 evidence-backed success，避免把“最终答对”误写成“检索有效”。
- 在代表案例中保留 `resolved_layer`、`llm_classified_categories`、`top1_context` 和 `matched_keyword` 质量提示，减少过度解释空间。