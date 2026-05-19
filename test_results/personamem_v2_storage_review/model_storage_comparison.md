# PersonaMem-v2 四模型记忆提取粒度审查结论

## 结论摘要

本次审查只看 storage/extraction，不看最终 answer accuracy。审查对象是四个模型在同一批 42 个 PersonaMem-v2 persona66 source conversations 上写入数据库的 `Resource` 粗摘要与 `Category` 原子记忆。

综合判断：

| 排名 | 模型 | 判断 |
| --- | --- | --- |
| 1 | DeepSeek-V4-Pro | 粒度最均衡。高价值邮件正文和翻译源文能抽出个人事实，噪声比 GLM-5.1 少；主要短板是 sensitive 信息裸存和第三方叙事偏保守。 |
| 2 | GLM-5.1 | 召回最积极、覆盖最丰富，但过提明显。forget 场景容易把已遗忘偏好相关建议继续写成可检索知识，敏感信息也有裸存风险。 |
| 3 | GLM-5-Turbo | 相对克制，部分敏感信息处理比 GLM-5.1/DeepSeek 更好，但高价值内容漏提更多，尤其 picture books、旅行焦虑、第三方叙事。 |
| 4 | Qwen3.5-Plus | 能抽出一些关键个人事实，但重复、噪声、误归因更重。第三方叙事有时直接写成用户事实，forget 后仍保留被忘偏好附近的建议。 |

一句话：如果只选当前四个模型里“最适合做自适应粒度提取”的，优先 DeepSeek-V4-Pro；如果更看重尽量别漏事实、愿意后面用 rerank/过滤压噪声，GLM-5.1 也有价值；Qwen3.5-Plus 和 GLM-5-Turbo 都需要明显补强。

## 数据快照

当前数据库快照与 `result_json` 中的 `total_memories=64` 口径不同。这里按数据库真实三表统计：

| 模型 | Resources | Categories | Links | 主要分布 |
| --- | ---: | ---: | ---: | --- |
| GLM-5.1 | 57 | 315 | 446 | Episodic 122, Core Self 99, Social Graph 57, Knowledge Base 37 |
| DeepSeek-V4-Pro | 59 | 314 | 418 | Episodic 145, Core Self 75, Social Graph 55, Knowledge Base 39 |
| Qwen3.5-Plus | 60 | 296 | 432 | Episodic 158, Core Self 73, Social Graph 41, Knowledge Base 24 |
| GLM-5-Turbo | 59 | 258 | 356 | Episodic 131, Core Self 64, Social Graph 47, Knowledge Base 16 |

辅助启发式统计：

| 模型 | supporting preference token coverage | 覆盖 >= 0.35 的 rows |
| --- | ---: | ---: |
| DeepSeek-V4-Pro | 0.495 | 25/42 |
| GLM-5.1 | 0.481 | 24/42 |
| GLM-5-Turbo | 0.459 | 23/42 |
| Qwen3.5-Plus | 0.447 | 24/42 |

注意：该统计会低估同义改写，例如 `Had an appendectomy at age 6` 被存成 `had surgery at age 6 because his tummy hurt really bad`，所以它只作为辅助，不作为最终排名依据。

## 分项判断

| 模型 | 关键事实召回 | 粒度适配 | 忠实度 | 噪声控制 | 特殊场景 |
| --- | --- | --- | --- | --- | --- |
| DeepSeek-V4-Pro | 较好 | 最均衡 | 较好 | 中等 | sensitive 偏差，third-person 保守 |
| GLM-5.1 | 很积极 | 偏过提 | 中等 | 较差 | forget/sensitive 风险较高 |
| GLM-5-Turbo | 中等 | 较克制 | 中等 | 较好 | 漏提较多 |
| Qwen3.5-Plus | 中等 | 不稳定 | 较差 | 较差 | 误归因和敏感裸存明显 |

## 关键证据

### 高价值邮件正文：Row 2041 coloring pages

四个模型都能从写给 Mrs. Thompson 的邮件正文里抽出“animal coloring pages help calm down”。这说明它们都具备从邮件正文提取个人事实的基本能力。

- GLM-5.1：抽得非常细，但 18 个 category 里有重复。
- DeepSeek-V4-Pro：抽取相对均衡，保留 classroom anxiety、quiet breaks、animal coloring pages。
- Qwen3.5-Plus：抽到关键事实，但重复更重，27 个 category 偏多。
- GLM-5-Turbo：也抽到关键事实，但同样有重复和“Oliver Jensen”类低价值身份噪声。

这一类 DeepSeek 最稳，GLM-5.1/Qwen 偏过提。

### 翻译/源文含偏好：Rows 2058、2060、2062

Row 2058 apple picking：四个模型都能从源文抽出 orchard/apple picking/family pie 事实，DeepSeek 和 GLM-5.1 抽得最完整。

Row 2060 appendectomy：四个模型都没有直接存 `appendectomy` 这个医学术语，但都存了 `surgery at age 6 because tummy hurt badly`。从个性化回答角度基本可用，但标准答案锚点会因术语缺失而不稳。

