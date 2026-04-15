# 上下文构建

本文档定义检索流程的最后一步：将检索结果构建为 System Prompt 上下文。

---

## 1. 上下文格式

检索到的记忆作为 **System Prompt 上下文** 供 LLM 回答时参考：

```
[分类名] 记忆内容 (相关性: 0.92)
[分类名] 记忆内容 (相关性: 0.85)
```

---

## 2. Token 控制

使用 `llm.count_tokens()` 控制上下文总长度，超出 `max_tokens` 时截断。

---

## 3. System Prompt 结构

```
# 用户画像
{user_prompt_template}

# AI 人设
{agent_persona_template}

# 相关记忆（供参考）
{retrieved_context}

---

请根据以上信息回答用户的问题。
```
