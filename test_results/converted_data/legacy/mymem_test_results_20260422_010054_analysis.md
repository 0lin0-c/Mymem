## 1. 总览
- 结果文件: mymem_test_results_20260422_010054.json
- 评测模式: `assistant_eval`
- 题目数: 90
- 回答准确率: 32.22% (29/90)
- adjusted accuracy: 20.31%
- Recall@K: 28.89%
- 存储覆盖率: 100.00%
- 错误题数: 61
- 正确题数: 29
- 统计口径风险:
  - 存在标准答案为空但回答被判正确的样本，主准确率需要结合 adjusted accuracy 解读。

本报告只基于当前 JSON trace 可直接支撑的事实下结论，不额外假设数据库中一定已经存在“强证据”，也不把自动诊断标签直接等同于最终根因。

## 2. 这轮 trace 能直接证明什么
- 90 题中有 61 题回答错误，整体 assistant 侧表现较弱。
- 所有题目的 `storage_hit=True`，说明在 DB 诊断阶段，每题都找到了某种候选相关记忆。
- 有 26 题 `retrieval_hit=True`，其余题目未在 trace 中形成明确 retrieval 命中。
- 23 个答对样本同样 `retrieval_hit=False`，因此这轮结果不能证明检索链路有效。
- 错误高度集中在时间相关题和精确事实定位题：
- Category 1 - 事实回忆（单一事实）: 13 题，正确 2 题，准确率 15.38%
- Category 4 - 偏好态度: 24 题，正确 4 题，准确率 16.67%
- Category 2 - 时间相关（when/how long）: 19 题，正确 4 题，准确率 21.05%

## 3. 失败原因
- retrieval_gap: 41
- answer_or_eval_gap: 20
- 当前 `statistics.answer_failure_patterns` 中，失败样本主要会被标记为 `retrieval_gap`。
- 这个标签在本轮里更适合解读为：
  - 回答层没有拿到足够直接、足够贴近问题核心的检索证据
  - 但不代表每一题都已经高置信证明“数据库里有强证据，只是 retrieval 漏召回了它”
- 更稳妥的总判断是：
  - 这轮 assistant 失败主要表现为“回答层缺少可用证据”
  - 其中一部分样本较像真实检索失配
  - 另一部分样本仍存在候选证据污染，暂时不能把责任完全坐实到 retrieval

### 3.1 较高置信的检索失配样本
- `When did Caroline give a speech at a school?`
  - `top1_context` 是 `Mel's son was involved in an accident around 2026-03-24; the other children were scared but reassured that their brot...`
  - `missed_in_retrieval` 里出现了 `give` 相关关键词
  - 这一题可以较高置信地判断为：回答层没有拿到贴近问题核心的检索证据
- `What career path has Caroline decided to persue?`
  - `top1_context` 是 `User's name is Caro.`
  - `missed_in_retrieval` 里出现了 `career / has` 相关关键词
  - 这一题可以较高置信地判断为：回答层没有拿到贴近问题核心的检索证据
- `Would Caroline still want to pursue counseling as a career if she hadn't received support growing up?`
  - `top1_context` 是 `Melanie deeply values her family as her core support system and rock.`
  - `missed_in_retrieval` 里出现了 `counseling / want` 相关关键词
  - 这一题可以较高置信地判断为：回答层没有拿到贴近问题核心的检索证据

### 3.2 需要保守表述的样本
- `When did Caroline go to the LGBTQ support group?`
- `What is Caroline's relationship status?`
- `When did Caroline give a speech at a school?`
- `When did Caroline meet up with her friends, family, and mentors?`
- `How long has Caroline had her current group of friends for?`

这些题的共同特点是：
- `retrieval_hit=False`
- `top1_context` 往往明显偏题，说明回答层没拿到直接证据
- 但 `db_memories_sample` 或 `missed_in_retrieval` 中，很多候选是由弱关键词触发

因此这些题当前只能写成：
- DB 诊断阶段找到了候选片段
- retrieved top-k 没有把足以支撑标准答案的证据带到回答层
- 但 trace 还不足以高置信证明“强证据已经明确存在且被 retrieval 漏掉了”

### 3.3 路由与回答行为层面的直接现象
- 多个失败样本的 `resolved_layer=category_only`。
  - 这说明系统有时在 category 层就停止了，没有继续进入 resource 层寻找更细粒度证据。
  - 但仅凭当前 trace，还不能单独证明“提前停止”就是唯一根因。
- 多个失败样本的回答表现为保守拒答，或给出邻近但不等价的记忆。
  - 这说明回答层整体更像是在“证据不足时保守作答”，而不是无依据编造。