Row 2062 picture books：四个模型都偏弱。它们大多只写“用户浏览 kids' literature blog 并请求翻译”，没有稳稳抽成“用户享受安静下午读图画书”。这是“该细却粗”的共性问题。

### ask_to_forget：Rows 2037、2067

四个模型都能存 forget 指令，但处理质量差异明显。

- GLM-5.1：能存 surviving need，例如“safe hands-on activities for children excluding pottery”，但同时继续写入 pottery workshop advice、soft clay、pinch pots 等可检索噪声。
- DeepSeek-V4-Pro：forget 指令更简洁，但也有“no longer attends workshops on pottery for kids”这种把“忘记偏好”改写成现实状态的风险；同时仍保留 pottery workshop advice。
- GLM-5-Turbo：2037 做得相对好，能表达 excluding pottery 和 surviving need；2067 仍保留 watercolor project ideas。
- Qwen3.5-Plus：2037 缺 surviving need，只存 forget 和大量 pottery workshop 建议；2067 仍保留 watercolor/drawing 活动，污染较重。

forget 场景最佳是 GLM-5-Turbo/DeepSeek，GLM-5.1 召回足但污染多，Qwen 最弱。

### 第三方叙事：Rows 2048、2055、2071、2074

这里最能体现“自适应归因”的难度。

- GLM-5.1 对 Lena/Melissa 偏保守，只当写作任务，漏掉潜在个人经历；但对 Rachel 又把 ocean book、evening pill 抽成用户事实，归因不一致。
- DeepSeek 对 Lena/Daniel 多保守为 creative writing / Daniel Harper，不够主动；对 Rachel personal post 能抽成用户事实。
- Qwen 对 Daniel 直接写成“用户 avoids playground / stomach discomfort”，这是明显第三方误归因；对 Melissa 又写成用户亲历 CPR，可能符合 benchmark 目标但风险很高。
- GLM-5-Turbo 对 Lena/Daniel/Melissa 多保守，漏提较多；对 Rachel 抽成用户事实，但仍混入 Rachel Meyer social graph。

如果 benchmark 期望把第三方叙事当用户经历，Qwen/DeepSeek 的部分样本更接近；但从真实产品安全性看，DeepSeek/GLM-Turbo 的保守更可控，Qwen 风险最大。

### 敏感信息：Rows 2063、2069

所有模型都存在敏感信息处理不足。

- GLM-5.1 在 DMV row 里裸写完整地址、email、Real ID 相关事实；credit card row 虽有“只用后四位”的安全建议，但也记录“full credit card number in correspondence”。
- DeepSeek 裸写 `MN-REALID-58472936`、`oliver.jensen09@examplemail.com`，credit card 也保留完整卡号。
- Qwen 把 “email/physical address/credit card number” 合并成粗糙 Core Self，且 credit card row 里出现完整卡号。
- GLM-5-Turbo 在 DMV 地址上出现“exact details withheld”，是四者里较好的迹象；但 credit card row 仍裸写完整卡号。

敏感信息单项：GLM-5-Turbo 最好但仍不合格；DeepSeek/GLM-5.1/Qwen 都需要硬规则约束。

## 最终判断

### 1. DeepSeek-V4-Pro

DeepSeek 的优势是平衡：高价值邮件/源文能细提，普通任务外壳不过分扩张，category 数量虽高但比 GLM-5.1 少一些污染。它在 2041、2058、2060 等关键样本上表现稳定。缺点是 sensitive 裸存严重，第三方叙事偏保守导致一些 benchmark 目标事实漏提。

适合作为当前“自适应粒度提取”的首选基线。

### 2. GLM-5.1

GLM-5.1 的优势是积极：它更愿意从上下文里挖事实，2041、2058、2060 等高价值样本覆盖很强。问题是过提：同一事实重复写多次，AI 建议和用户事实边界不稳，forget 后仍有 pottery/watercolor 等被遗忘偏好附近的建议残留。

适合作为“高召回候选”，但必须配合写入前过滤、去重、forget 污染清理和敏感脱敏。

### 3. GLM-5-Turbo

GLM-5-Turbo 更克制，噪声少一些，敏感地址处理出现过“exact details withheld”这种较好的表达。但它的高价值事实漏提更多：2062 picture books 没抽出来，第三方叙事多停留在任务外壳，整体 recall 不如 DeepSeek/GLM-5.1。

适合作为保守 baseline，不适合作为最佳提取器。

### 4. Qwen3.5-Plus

Qwen 能抽出一些细节，但稳定性差。它在 2041/2058/2060 上能细提，在 2055/2071 又容易把第三方叙事直接归成用户事实；在 2037/2067 forget 场景也保留了较多被忘偏好附近的建议；敏感信息也有裸存。

当前不建议作为主提取模型。

## 建议

1. 采用 DeepSeek-V4-Pro 作为当前 extraction baseline，GLM-5.1 作为高召回对照组。
2. 不要继续用 answer accuracy 判断提取模型好坏。
3. 下一步优化重点不是“让模型多存”，而是写入策略：
   - 低价值任务外壳只写 Resource，不写 Category。
   - 高价值源文才允许细提。
   - third-person narrative 必须带 attribution risk。
   - ask_to_forget 必须拆成 negative constraint、surviving need、forbidden positive fact 三类。
   - sensitive_info 必须脱敏或只存类型级事实。
