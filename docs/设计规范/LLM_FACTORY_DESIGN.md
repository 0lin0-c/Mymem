# 🤖 大模型中枢服务层 (LLM Factory) 设计说明书

## 1. 模块需求概述

本模块的核心目标是在 `services/llm/` 目录下构建一个**高内聚、低耦合**的大模型调用中枢。

系统目前需要接入 OpenAI（或兼容其 SDK 格式的厂商，如 DeepSeek、阿里百炼等）以及 Anthropic (Claude)。由于各家大模型的官方 SDK 在参数结构、系统提示词传入方式、异步调用方法上存在巨大差异，本模块必须抹平这些底层差异，为上层业务逻辑提供一套标准、统一、类型安全的 Python 调用接口。

---

## 2. 核心架构与设计哲学

| 设计原则 | 说明 |
|---------|------|
| **依赖倒置原则** | 上层业务代码绝对不允许直接 `import openai` 或 `import anthropic`，只依赖于抽象基类（契约）。保证未来厂商 SDK 破坏性更新或接入新模型时，核心业务代码无需修改。 |
| **简单工厂模式** | 根据 `.env` 中的 `LLM_PROVIDER` 配置，由工厂类动态实例化对应的模型提供商对象，注入到 FastAPI 请求上下文。 |
| **强制异步** | 所有对外方法必须使用 `async/await`，确保等待外部 API 响应时，FastAPI 主事件循环仍能处理其他并发请求。 |
| **结构化输出约束** | 底层适配器负责引导并校验模型返回严谨的 JSON 结构（如记忆分类提取、重要性打分），而非发散的自然语言。 |

---

## 3. 代码目录拓扑

```
Mymem/
└── services/
    └── llm/
        ├── __init__.py          # [包声明] 暴露对外的核心类
        ├── base.py              # [接口契约] BaseLLMProvider 抽象基类
        ├── openai_sdk.py        # [适配器] OpenAI 及兼容标准 (DeepSeek 等)
        ├── anthropic_sdk.py     # [适配器] Claude 独立 API 结构
        ├── factory.py           # [总调度] 读取配置并分发适配器
        └── tools.py             # [工具层] Prompt 构建、Tool 定义、向量计算
```

---

## 4. 核心接口与标准协议

定义在 `base.py` 中的标准契约，任何接入系统的大模型都必须严格实现以下核心方法：

### 4.1 `generate_chat_response`

| 项目 | 说明 |
|-----|------|
| **功能** | 核心对话能力 |
| **输入** | `system_prompt` (str): 系统设定<br>`context` (str): 检索到的记忆上下文<br>`user_query` (str): 用户当前提问 |
| **返回** | `str`: 纯文本回答 |
| **备注** | 底层需处理不同 SDK 对 System Prompt 的位置要求（Claude 是单独参数，OpenAI 是 `role: "system"`） |

### 4.2 `get_embedding`

| 项目 | 说明 |
|-----|------|
| **功能** | 语义降维能力 |
| **输入** | `text` (str): 需要向量化的文本 |
| **返回** | `List[float]`: 浮点数数组，维度由 `EMBEDDING_DIMENSIONS` 配置决定（默认 1536） |
| **备注** | 专为存入 `resources` 表的 `description_vector` 字段服务 |

> **配置说明**：Embedding 维度可通过 `.env` 中的 `EMBEDDING_DIMENSIONS` 配置，支持不同模型（如 `text-embedding-3-small` 默认 1536 维，`text-embedding-3-large` 支持 3072 维）。

### 4.3 `extract_memory_intent`

| 项目 | 说明 |
|-----|------|
| **功能** | 后台分析能力 |
| **输入** | `text` (str): 用户最新输入的对话<br>`categories` (List[Dict[str, Any]]): 当前已有的分类列表，每个元素包含 `name` 和 `description`<br>`assistant_response` (str, 可选): AI 回复内容，用于生成回复摘要 |
| **返回** | `Dict`: 包含分类名、摘要、重要性打分的标准 JSON 字典 |
| **备注** | 底层需通过 function calling 或特定 prompt 强制模型输出 JSON |

#### 结构化输出保证

