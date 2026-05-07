# Unsupported Success Casebook

## 这类问题为什么危险？
这类样本最初的现象是 `is_correct=true` 但 `retrieval_hit=false`。
也就是说，答案表面上答对了，但 trace 不能证明它是靠正确证据答对的。

现在分析时应优先看 `answer_support_type`：

| 类型 | 含义 | 该怎么理解 |
| --- | --- | --- |
| `direct_fact` | 检索直接带回能回答标准答案的事实 | 真正的 evidence-backed success |
| `profile_inference` | 靠画像/长期偏好推断答对 | 可以算答对，但不等于直接事实召回 |
| `empty_gold` | 标准答案为空，assistant 保守说不知道 | 说明拒答边界，不说明事实检索成功 |
| `unsupported` | 答对了，但证据链仍不闭合 | 还需要继续查 |
| `wrong` | 当前回答没答对 | 未修复 |

## 本轮重测来源

- 原始 QA：`data/converted_data_recent_2026q1_name_trimmed/sample_0_qa.json`
- 上一轮 23 题结果：`test_results/converted_data/legacy/mymem_test_results_20260423_120916.json`
- 本轮 23 题结果：`test_results/converted_data/legacy/mymem_test_results_20260424_113537.json`
- 7 题 DB 只读诊断：`test_results/converted_data/legacy/nonempty_gold_7q_db_rank_diagnosis_20260423.json`
- 运行方式：真实 Caroline 数据库 + `--converted-retrieval-only`

上一轮 23 题结果：

- `12/23` 答对
- `11/23` 未答对
- `direct_fact=1`
- `profile_inference=3`
- `empty_gold=8`
- `wrong=11`

## 2026-04-24 Prompt + Top-k 实验更新

在上一版 casebook 基础上，又做了一轮只读 assistant_eval 回归：

- 新 prompt：更强调 factual question 不要过窄分类，主分类后补 1-2 个 fallback 分类
- 默认 `top_k`：从 `10` 提升到 `15`
- 运行方式：真实 Caroline 数据库 + `--converted-retrieval-only`
- 结果文件：`test_results/converted_data/legacy/mymem_test_results_20260424_113537.json`

本轮结果：

- `11/23` 答对
- 相比上一轮 `12/23`，没有净提升，反而新增 1 道回归
- 因此，这轮实验说明：继续把 classification prompt 写得更细，并不能稳定提升最终 assistant 表现

## 这轮更新后的总体判断

大多数未答对题的根因与上一版 casebook 保持一致，仍主要落在以下几类：

- 正确证据在 DB 中，但没有稳定进入最终 top-k
- 命中了相关主题证据，但不是能直接回答 gold 的正确证据
- DB 摘要本身缺失、漂移，或与 gold 时间口径冲突
- empty-gold 题的保守拒答边界不稳定

与上一版相比，这一轮最重要的变化只有两点：

1. `What did Caroline research?` 的失败链路应更新为 `route instability + threshold filtering`
2. 新增 1 道 empty-gold 回归题：`What did Caroline realize after her charity race?`

## 已答对题目

| 题目 | 标准答案 | 当前支持类型 | 简单说明 |
| --- | --- | --- | --- |
| `What fields would Caroline be likely to pursue in her educaton?` | `Psychology, counseling certification` | `profile_inference` | 主要靠 counseling / mental health career direction 这类画像证据支撑 |
| `When did Caroline join a new activist group?` | `The Tuesday before 8 February 2026` | `direct_fact` | 当前最扎实的一题，直接召回 `February 3, 2026` |
| `What is Caroline's identity?` | `Transgender woman` | `profile_inference` | 仍主要是画像推断，不是 direct fact |
| `What would Caroline's political leaning likely be?` | `Liberal` | `profile_inference` | `likely` 问句，允许画像推断 |
| `What are the new shoes that Caroline got used for?` | `(empty)` | `empty_gold` | 空 gold 下保守拒答 |
| `What is Caroline's reason for getting into running?` | `(empty)` | `empty_gold` | 空 gold 下保守拒答 |
| `Which classical musicians does Caroline enjoy listening to?` | `(empty)` | `empty_gold` | 空 gold 下保守拒答 |
| `What setback did Caroline face recently?` | `(empty)` | `empty_gold` | 空 gold 下保守拒答 |
| `What was grandpa's gift to Caroline?` | `(empty)` | `empty_gold` | 空 gold 下保守拒答 |
| `What did Caroline and her family see during their camping trip last year?` | `(empty)` | `empty_gold` | 识别到 camping 更像 Mel 的经历，因此保守 |
| `What precautionary sign did Caroline see at the café?` | `(empty)` | `empty_gold` | 空 gold 下保守拒答 |

## 新增回归题

| 题目 | 上一轮 | 这一轮 | 说明 |
| --- | --- | --- | --- |
| `What did Caroline realize after her charity race?` | `correct` | `wrong` | empty-gold 题，原本保守拒答稳定；本轮 prompt/top-k 调整后出现边界回退 |

这说明本轮实验不仅没有净提升，还对 empty-gold 保守拒答题产生了副作用。

## 仍未答对题目

