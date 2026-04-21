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
system_prompt:
  assistant rules
  profile/persona
  memory-use priority rules

context:
  # Recent Conversation
  ...

  # Retrieved Memories
  ...

user_query:
  current user message only
```

`user_query` 必须只包含当前用户消息，不把 recent conversation 或 retrieved memories 拼进去。

## 4. ChatOrchestrator Trace

`ChatOrchestrator.build_context()` 可以返回 trace，供测试、评估和开发者调试使用。普通 `/v1/chat` 默认不暴露 trace。

| 字段 | 说明 |
|------|------|
| `retrieved_results` | `MemoryRetriever.retrieve()` 原始结果 |
| `retrieved_context` | 格式化后的检索上下文 |
| `recent_context` | 最近 pending conversation 上下文 |
| `context` | 最终传给 LLM 的 context |
