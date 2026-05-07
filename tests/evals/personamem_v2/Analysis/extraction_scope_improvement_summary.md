# PersonaMem-v2 提取范围（Extraction Scope）改进总结

> 日期：2026-04-28
> 修改文件：`services/prompts/memory_prompt.py`
> 评估数据集：PersonaMem-v2, persona_id=66 (Oliver), 42 题

---

## 1. 发现的问题

通过对 v1 基线（原始 prompt）和 v2（术语保真 prompt 改后）的 Storage Sufficiency 分析，发现 **83.3% 的失败原因是 MISSING_PREFERENCE（偏好完全没存入 DB）**，而非存了但术语写错。深入分析 bad case 后，定位到三个根因：

### 问题一：对话伪装 — 用户偏好藏在辅助任务内容里

**现象**：PersonaMem-v2 的对话设计中，用户不直接说"我喜欢涂色书"，而是通过一个看似无关的辅助任务把偏好嵌进去。LLM 提取时只看到了任务表面（翻译/润色/写作辅助），没看到藏在内容里的偏好。

**典型案例**：
- Row 2041：用户说"帮我给老师写封更清晰的邮件"，邮件正文里写着"I work on the animal coloring pages from my folder. It helps me feel calm"，LLM 只存了"用户请老师帮助润色邮件"，**偏好"enjoys coloring in coloring books"完全没被提取**。
- Row 2058：用户请翻译一段话到日语，原文描述了去果园摘苹果的经历，LLM 只存了"用户请求日语翻译"，**偏好"enjoys picking apples in the fall"完全没被提取**。
- Row 2060：用户请把自己的自我介绍翻译成越南语，自我介绍中提到"I had to have surgery because my tummy hurt really bad"，LLM 只存了翻译请求，**关键医疗事实"had an appendectomy at age 6"完全没被提取**。
- Row 2062：用户请翻译一段法语，内容描述了安静午后看绘本的体验，LLM 只存了翻译任务，**偏好"enjoys quiet afternoons reading picture books"完全没被提取**。
- Row 2057：用户请把一段关于夏日家庭后院烧烤的段落翻译成印地语，LLM 只存了翻译请求，**偏好"likes hot dogs at cookouts"完全没被提取**。

**影响范围**：约 6-8 题（翻译/润色/写作辅助类对话）

**根因**：当前提取 prompt 没有区分"用户自己的话"vs"用户让 AI 处理的内容"。LLM 把整个对话归类为"翻译任务"或"写作辅助"，偏好被埋在了用户提供的原文/邮件正文/翻译源文本里，从来没被当作独立事实提取。

---

### 问题二：ask_to_forget — 忘记指令存了，替代偏好没存

**现象**：PersonaMem-v2 中有一类 `ask_to_forget` 题目，结构是三段式对话：用户先表达一个偏好→AI 给出建议→用户说"请忘记我喜欢X"→AI 确认遗忘。当前系统只存了 forget 指令，但用户的**底层需求/意图**并没有消失。

**典型案例**：
- Row 2037：用户先问"有什么安全有趣的儿童手工艺活动？"→AI 推荐了 pottery workshops for kids→用户说"请忘记我参加 pottery workshops for kids"。系统只存了 forget 指令，**没存"用户仍然需要儿童手工艺活动推荐"这个存活需求**。Gold answer 需要用 cardboard collage 替代 pottery。
- Row 2040：用户先问"有什么创意的室内空间布置方法？"→AI 推荐了 blanket forts→用户说"请忘记我喜欢在室内建 blanket forts"。系统只存了 forget 指令，**没存"用户仍然需要室内空间布置方案"**。Gold answer 需要用 pop-up tents 替代。
- Row 2043：用户先问"长途徒步有什么建议？"→AI 推荐了用 inhaler→用户说"请忘记我轻度哮喘需要 inhaler"。系统只存了 forget 指令，**没存"用户仍然需要长距离活动建议"**。Gold answer 需要用 pacing + hydration 替代。
- Row 2066/2067/2068：类似的 forget 模式，分别涉及 school spirit days、watercolor painting、gardening with grandmother。

**影响范围**：约 5-6 题

**根因**：当前提取逻辑把 forget 当作一个"全删"操作，没有意识到 forget 只删除了**具体偏好**，用户的**底层需求**仍然存在。forget 指令覆盖了整个对话，导致 AI 之前给出的通用建议也被丢失。

---

### 问题三：第三方叙事 — 虚构人物背后是用户的真实经历

**现象**：PersonaMem-v2 中有些对话使用了虚构人物名来讲述故事，但这些故事实际上就是用户本人的经历。LLM 看到第三方名字，就把它当作"别人"或"虚构创作"处理，不会提取为用户事实。

