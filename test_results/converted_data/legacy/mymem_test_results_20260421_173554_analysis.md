## 1. 总览
- 结果文件: `mymem_test_results_20260421_173554.json`
- 评测模式: `assistant_eval`
- 题目数: 10
- 回答准确率: 20.00% (2/10)
- adjusted accuracy: 20.00%
- Recall@K: 0.00%
- 存储覆盖率: 100.00%
- 错误题数: 8
- 正确题数: 2

本报告只基于当前 JSON trace 可直接支撑的事实下结论，不额外假设数据库中一定已经存在“强证据”，也不把自动诊断标签直接等同于最终根因。

## 2. 这轮 trace 能直接证明什么
- 10 题中有 8 题回答错误，整体 assistant 侧表现较弱。
- 所有题目的 `storage_hit=True`，说明在 DB 诊断阶段，每题都找到了某种候选相关记忆。
- 所有题目的 `retrieval_hit=False`，说明没有任何一题在“DB 候选记忆”和“最终 retrieved top-k”之间形成明确命中。
- 2 个答对样本同样 `retrieval_hit=False`，因此这轮结果不能证明检索链路有效。
- 错误高度集中在时间相关题和精确事实定位题：
  - Category 2 - 时间相关（when/how long）: 5 题，正确 0 题，准确率 0.00%
  - Category 1 - 事实回忆（单一事实）: 4 题，正确 1 题，准确率 25.00%
  - Category 3 - 推理归纳（需综合多事实）: 1 题，正确 1 题，但该成功样本不是检索命中支撑型成功

## 3. 失败原因
- 当前 `statistics.answer_failure_patterns` 中，8 个错题都被标记为 `retrieval_gap`。
- 这个标签在本轮里更适合解读为：
  - 回答层没有拿到足够直接、足够贴近问题核心的检索证据
  - 但不代表每一题都已经高置信证明“数据库里有强证据，只是 retrieval 漏召回了它”
- 更稳妥的总判断是：
  - 这轮 assistant 失败主要表现为“回答层缺少可用证据”
  - 其中一部分样本较像真实检索失配
  - 另一部分样本仍存在候选证据污染，暂时不能把责任完全坐实到 retrieval

### 3.1 较高置信的检索失配样本
- `What is Caroline's identity?`
  - `top1_context` 是 `User's name is Caro.`
  - `missed_in_retrieval` 里出现了 `identity / transgender / woman` 相关关键词
  - 这一题可以较高置信地判断为：回答层没有拿到贴近问题核心的检索证据
- `What is Caroline's relationship status?`
  - `top1_context` 指向收养流程相关片段，而不是关系状态
  - `missed_in_retrieval` 里出现了 `relationship / single` 相关关键词
  - 这一题同样更像检索失配，而不是单纯回答层误用已有证据

### 3.2 需要保守表述的样本
- `When did Caroline go to the LGBTQ support group?`
- `When did Caroline give a speech at a school?`
- `When did Caroline meet up with her friends, family, and mentors?`
- `Where did Caroline move from 4 years ago?`
- `How long ago was Caroline's 18th birthday?`

这些题的共同特点是：
- `retrieval_hit=False`
- `top1_context` 往往明显偏题，说明回答层没拿到直接证据
- 但 `db_memories_sample` 或 `missed_in_retrieval` 中，很多候选是由弱关键词触发，例如 `the`、`with`、`how`、`from`

因此这些题当前只能写成：
- DB 诊断阶段找到了候选片段
- retrieved top-k 没有把足以支撑标准答案的证据带到回答层
- 但 trace 还不足以高置信证明“强证据已经明确存在且被 retrieval 漏掉了”

### 3.3 路由与回答行为层面的直接现象
- 多个失败样本的 `resolved_layer=category_only`
  - 这说明系统有时在 category 层就停止了，没有继续进入 resource 层寻找更细粒度证据
  - 但仅凭当前 trace，还不能单独证明“提前停止”就是唯一根因
- 多个失败样本的回答表现为保守拒答，或给出邻近但不等价的记忆
  - 例如把 “support group” 回成 “activist group”
  - 例如明确说“没有这条记录”
- 这说明回答层整体更像是在“证据不足时保守作答”，而不是无依据编造

