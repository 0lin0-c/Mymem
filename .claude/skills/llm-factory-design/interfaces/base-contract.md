
# 接口契约

本文档定义 `BaseLLMProvider` 抽象基类中的所有接口。

定义在 `base.py` 中的标准契约，任何接入系统的大模型都必须严格实现以下核心方法：

---

## 1. generate_chat_response

| 项目 | 说明 |
|-----|------|
| **功能** | 核心对话能力 |
| **输入** | `system_prompt` (str): 系统设定<br>`context` (str): 检索到的记忆上下文<br>`user_query` (str): 用户当前提问 |
| **返回** | `str`: 纯文本回答 |
| **备注** | 底层需处理不同 SDK 对 System Prompt 的位置要求（Claude 是单独参数，OpenAI 是 `role: "system"`） |

---

## 2. get_embedding

| 项目 | 说明 |
|-----|------|
| **功能** | 语义降维能力 |
| **输入** | `text` (str): 需要向量化的文本 |
| **返回** | `List[float]`: 浮点数数组，维度由 `EMBEDDING_DIMENSIONS` 配置决定（默认 1536） |
| **备注** | 专为存入 `resources` 表的 `description_vector` 字段服务 |

> **配置说明**：Embedding 维度可通过 `.env` 中的 `EMBEDDING_DIMENSIONS` 配置，支持不同模型（如 `text-embedding-3-small` 默认 1536 维，`text-embedding-3-large` 支持 3072 维）。

---

## 3. extract_memory_intent

| 项目 | 说明 |
|-----|------|
| **功能** | 后台分析能力 |
| **输入** | `text` (str): 用户最新输入的对话<br>`categories` (List[Dict[str, Any]]): 当前已有的分类列表，每个元素包含 `name` 和 `description`<br>`assistant_response` (str, 可选): AI 回复内容，用于生成回复摘要 |
| **返回** | `Dict`: 包含分类名、摘要、重要性打分的标准 JSON 字典 |
| **备注** | 底层需通过 function calling 或特定 prompt 强制模型输出 JSON |

### 3.1 结构化输出保证

本系统使用 Function Calling（OpenAI）或 Tool Use（Anthropic）强制模型输出结构化 JSON，无需额外的清洗逻辑。

| Provider | 实现方式 |
|----------|----------|
| OpenAI | 使用 `tools` 参数 + `tool_choice` 强制调用 `extract_memory` 函数 |
| Anthropic | 使用 `tools` 参数 + `tool_choice` 强制调用 `extract_memory` 函数 |

> **注意**：由于使用了 Function Calling，模型输出必定是结构化的 JSON，无需 `_clean_json_response` 方法。

---

## 4. count_tokens

不同模型的 Context Window（上下文窗口）不同。如果检索出的记忆上下文过长，直接请求会导致 API 报错。

| 方法 | 功能 |
|------|------|
| `count_tokens(text: str) -> int` | 统计文本的 Token 数量 |

**实现差异**：
| Provider | 实现方式 |
|----------|----------|
| OpenAI | 使用 `tiktoken` 库，按 `cl100k_base` 编码计算 |
| Anthropic | 使用 Claude 官方 Token 计数逻辑 |

**上层调用示例**：
```
max_context_tokens = model_limit - query_tokens - response_reserve
if count_tokens(context) > max_context_tokens:
    context = truncate_by_tokens(context, max_context_tokens)
```

> **设计意图**：让上层业务在发送请求前自动截断过长的记忆，避免 API 报错。

---

## 5. generate_stream_response

为提升前端用户体验（打字机效果），增加流式输出支持。

| 方法 | 功能 |
|------|------|
| `generate_stream_response(...)` | 流式返回对话内容 |

**接口定义**：

| 项目 | 说明 |
|-----|------|
| **输入** | 与 `generate_chat_response` 相同 |
| **返回** | `AsyncGenerator[str, None]`: 异步生成器，每次 yield 一个文本片段 |
| **备注** | 底层通过 SSE (Server-Sent Events) 实现逐字符/逐词推送 |

**FastAPI 路由示例**：
```python
@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    llm: BaseLLMProvider = Depends(get_llm_service),
):
    async def event_generator():
        async for chunk in llm.generate_stream_response(...):
            yield f"data: {chunk}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

---

## 6. 必须实现的接口汇总

| 方法 | 功能 |
|------|------|
| `generate_chat_response` | 核心对话能力 |
| `get_embedding` | 语义向量化 |
| `extract_memory_intent` | 记忆意图提取 |
| `count_tokens` | Token 计数 |
| `generate_stream_response` | 流式输出（可选，基类提供默认实现） |

**设计意图**：给所有模型厂商定规矩——"想进我的系统打工，必须实现这些接口，并且交出的结果格式必须一致"。