### 3.4 检索失败类型拆解
- 现有 trace 中，可观察到的失败现象主要有三类：
  - `route_miss_category_only`: 分类层结果不足，但流程停在 category 层
  - `noise_outrank_target`: top1/top-k 被明显弱相关或无关上下文占据
  - `low-confidence retrieval_gap`: DB 候选片段存在，但候选证据受弱关键词污染，不能高置信定性

基于当前失败样本，可按更保守的口径归纳为：
- 较高置信检索失配: 19 题
- category 层提前停止且未拿到可用证据: 5 题
- 候选证据污染、暂不能高置信定性的样本: 36 题

## 4. 成功模式
- 回答成功题数: 29。
- 其中检索命中支撑的成功题数: 6。
- 有 23 题属于“回答正确但 retrieval_hit=False”，这类成功不能直接算作检索有效，更可能来自 profile、prompt 或模型推断。
- 一个典型成功模式是检索直接带回支持证据，例如“When did Caroline pass the adoption interview?”的 Top1/Top2 context 已经贴近标准答案。

## 5. 代表性案例
### 失败案例 1
- question: `When did Caroline give a speech at a school?`
- standard_answer: `The week before 20 January 2026`
- generated_answer: `我没有关于Caroline在学校发表演讲的记录。现有的记忆中没有提到过这件事，可能没有被记录下来，或者是我还没有了解到。你还记得大概是什么时候、在哪个学校吗？可以跟我说说，我帮你记下来。`
- storage_hit=True | retrieval_hit=False | layer=category+resource
- llm_classified_categories: `Timeline`
- top1_context: `Mel's son was involved in an accident around 2026-03-24; the other children were scared but reassured that their brother would be OK`
- 当前 trace 可直接支撑的结论:
  - top1 明显不贴题
  - 回答层没有拿到足够贴近问题核心的检索证据
  - 这题较高置信属于检索失配

### 失败案例 2
- question: `When did Caroline go to the LGBTQ support group?`
- standard_answer: `4 January 2026`
- generated_answer: `根据记录，Caroline 在 **2026年2月3日（星期二）** 加入了一个新的 LGBTQ 活动小组。

不过需要说明的是，记录中提到的是"activist group"（活动/倡导小组），和"support group"（支持小组）可能不完全一样。如果你想确认的是另一个活动，可以再跟我说说细节，我帮你想想。`
- storage_hit=True | retrieval_hit=False | layer=category_only
- llm_classified_categories: `Timeline`
- top1_context: `Mel's son was involved in an accident around 2026-03-24; the other children were scared but reassured that their brother would be OK`
- 当前 trace 可直接支撑的结论:
  - 当前 retrieved 结果不足以支持正确回答
  - top1 更像噪声或邻近记忆，而不是标准答案所需证据
  - 但 `missed_in_retrieval` 里的候选证据受弱关键词影响较大，不能直接下结论说“强证据已明确存在却被 retrieval 漏掉”

### 失败案例 3
- question: `What is Caroline's relationship status?`
- standard_answer: `Single`
- generated_answer: `Based on what I know, I don't have a clear answer about Caroline's relationship status. The memories mention a caring relationship with someone named Melanie (also called Mel),...`
- storage_hit=True | retrieval_hit=False | layer=category+resource
- llm_classified_categories: `Social Graph`
- top1_context: `The user shared a recent negative hiking experience where they encountered religious conservatives who made upsetting remarks, which led...`
- 当前 trace 可直接支撑的结论:
  - resource 层也未能把有效证据带到回答层
  - 当前 trace 只能证明回答层缺少可用证据
  - 若 DB 候选同时受到弱关键词污染，就不能直接把责任完全坐实到 retrieval

### 成功案例 1
- question: `What fields would Caroline be likely to pursue in her educaton?`
- standard_answer: `Psychology, counseling certification`
- generated_answer: `Based on Caroline's interests and activities, she'd likely gravitate toward fields like:

- **Psychology or Counseling** — 心理咨询 is a direct interest of hers, and her involvement...`
- storage_hit=True | retrieval_hit=False | layer=category_only
- llm_classified_categories: `Core Self / Timeline`
- top1_context: `User is hosting/participating in an LGBTQ art show in March 2026`
- 当前 trace 可直接支撑的结论:
  - 最终回答正确
  - 但没有证据表明该正确答案来自有效 retrieval 命中
  - 该样本不能作为检索成功案例

## 6. 建议动作
- 报告口径上，后续不要再把“`storage_hit=True` 且 `retrieval_hit=False`”自动翻译成“数据库里已有强证据但 retrieval 漏召回”。
- 对 assistant_eval，优先区分三种结论：回答层缺少可用证据、较高置信的检索失配、候选证据污染且暂不能高置信定性。
- 对成功样本，单独标注是否为 evidence-backed success，避免把“最终答对”误写成“检索有效”。
- 在代表案例中保留 `resolved_layer`、`llm_classified_categories`、`top1_context` 和 `matched_keyword` 质量提示，减少过度解释空间。