| 题目 | 标准答案 | retrieval_hit | 主要问题 |
| --- | --- | --- | --- |
| `What did Caroline research?` | `Adoption agencies` | `false` | 正确 evidence 在 DB 里；本轮更准确的主因是 `route instability + threshold filtering`，不是 assistant misuse |
| `What advice does Caroline give for getting started with adoption?` | `Do research, find an adoption agency or lawyer, gather necessary documents, and prepare emotionally.` | `true` | 命中了 adoption 相关证据，但不是 checklist 本身，更像存储摘要缺失 |
| `What was the poetry reading that Caroline attended about?` | `It was a transgender poetry reading where transgender people shared their stories.` | `false` | 原始对话有明确答案，但 DB 里没有对应摘要 |
| `Did Caroline make the black and white bowl in the photo?` | `No` | `false` | 正确 evidence 在 DB 里，而且全库 rank 很高，但被错误分类范围挡掉 |
| `When is Caroline going to the transgender conference?` | `February 2026` | `false` | 当前库里的主导证据偏向 `January 2026`，和 gold 冲突 |
| `When did Caroline attend a pride parade in August?` | `The Friday before 20 February 2026` | `true` | 命中的是 January pride 相关摘要，不是正确 February 事件 |
| `What does Caroline's drawing symbolize for her?` | `Freedom and being true to herself.` | `true` | 命中的只是 painting/name 泛证据，不是 symbol 本身 |
| `What did Caroline and her family do while camping?` | `(empty)` | `false` | 空 gold 题，但回答仍被 camping 相关噪声带偏 |
| `What does Caroline say running has been great for?` | `(empty)` | `true` | 空 gold 题，但回答给出了额外内容 |
| `How did Caroline feel about her family after the accident?` | `(empty)` | `true` | 空 gold 题，主体/语境处理仍不稳定 |
| `What does Caroline love most about camping with her family?` | `(empty)` | `true` | 空 gold 题，仍展开了 Mel camping 内容 |

## 7 道非空 Gold Miss 的 DB 诊断小表

| 题目 | DB 中是否存在可支撑证据 | 当前诊断 | 关键信号 |
| --- | --- | --- | --- |
| `What did Caroline research?` | 存在 | 正确证据仍被过滤，但这轮应补充“分类不稳定” | 正式 run 中 `llm_classified_categories = ["Timeline"]`；在 `Timeline` 的 resource 内部，正确 evidence `researching adoption agencies` 排 `rank=2`，但 `score≈0.0172 < 0.03`，在 category+resource 合并后的最终过滤阶段被删除，因此 assistant 没有看到正确 evidence |
| `What advice does Caroline give for getting started with adoption?` | 当前未找到 | 更像存储抽取缺失 | 原始对话 `D17:7` 有完整 checklist，但 DB 中查不到 `lawyer / references / medical checks / prepare emotionally` 这类摘要 |
| `What was the poetry reading that Caroline attended about?` | 当前未找到 | 更像存储抽取缺失 | 原始对话 `D17:19` 很明确，但 DB 中查不到 `poetry reading / shared their stories / identities` 这类摘要 |
| `Did Caroline make the black and white bowl in the photo?` | 存在 | 分类范围错误导致 evidence 被挡掉 | 直接 resource 全库 `rank=1`，category 全库 `rank=2`，但当前被路由错范围，pottery/photo 证据没进搜索范围 |
| `When is Caroline going to the transgender conference?` | 存在，但与 gold 冲突 | 更像存储摘要/时间归一化冲突 | DB 里最强证据是 `plans to attend ... in January 2026`；另有一条 `attended LGBTQ conference around February 2, 2026`，不是单纯没召回，而是库内时间事实冲突 |
| `When did Caroline attend a pride parade in August?` | 存在相关证据，但时间漂移 | 错误事件/错误时间替代 | 当前命中的都是 January pride 摘要；宽松 DB probe 也主要只看到 January / late January 版本，没有稳定保住 `2026-02-13` |
| `What does Caroline's drawing symbolize for her?` | 当前未找到 | 更像存储抽取缺失 | 原始对话 `D17:23` 有 `freedom / true to myself / embrace my womanhood`，但 DB 中查不到这些摘要；当前 `retrieval_hit=true` 只是命中了 name/painting 泛证据 |

## 对这轮 Prompt 实验的结论

这轮更强约束的 classification prompt + `top_k=15` 带来了局部正向信号：

- 只读 probe 中，`What did Caroline research?` 有时能从单一 `Knowledge Base` 扩成 `Knowledge Base + Timeline`
- 在 `Timeline` 路由下，正确 resource `researching adoption agencies` 已能进入 resource 内部 `rank=2`

但正式 assistant_eval 结果表明，这种 prompt 调整没有稳定转化成最终回答提升：

- 正式 run 中，这题仍可能只落到 `Timeline`
- 即使正确 resource 进入 routed resource top rank，也仍会在最终阈值过滤阶段被删除
- 总体分数从 `12/23` 下降到 `11/23`

因此，这轮实验的结论是：

- prompt wording 不是当前主瓶颈
- 后续不应继续主要依赖“把分类 prompt 写得更细”来救 bad cases

## 下一步优先方向

1. 先修 `What did Caroline research?` 这类“正确 evidence 已经进 routed resource top rank，但最终被阈值过滤”的题
2. 再修 `black and white bowl` 这类“分类范围错了，直接把正确 evidence 挡掉”的题
3. 对 `adoption advice / poetry reading / drawing symbol` 这三题，要回到存储抽取链路，而不是只调检索
4. 对 `transgender conference / pride parade` 这类时间题，要单独查时间归一化和摘要漂移
