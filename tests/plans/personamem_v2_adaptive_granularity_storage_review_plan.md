# PersonaMem-v2 四模型记忆提取粒度自适应审查方案

## 核心问题

我们不问“模型答对了多少”，而问：

> 给定同一批 42 个 PersonaMem-v2 source conversations，模型写入数据库的 `resources` 粗粒度摘要和 `categories` 原子记忆，是否能根据内容价值自动选择合适粒度？

也就是：

- 对无关/低价值邮件：是否只保留粗略任务摘要，避免塞一堆噪声原子记忆？
- 对有个性化价值的邮件正文、翻译源文、润色段落：是否能抽出关键个人事实？
- 对敏感信息、forget、第三方叙事：是否既不过度遗忘，也不过度误归因？
- 粗摘要 `Resource.description` 和细粒度 `Category.content` 是否互补，而不是互相重复或互相污染？

## 已有材料

当前可用材料是：

- `tests/test.json`：四模型横向索引和结果路径。
- 四个 `result_json`：包含每题 `retrieved_contexts`、supporting preference、snippet、retrieval/answer stage，但不包含完整数据库快照。
- 当前数据库：需要按 `user_id` / `username` 直接查询每个模型写入的 `resources`、`categories`、`resource_categories`。
- 规范层面，项目设计正好支持这个拆分：`resources` 是对话级粗摘要，`categories` 是原子化记忆，`resource_categories` 负责来源追踪。

四个用户隔离键：

| 模型 | username | user_id |
| --- | --- | --- |
| GLM-5.1 | `GLM-5.1-persona66` | `fc20e640-320d-4ef3-a06a-4f9d5e1913e4` |
| DeepSeek-V4-Pro | `DeepSeek-V4-Pro-persona66` | `c54634b7-bf63-4da9-a2c4-aaf2261545a9` |
| Qwen3.5-Plus | `Qwen3.5-Plus-persona66` | `624da605-a9e3-4832-ae8c-f883f59a62a7` |
| GLM-5-Turbo | `GLM-5-Turbo-persona66` | `02481aa6-272a-419f-9a79-5c6bdae1ea44` |

## 对比单位

每个模型都按同一套 42 个 source conversation 审查。每个 source conversation 拆成三层判断：

| 层 | 看什么 | 目的 |
| --- | --- | --- |
| Source | 原始邮件/润色/翻译/forget 对话 | 判断这条内容本来该粗提还是细提 |
| Resource | `resources.description` / `raw_content` | 看粗摘要是否保留任务背景和关键上下文 |
| Category | `categories.content` / `category_name` | 看是否抽出了必要的个性化原子事实 |

重点不是“总共 64 条 memory”这种数量，而是“该细的有没有细，该粗的有没有克制”。

## 样本分桶

先把 42 题按内容价值分成几类：

| 桶 | 例子 | 理想行为 |
| --- | --- | --- |
| 低个性化价值邮件 | 普通措辞润色、泛化任务请求 | 只存粗摘要，少建或不建 category |
| 高个性化价值邮件正文 | 邮件里藏着 coloring pages、car accident、nightmares | Resource 概括任务，Category 抽出个人事实 |
| 翻译/润色源文含偏好 | apple picking、picture books、hot dogs、appendectomy | 必须从“被处理文本”里抽事实 |
| 第三方叙事 | Lena/Daniel/Rachel 等叙事 | 谨慎抽取，最好带“不确定/用户描述”限定 |
| ask_to_forget | pottery、blanket fort、asthma、watercolor | 存 negative constraint，同时保留 surviving need |
| 敏感信息 | DMV、email、Real ID、credit card | 需要识别但避免不必要暴露，安全类记忆要适度 |

这个分桶直接对应“自适应粒度”：不同桶应有不同存储策略。

## 评分维度

给每个模型打 6 个主分，每项 0-5：

| 指标 | 问题 |
| --- | --- |
| 1. 关键事实召回 | 高价值内容里的个人事实是否被抽出来？ |
| 2. 粒度适配 | 高价值内容是否细提，低价值内容是否粗提？ |
| 3. 事实忠实度 | 有没有把 AI 建议、虚构角色、泛化价值观误当用户事实？ |
| 4. 噪声控制 | 是否生成太多同话题但不可作答的 category？ |
| 5. 来源可追踪 | category 是否能追到正确 resource/source，而不是孤立漂浮？ |
| 6. 特殊场景处理 | forget、敏感信息、第三方叙事是否处理得当？ |

再算几个辅助指标：

- `High-value extraction recall`：高价值 source 中应抽事实的命中率。
- `Low-value over-extraction rate`：低价值 source 中不该细提却细提的比例。
- `Noise-to-signal ratio`：无用/错误 category ÷ 有用 category。
- `Granularity Adaptivity Score`：高价值细提得分 - 低价值过提惩罚。
- `Misattribution count`：把第三方/AI/泛化建议误归给用户的次数。
- `Forget compliance score`：是否只忘具体偏好，同时保留底层需求。
- `Sensitive handling score`：是否避免把敏感号码裸存成可随意召回的偏好。

## 审查流程

1. 从四个 `result_json` 提取 42 个 source rows、问题、gold preference、snippet、`retrieved_contexts`。
2. 按四个 `user_id` 查询数据库里的 `resources`、`categories`、`resource_categories`。
3. 用 `raw_content` / `source_raw_content` / 文本 overlap 把 DB memory 对齐回 42 个 source conversation。
4. 对每个 source 先标注“理想粒度”：`skip` / `coarse_only` / `coarse_plus_atomic` / `fine_atomic` / `negative_constraint` / `sensitive_guarded`。
5. 再审查每个模型实际写入：

   - Resource 是否充分但不啰嗦；
   - Category 是否必要、准确、可复用；
   - 是否有遗漏、噪声、幻觉、误归因。

6. 每个模型输出一张 per-row 评分表和一个 casebook。
7. 最终排名只基于 storage/extraction，不看最终 answer accuracy。

## 预期输出

建议最后产出：

- `model_storage_comparison.md`：四模型总排名和证据。
- `per_model_memory_dump.json`：四模型 DB 快照，包含 resources/categories/links。
- `adaptive_granularity_matrix.csv`：42 rows × 4 models 的评分矩阵。
- `casebook.md`：每类典型好/坏案例，比如“该粗却细”“该细却粗”“第三方误归因”“forget 处理正确”。

## 注意点

- `accuracy` 只能作为背景，不参与提取质量排名。
- `loose_recall` 只能说明召回了相关或相邻记忆，不能证明提取得好。
- `storage_coverage=100%` 不能直接说明完整存储，只说明能粗略匹配到某些 DB 记录。
- 最终结论必须来自数据库里的 `Resource` / `Category` 内容和 row-level case evidence。