本系统使用 Function Calling（OpenAI）或 Tool Use（Anthropic）强制模型输出结构化 JSON，无需额外的清洗逻辑。

| Provider | 实现方式 |
|----------|----------|
| OpenAI | 使用 `tools` 参数 + `tool_choice` 强制调用 `extract_memory` 函数 |
| Anthropic | 使用 `tools` 参数 + `tool_choice` 强制调用 `extract_memory` 函数 |

### 4.4 `count_tokens`

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

### 4.5 `generate_stream_response`

为提升前端用户体验（打字机效果），增加流式输出支持。

| 项目 | 说明 |
|-----|------|
| **输入** | 与 `generate_chat_response` 相同 |
| **返回** | `AsyncGenerator[str, None]`: 异步生成器，每次 yield 一个文本片段 |
| **备注** | 底层通过 SSE (Server-Sent Events) 实现逐字符/逐词推送 |

### 4.6 必须实现的接口汇总

| 方法 | 功能 |
|------|------|
| `generate_chat_response` | 核心对话能力 |
| `get_embedding` | 语义向量化 |
| `extract_memory_intent` | 记忆意图提取 |
| `count_tokens` | Token 计数 |
| `generate_stream_response` | 流式输出（可选，基类提供默认实现） |

**设计意图**：给所有模型厂商定规矩——"想进我的系统打工，必须实现这些接口，并且交出的结果格式必须一致"。

---

## 5. 核心文件功能规范

### 5.1 `services/llm/base.py` (抽象基类)

**功能**：使用 Python `abc` 模块定义 `BaseLLMProvider` 类，只写方法签名，不写具体实现。

**设计意图**：给所有模型厂商定规矩——"想进我的系统打工，必须会干这些事，并且交出的结果格式必须一致"。

### 5.2 `services/llm/openai_sdk.py` (OpenAI 标准适配器)

**功能**：包含实现类 `OpenAIProvider(BaseLLMProvider)`

**核心职责**：
1. 在 `__init__` 中使用 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL` 实例化 `AsyncOpenAI` 客户端
2. 实现 `generate_chat_response`，组装 `messages=[{"role": "user", "content": ...}]` 格式
3. 实现 `count_tokens`，使用 `tiktoken` 库按 `cl100k_base` 编码计算
4. 实现 `generate_stream_response`，通过 `stream=True` 参数启用流式输出
5. 此文件可作为通用适配器复用（DeepSeek、通义千问等均兼容 OpenAI 格式）

#### 扩展配置项

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `OPENAI_API_KEY` | OpenAI API 密钥 | 必填 |
| `OPENAI_BASE_URL` | API 基础 URL | `https://api.openai.com/v1` |
| `OPENAI_PROXY` | HTTP 代理地址 | 无 |
| `EMBEDDING_API_KEY` | 独立的 Embedding API 密钥 | 继承 `OPENAI_API_KEY` |
| `EMBEDDING_BASE_URL` | 独立的 Embedding API URL | 继承 `OPENAI_BASE_URL` |
| `EMBEDDING_MODEL` | Embedding 模型名称 | `text-embedding-3-small` |
| `EMBEDDING_DIMENSIONS` | Embedding 向量维度 | `1536` |
| `CHAT_MODEL` | 对话模型名称 | `gpt-4o-mini` |

> **设计意图**：支持 Embedding 服务与对话服务分离部署，常见于国内使用阿里云/智谱等 Embedding API 而对话使用 OpenAI 的场景。

### 5.3 `services/llm/anthropic_sdk.py` (Claude 专属适配器)

**功能**：包含实现类 `AnthropicProvider(BaseLLMProvider)`

**核心职责**：
1. 在 `__init__` 中实例化 `AsyncAnthropic` 客户端
2. 实现 `generate_chat_response`，处理 Claude 独特的 API 逻辑（`system` 参数脱离 `messages` 数组独立存在）
3. 实现 `count_tokens`，使用 Claude 官方 Token 计数逻辑
4. 实现 `generate_stream_response`，通过 `stream=True` 参数启用流式输出

### 5.4 `services/llm/factory.py` (实例化工厂)

**功能**：包含 `LLMFactory` 类，拥有静态方法 `get_provider()`，采用懒加载机制管理单例。

