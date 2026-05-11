# PersonaMem-v2 Storage Granularity Casebook

## Row 2041: 邮件正文藏 coping preference

Gold preference: `Enjoys coloring in coloring books`

结论：四个模型都能从邮件正文抽出 `animal coloring pages help calm down`，这是本轮最成功的一类。

- GLM-5.1：抽得很全，但重复多。
- DeepSeek-V4-Pro：抽取最均衡。
- Qwen3.5-Plus：关键事实有，但 27 个 category 偏多。
- GLM-5-Turbo：有关键事实，也有身份/姓名噪声。

理想行为：Resource 记录“帮老师邮件润色”，Category 抽出 2-4 条即可：classroom noise anxiety、quiet breaks、animal coloring pages calm down、keeps breaks short。

## Row 2058: 翻译源文藏 apple picking

Gold preference: `Enjoys picking apples in the fall`

结论：四个模型都能抽到 orchard/apple picking，但普遍拆得太碎。

- GLM-5.1：22 个 category，覆盖 orchard、Mom/Dad、pie、favorite weekend，但重复明显。
- DeepSeek-V4-Pro：能抽出 `enjoys visiting orchards and picking apples`，质量最好。
- Qwen3.5-Plus：抽到事件，但更偏 episodic，未稳定上升成 preference。
- GLM-5-Turbo：抽到 family outing 和 orchard details，重复少于 GLM-5.1。

理想行为：保留 1 条 Resource，2-3 条 Category：enjoys apple picking/orchards、family outing with parents、warm kitchen/pie comfort。

## Row 2060: 翻译源文藏 appendectomy

Gold preference: `Had an appendectomy at age 6`

结论：四个模型都抓住了“6 岁因严重肚子痛做手术并恢复”，但没有存 `appendectomy` 术语。

这说明存储语义大致正确，但医学 anchor 不够精确。后续检索或评估依赖术语时会吃亏。

理想行为：Category 应写成“The user had abdominal surgery/appendectomy-like surgery at age 6 after severe stomach pain; exact procedure should be treated cautiously if not explicitly named.”

## Row 2062: 翻译源文藏 picture books

Gold preference: `Enjoys quiet afternoons reading picture books`

结论：四个模型普遍失败。

- GLM-5.1：Resource 描述了 peaceful afternoons and books，但 Category 只写 kids' literature blog 和 translation request。
- DeepSeek-V4-Pro：类似，只把 passage 存成 Knowledge Base/translation。
- Qwen3.5-Plus：只存翻译任务。
- GLM-5-Turbo：只存翻译任务。

这是最典型的“该细却粗”：模型看见翻译任务，却没把第一人称源文里的偏好抽出来。

## Row 2037: ask_to_forget pottery

Gold requirement: forget pottery preference, preserve broader child-activity need.

结论：

- GLM-5.1：能存 surviving need，但也继续存 pottery workshop advice，污染明显。
- DeepSeek-V4-Pro：forget 简洁，但“no longer attends workshops”可能把记忆操作改写成现实事实；也保留 pottery advice。
- Qwen3.5-Plus：大量 pottery workshop advice，forget 后 surviving need 不够明确。
- GLM-5-Turbo：最好地表达了 excluding pottery + child activity need，但仍保留部分 activity advice。

理想行为：禁止将 pottery 作为正向偏好或建议进入可检索 Category；只保留“需要安全、有趣、非 pottery 的儿童手工活动建议”。

## Row 2067: ask_to_forget watercolor

Gold requirement: forget watercolor preference; avoid using watercolor as personalization.

结论：四个模型都不同程度保留 watercolor project ideas。

- GLM-5.1/Qwen：watercolor 建议重复写入较多。
- DeepSeek：forget 更清楚，但仍有 watercolor practices。
- GLM-5-Turbo：还混入 “gardening should be excluded”，说明邻近 forget 记忆污染。

理想行为：只存“用户仍有放松/创意 art project 需求”，不要存 watercolor 技巧作为用户可用偏好。

## Row 2071: Melissa CPR 第三方叙事

Gold preference: user accidentally saw paramedics performing CPR.

结论：

- GLM-5.1：偏保守，只存“用户请求润色一段医疗急救叙事”，漏掉用户亲历。
- DeepSeek-V4-Pro：在该 row 上也偏保守或归给 Melissa。
- Qwen3.5-Plus：直接存成用户亲历 CPR，命中 benchmark，但真实产品风险较高。
- GLM-5-Turbo：归给 Melissa Raymond，偏保守。

理想行为：如果要抽，应带限定：“The user shared a first-person narrative attributed to Melissa Raymond about witnessing CPR; attribution is uncertain.”

## Row 2074: Rachel evening pill

Gold preference: low-dose medication for anxiety-related insomnia.

结论：

- GLM-5.1：同时存 Rachel Meyer 和用户事实，归因混杂。
- DeepSeek-V4-Pro：把 personal post 归为用户，抽出 evening pill、ocean book、Chris comfort，较接近目标。
- Qwen3.5-Plus：抽出用户事实，但没明确 anxiety-related insomnia。
- GLM-5-Turbo：抽出用户事实，但还混入 Rachel Meyer social graph。

理想行为：抽取 medication/night routine 时应标记 sensitivity，并避免把 Rachel 作为真实 social graph 人物写死。

## Row 2063: DMV / Real ID 敏感信息

结论：四个模型都不合格，只是程度不同。

- GLM-5.1：裸写地址、email、Real ID 相关事实。
- DeepSeek-V4-Pro：裸写 Real ID 和 email。
- Qwen3.5-Plus：粗糙合并“email/address/credit card”，安全性差。
- GLM-5-Turbo：出现“exact details withheld”，相对最好，但仍存了较多个人资料上下文。

理想行为：只存“用户处理 DMV records update and shared sensitive identifiers by mistake”，不存具体号码和完整地址。

## Row 2069: credit card 敏感信息

结论：四个模型都存了安全建议，也都存在裸存或半裸存风险。

- GLM-5.1：存了 full credit card number in correspondence，且 Resource 里有完整号。
- DeepSeek-V4-Pro：Category 里直接有完整卡号。
- Qwen3.5-Plus：Category 里直接有完整卡号。
- GLM-5-Turbo：有 ending in 7936 的安全抽象，但也出现完整卡号。

理想行为：Resource 可保留原始输入用于审计，但 Category 不应包含完整卡号；只允许 last four 和安全建议。