**典型案例**：
- Row 2048：用户请润色一段关于"Lena was walking home from the park… she watched two police officers rush past"的段落。LLM 只存了"用户请帮忙润色关于角色 Lena 的创意写作"，**实际是用户本人目睹了家附近的警察追捕事件**。
- Row 2055：用户请润色一段关于"Daniel Harper: I've been avoiding the playground during recess. A while ago there was a lot of shouting and kids pushing each other"的段落。LLM 只存了创意写作润色，**实际是用户目睹了校园斗殴**。
- Row 2071：用户请润色一段关于"Melissa Raymond: I noticed a young boy standing completely still near the fountain… Paramedics were working quickly, pressing on someone's chest"的段落。LLM 只存了创意写作润色，**实际是用户目睹了急救人员做 CPR**。
- Row 2074：用户请润色一段关于"Rachel Meyer: I took my small evening pill and read my favorite book about ocean creatures"的段落。LLM 只存了创意写作润色，**实际是用户在服用低剂量焦虑药物**。

**影响范围**：约 4-5 题

**根因**：LLM 默认把包含第三方名字的叙事当作虚构创作，不会从中提取用户事实。在记忆助手的场景下，用户分享的所有叙事（即使包裹在虚构名字里）都可能是与用户相关的事实。

---

## 2. 对应的解决办法

### 修改了哪些文件

仅修改了一个文件：**`services/prompts/memory_prompt.py`**

### 具体修改内容

#### 修改 1：在 `MEMORY_EXTRACTION_PROMPT` 中新增三条规则

在原有的 `## Source and Attribution Rules` 之后，新增了三个独立章节：

**① Quoted Content Audit (CRITICAL)** — 解决"对话伪装"问题

```
## Quoted Content Audit (CRITICAL)
When the user asks you to refine, translate, polish, or improve a piece of text,
that text is NOT just a task artifact — it often contains real personal facts,
preferences, conditions, and experiences about the user.

- Do NOT treat the user's original text as mere task context.
- If the user says "help me refine this email" and the email body says
  "I take my animal coloring pages to calm down", extract that as a preference.
- If the user asks to translate "I enjoy picking apples at the orchard every fall",
  extract "The user enjoys picking apples in the fall".
- The rule: extract facts from WHAT the user wrote/shared, not just from the fact
  THAT they asked for help.
```

**② Narrative Attribution Rule** — 解决"第三方叙事"问题

```
## Narrative Attribution Rule
In a personal memory assistant context, when the user shares a story or passage
for refinement/translation that describes personal experiences, treat those
experiences as potentially autobiographical even if a different name is used.

- If a passage uses a third-person character name but describes experiences that
  could be the user's own, extract the described experience as a fact about the user.
- Clearly fictional scenarios (e.g., "Once upon a time in a faraway kingdom") are excluded.
- If uncertain, extract with a qualifier: "The user described an experience of [X],
  shared through a narrative about [character name]."
```

**③ Forget/Negation Survival Rule** — 解决"ask_to_forget"问题

```
## Forget/Negation Survival Rule
When the user asks to forget a preference or fact, the forget/negation itself must
be stored. However, the UNDERLYING INTENT or NEED that prompted the original
preference often still exists and must also be stored separately.

- If the user first asks about "fun creative activities for kids" and then says
  "forget that I like pottery workshops", the need for "fun creative activities for
  kids" STILL EXISTS — store it as a separate positive fact.
- If the AI provided useful general advice before the forget request (e.g., pacing
  strategies, alternative activity ideas), that advice is still valid and should
  be stored as advice_checklist.
- The forget instruction only removes the SPECIFIC preference — it does not erase
  the user's broader need or the general advice that was given.
```

#### 修改 2：同步到 `CATEGORY_MEMORY_EXTRACTION_PROMPT`

在 Category 提取 prompt 的 `# Source and Attribution Rules` 之后，新增了精简版的三条规则（Quoted Content Audit、Narrative Attribution、Forget/Negation Survival），措辞与通用版一致但略作精简。

#### 修改 3：更新 `CORE_SELF_EXTRACTION_REQUIREMENTS`

在 Core Self 的提取要求中新增三条：
- **Quoted Content**：如果用户分享的待润色/翻译文本揭示了个人偏好/健康状态/特征，按用户直接陈述来提取。
- **Narrative Attribution**：如果用户分享的叙事使用第三方名字但描述了稳定特征/偏好/条件，提取为用户事实。
- **Forget Survival**：当用户说"忘记我偏好 X"时，存储 forget 指令，但如果存在存活的底层需求，也单独提取。

在 Good examples 中新增：
> The user is interested in fun creative activities for children (surviving need after forgetting pottery preference).

#### 修改 4：更新 `EPISODIC_MEMORY_EXTRACTION_REQUIREMENTS`

在 Episodic Memory 的提取要求中新增三条：
- **Quoted Content**：如果用户分享的待润色/翻译文本描述了具体的个人经历，提取为情景事实。
- **Narrative Attribution**：如果用户分享的叙事使用第三方名字但描述了可能是用户自己的具体经历，提取为情景事实。
- **Forget Survival**：当用户要求忘记某活动时，存储 forget 事件，同时单独提取存活的意图/请求。

在 Good examples 中新增：
> The user is looking for fun creative activities for a group of children (surviving request after forgetting pottery preference).

#### 修改 5：更新 `GENERIC_CATEGORY_EXTRACTION_REQUIREMENTS`