**内部逻辑**：
```
读取 core.config.settings.llm_provider
  ├── "openai"              → 导入 openai_sdk → return OpenAIProvider(...)
  ├── "openai-compatible"   → 导入 openai_sdk → return OpenAIProvider(...)
  ├── "deepseek"            → 导入 openai_sdk → return OpenAIProvider(...)
  ├── "qwen"                → 导入 openai_sdk → return OpenAIProvider(...)
  ├── "glm"                 → 导入 openai_sdk → return OpenAIProvider(...)
  ├── "minimax"             → 导入 openai_sdk → return OpenAIProvider(...)
  ├── "custom"              → 导入 openai_sdk → return OpenAIProvider(...)
  ├── "anthropic"           → 导入 anthropic_sdk → return AnthropicProvider(...)
  └── 其他                  → 抛出异常，阻止系统启动
```

> **说明**：所有兼容 OpenAI API 格式的厂商都复用 `OpenAIProvider`，只需配置不同的 `OPENAI_BASE_URL`。

### 5.5 `services/llm/tools.py` (工具层)

**功能**：存放 Prompt 构建函数、Tool 定义、向量计算等公共逻辑。

| 函数/常量 | 说明 |
|----------|------|
| `build_chat_prompt(context, user_query)` | 构建对话 Prompt |
| `build_memory_extraction_prompt(categories)` | 构建记忆提取 Prompt |
| `build_memory_merge_prompt(existing, new)` | 构建记忆合并判断 Prompt |
| `EXTRACT_MEMORY_TOOL_OPENAI` | OpenAI Function Calling 工具定义 |
| `EXTRACT_MEMORY_TOOL_ANTHROPIC` | Anthropic Tool Use 工具定义 |
| `cosine_similarity_from_bytes()` | 从字节计算余弦相似度 |
| `cosine_distance_to_similarity()` | 余弦距离转相似度 |

### 5.6 `api/dependencies.py` (路由层调用桥梁)

**功能**：新增 `get_llm_service()` 函数用于 FastAPI 依赖注入。

```python
def get_llm_service() -> BaseLLMProvider:
    return LLMFactory.get_provider()
```

**调用方式**：路由层 (`chat.py`) 只需写：

```python
llm: BaseLLMProvider = Depends(get_llm_service)
```

FastAPI 会自动从工厂获取当前配置的大模型实例，传递给下游业务逻辑。

---

## 6. 用户级 LLM 配置

### 6.1 设计背景

支持每个用户配置自己的 LLM API Key 和模型，实现多租户隔离。

### 6.2 数据模型

用户表新增字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `llm_provider` | String | LLM 提供商 (openai/deepseek/qwen/anthropic 等) |
| `llm_api_key` | String | 用户的 API Key |
| `llm_base_url` | String | API Base URL（可选） |
| `llm_model` | String | 模型名称 |
| `llm_warmed_up` | Boolean | 是否已预热 |

### 6.3 用户级工厂

`UserLLMFactory` 为每个用户维护独立的 LLM 客户端：

```python
# 获取用户级 LLM
llm = UserLLMFactory.get_or_create(
    user_id=user.id,
    provider=user.llm_provider,
    api_key=user.llm_api_key,
    base_url=user.llm_base_url,
    model=user.llm_model,
)
```

### 6.4 优先级规则

聊天时，LLM 配置的优先级：

1. **用户级配置**（优先）：如果用户在设置页面配置了 LLM，使用用户配置
2. **全局配置**（后备）：如果用户未配置，使用环境变量中的全局配置

### 6.5 预热机制

用户保存 LLM 配置后，后台异步预热：

```python
asyncio.create_task(_warmup_and_generate_categories(...))
```

预热完成后再生成个性化分类。

---

## 7. 待完善事项

| 优先级 | 事项 | 说明 |
|--------|------|------|
| 高 | 强制用户配置 LLM | 当前允许未配置用户使用全局配置，应改为引导用户配置 |
| 中 | LLM 配置加密存储 | 当前 API Key 明文存储，应加密 |
| 中 | 配置校验 | 保存前验证 API Key 有效性 |
| 低 | 多模型支持 | 支持用户配置多个模型（聊天/嵌入分开） |