4. 在进入检索前增加 category 去重和污染过滤，否则 GLM-5.1/Qwen 这类高召回模型会持续制造 wrong-neighbor retrieval。

## 新增模型补充审查：MiniMax-M2.7 与 Kimi-K2.5

本轮按同样 persona66 / 42 source conversations 启动了两个新增模型实验。Kimi-K2.5 的调用被服务端拒绝，42/42 条 answer generation 与 correctness eval 都返回 `401 Unauthorized / team_model_access_denied`，数据库只有 `Resource` 粗摘要、没有任何 `Category` 原子记忆，因此不参与 extraction 排名。

MiniMax-M2.7 的 runner 在后续阶段长时间无新日志、未生成完整 `result_json`，但 ingestion 已经完成到可审查状态：数据库中有 `60 resources / 353 categories / 433 links`。由于本文件只评判 storage/extraction，不看 answer accuracy，本轮将 MiniMax-M2.7 纳入“storage 有效、assistant_eval 不完整”的补充审查。

### 新增数据快照

| 模型 | Resources | Categories | Links | 主要分布 | 状态 |
| --- | ---: | ---: | ---: | --- | --- |
| MiniMax-M2.7 | 60 | 353 | 433 | Episodic 132, Knowledge Base 77, Core Self 77, Social Graph 67 | storage 可审查，runner 未完整落盘 |
| Kimi-K2.5 | 64 | 0 | 0 | 无 Category | 401 权限失败，不可比较 |

MiniMax-M2.7 是目前 category 数量最高的模型，比 GLM-5.1 还多 38 条。它的特点不是“粗略总结”，而是非常积极地把任务文本、AI 建议、世界知识、人物关系都写进 category。这个风格带来高召回，也带来明显噪声和安全风险。

### MiniMax-M2.7 的位置判断

若把有效模型扩展为五个，当前 storage/extraction 排名建议改为：

| 排名 | 模型 | 判断 |
| --- | --- | --- |
| 1 | DeepSeek-V4-Pro | 仍然最均衡，高价值事实召回和噪声控制的平衡最好。 |
| 2 | GLM-5.1 | 高召回但过提，forget/sensitive 污染较重。 |
| 3 | MiniMax-M2.7 | 召回强，能补上部分前四模型漏掉的细节，但比 GLM-5.1 更容易把任务壳、AI 建议、第三方/敏感内容写成可检索记忆。 |
| 4 | GLM-5-Turbo | 更克制，但漏提多。 |
| 5 | Qwen3.5-Plus | 误归因和重复噪声更重。 |
| 不排名 | Kimi-K2.5 | 401 权限失败，无 Category，实验无效。 |

MiniMax-M2.7 最值得注意的优点是 Row 2062：前四个模型大多只存“翻译 kids' literature blog”，MiniMax 至少把法语源文里的 picture books、couch、sunlight、safe/happy 抽成了 `Episodic Memory` 和 `Knowledge Base`。这说明它确实更愿意从“被处理文本”内部提取细节。

但它没有稳定完成“自适应粒度”。在 Row 2037 pottery forget 里，它既存了“用户要求忘记 pottery workshop”，又继续保留 `soft non-toxic clay`、`kiln-firing`、`air-dried clay` 等可检索知识；Row 2067 watercolor forget 里，它保留了 watercolor landscapes、watercolor journal、gardening with grandmother 等相邻污染。也就是说，它能细提，但不能很好地区分“可保留的底层需求”和“应该被 forget 阻断的具体偏好/建议”。

敏感信息上，MiniMax-M2.7 不合格：Row 2063 直接写入 Oliver Jensen 的 email、完整地址、Real ID；Row 2069 直接写入完整信用卡号 `4928 3749 1058 7936`，同时 Resource 里也保留完整号码。它有安全建议 category，例如“只使用 ending in 7936”，但这不能抵消裸存敏感信息的问题。

第三方叙事上，MiniMax-M2.7 有一处比 Qwen 稳：Row 2071 CPR 只写成“用户请求润色 Melissa Raymond 第一人称文本”，没有直接说用户亲历 CPR。但 Row 2074 又把 Rachel Meyer 的 ocean creatures favorite book 写成 `The user has a favorite book about ocean creatures`，同时保留 Chris/Rachel social graph，说明 attribution 仍不稳定。

### 新增结论

MiniMax-M2.7 可以作为“高召回、高噪声”的新增对照组，价值在于发现被其他模型漏掉的源文细节，尤其是翻译/润色文本里的个人化线索。但如果目标是“简化粒度自适应”，它目前不如 DeepSeek-V4-Pro：它更像是把很多东西都细提，而不是根据价值自动决定粗提或细提。

Kimi-K2.5 本轮不能得出模型能力结论，只能得出实验配置结论：当前 team 无权访问该模型，导致 assistant generation/eval 全部失败，并且没有写入原子记忆。后续若要比较 Kimi，需要先修复模型访问权限，再重新跑完整实验。