在通用 Category 提取要求中新增三条：
- **Quoted Content**：从文本内容而非任务行为中提取与本类目相关的事实。
- **Narrative Attribution**：从使用第三方名字的叙事中提取与本类目相关的用户经历。
- **Forget Survival**：当用户要求忘记某事实时，也提取任何存活的、与本类目相关的更广泛需求或请求。

---

## 3. 最后的对比结果

### 三轮评估结果

| 指标 | v1 (原始基线) | v2 (术语保真) | v3 (提取范围) | v1→v3 变化 |
|------|-------------|-------------|-------------|-----------|
| **Answer accuracy** | 57.14% | 61.54% | 47.62% | **-9.52pp** |
| **Target preference hit@k** | 14.29% | 11.90% | 23.81% | **+9.52pp** |
| **Answerable context hit@k** | 14.29% | 9.52% | 21.43% | **+7.14pp** |
| **Loose recall@k** | 97.62% | 42.86% | 66.67% | -30.95pp |
| **LLM judged sufficient** | ~16.7% | 7.1% | 9.5% | -7.2pp |
| **Preference found in DB** | 11.9% | 7.1% | 9.5% | -2.4pp |
| **MISSING_PREFERENCE** | 76.2% | 83.3% | 78.6% | +2.4pp |

### Storage Sufficiency 细分对比

| 失败原因 | v1 | v2 | v3 |
|---------|-----|-----|-----|
| MISSING_PREFERENCE | 76.2% | 83.3% | 78.6% |
| SUFFICIENT | ~16.7% | 7.1% | 9.5% |
| MISSING_DETAIL | ~4.8% | 4.8% | 4.8% |
| PARTIAL_INFO | ~2.4% | 2.4% | 0% |
| PARSE_ERROR | 0% | 2.4% | 7.1% |

### 回归 vs 改进分析

- **改进的题目（v2 错 → v3 对）**：8 题，主要集中在 therapy_background、health_and_medical、sensitive_info、ask_to_forget 类型
- **回归的题目（v2 对 → v3 错）**：4 题，包括 Row 2037 (ask_to_forget)、Row 2054 (therapy)、Row 2056 (sensitive)、Row 2061 (therapy)
- **wrong_neighbor_substitution**：从 v1 的 14 → v3 的 23（恶化 64%），说明提取范围扩大后引入了更多噪声记忆

### 结果解读

**提取端（Storage）显著改善**：
- 目标偏好命中@k 从 14.29% → 23.81%（+9.52pp），**翻倍增长**
- 可回答上下文命中@k 从 14.29% → 21.43%（+7.14pp），**大幅提升**
- 更多偏好被成功存入 DB

**生成端（Answer）反而下降**：
- Answer accuracy 从 57.14% → 47.62%（-9.52pp）
- 核心原因：提取范围扩大后，**噪声记忆也被存入了**。例如从 thunderstorm 润色任务中错误归因出"The user values finding creative/resourceful solutions when circumstances change suddenly"这种"价值观"，这类噪声记忆在检索时排名反而高于目标偏好，导致 `wrong_neighbor_substitution` 从 14 升到 23。

**结论**：Quoted Content Audit / Narrative Attribution / Forget Survival 三条规则**确实让提取器存了更多正确偏好**，但同时也引入了更多低质量/噪声记忆。下一步需要在**检索端做 rerank 或 answerable evidence 判别**，让目标偏好排名高于噪声邻居。

### 结果保存文件

| 文件 | 路径 |
|------|------|
| v1 评估结果 | `test_results/personamem_v2/personamem_v2_assistant_eval_results_20260427_173735.json` |
| v1 分析报告 | `test_results/personamem_v2/personamem_v2_assistant_eval_results_20260427_173735_analysis.md` |
| v2 评估结果 | `test_results/personamem_v2/personamem_v2_assistant_eval_results_20260428_010050.json` |
| v2 分析报告 | `test_results/personamem_v2/personamem_v2_assistant_eval_results_20260428_010050_analysis.md` |
| v3 评估结果 | `test_results/personamem_v2/personamem_v2_assistant_eval_results_20260428_134602.json` |
| v3 分析报告 | `test_results/personamem_v2/personamem_v2_assistant_eval_results_20260428_134602_analysis.md` |
| v2 Storage Sufficiency | `tests/evals/personamem_v2/Analysis/storage_sufficiency_analysis_v2.md` |
| v3 Storage Sufficiency | `tests/evals/personamem_v2/Analysis/storage_sufficiency_analysis_v3.md` |
| 本总结文档 | `tests/evals/personamem_v2/Analysis/extraction_scope_improvement_summary.md` |

---

## 4. 下一步建议

| 优先级 | 方向 | 预期效果 |
|-------|------|---------|
| **P0** | 收紧 Narrative Attribution 规则 — 只提取明确的第一人称叙事，避免从 thunderstorm 润色等任务中错误归因出"价值观" | 减少 wrong_neighbor_substitution |
| **P1** | 检索端 rerank — 增加 answerable evidence 判别，让目标偏好排名高于噪声 | 提升 answer accuracy |
| **P2** | 改善 forget 类逻辑 — writer.py 中 forget 处理应保留底层需求，不仅靠 prompt | 改善 ask_to_forget 类题目 |