### 3.4 检索失败类型拆解
- 现有 trace 中，可观察到的失败现象主要有三类：
  - `route_miss_category_only`: 分类层结果不足，但流程停在 category 层
  - `noise_outrank_target`: top1/top-k 被明显弱相关或无关上下文占据
  - `low-confidence retrieval_gap`: DB 候选片段存在，但候选证据受弱关键词污染，不能高置信定性

基于当前 8 个错题，可按更保守的口径归纳为：
- 较高置信检索失配: 2 题
- category 层提前停止且未拿到可用证据: 3 题
- 候选证据污染、暂不能高置信定性的样本: 3 题

## 4. 成功模式
- 最终答对 2 题：
  - `What fields would Caroline be likely to pursue in her educaton?`
  - `What did Caroline research?`
- 这 2 题的共同点是：
  - `is_correct=True`
  - `storage_hit=True`
  - `retrieval_hit=False`
- 因此它们只能被描述为“最终回答正确”，不能被描述为“检索支撑下的成功”。

更准确的说法是：
- 本轮没有出现 `retrieval_hit=True 且 is_correct=True` 的证据支撑型成功样本。
- 当前两个成功样本，更像是模型基于主题先验、persona/profile、弱上下文或常识归纳作出了正确回答。
- 这轮 assistant_eval 不能用来证明 retrieval 已经有效支撑回答。

## 5. 代表性案例
### 失败案例 1
- question: `What is Caroline's identity?`
- standard_answer: `Transgender woman`
- generated_answer: `根据我了解的信息，Caroline 的身份标注为 "other"。`
- storage_hit=True | retrieval_hit=False | layer=category_only
- llm_classified_categories: `Core Self`
- top1_context: `User's name is Caro.`
- 当前 trace 可直接支撑的结论:
  - top1 明显不贴题
  - 回答层没有拿到足够贴近问题核心的检索证据
  - 这题较高置信属于检索失配

### 失败案例 2
- question: `When did Caroline go to the LGBTQ support group?`
- standard_answer: `4 January 2026`
- generated_answer: 回答中表示没有明确记录，并给出了更接近 `activist group` 的替代信息
- storage_hit=True | retrieval_hit=False | layer=category_only
- llm_classified_categories: `Timeline`
- top1_context: `Mel's son was involved in an accident around 2026-03-24...`
- 当前 trace 可直接支撑的结论:
  - category 层返回结果不足以支持正确回答
  - top1 明显更像噪声
  - 但 `missed_in_retrieval` 里的候选证据受弱关键词影响较大，不能直接下结论说“强证据已明确存在却被 retrieval 漏掉”

### 失败案例 3
- question: `Where did Caroline move from 4 years ago?`
- standard_answer: `Sweden`
- generated_answer: 回答表示没有这条信息
- storage_hit=True | retrieval_hit=False | layer=category+resource
- llm_classified_categories: `Timeline`
- top1_context: `Mel's son was involved in an accident around 2026-03-24...`
- 当前 trace 可直接支撑的结论:
  - resource 层也未能把有效证据带到回答层
  - 但 DB 候选里大量命中由 `from` 触发，存在明显弱关键词污染
  - 因此这题只能保守写成“回答层缺少可用证据”，不能直接写成“已确认 retrieval 漏召回强证据”

### 成功案例 1
- question: `What did Caroline research?`
- standard_answer: `Adoption agencies`
- generated_answer: 最终回答与标准答案一致
- storage_hit=True | retrieval_hit=False | layer=category+resource
- 当前 trace 可直接支撑的结论:
  - 最终回答正确
  - 但没有证据表明该正确答案来自有效 retrieval 命中
  - 该样本不能作为检索成功案例

## 6. 建议动作
- 报告口径上，后续不要再把“`storage_hit=True` 且 `retrieval_hit=False`”自动翻译成“数据库里已有强证据但 retrieval 漏召回”。
- 对 assistant_eval，优先区分三种结论：
  - 回答层缺少可用证据
  - 较高置信的检索失配
  - 候选证据污染，暂不能高置信定性
- 对成功样本，单独标注是否为 evidence-backed success，避免把“最终答对”误写成“检索有效”。
- 在代表案例中保留 `resolved_layer`、`llm_classified_categories`、`top1_context` 和 `matched_keyword` 质量提示，减少过度解释空间。
