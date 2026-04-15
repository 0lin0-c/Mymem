# 适配器实现规范

本文档定义各 Provider 的适配器实现规范和工厂逻辑。

---

## 1. OpenAI 标准适配器

**文件**：`services/llm/openai_sdk.py`

**功能**：包含实现类 `OpenAIProvider(BaseLLMProvider)`

**核心职责**：
1. 在 `__init__` 中使用 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL` 实例化 `AsyncOpenAI` 客户端
2. 实现 `generate_chat_response`，组装 `messages=[{"role": "user", "content": ...}]` 格式
3. 实现 `count_tokens`，使用 `tiktoken` 库按 `cl100k_base` 编码计算
4. 实现 `generate_stream_response`，通过 `stream=True` 参数启用流式输出
5. 此文件可作为通用适配器复用（DeepSeek、通义千问等均兼容 OpenAI 格式）

### 1.1 扩展配置项

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

---

## 2. Claude 专属适配器

**文件**：`services/llm/anthropic_sdk.py`

**功能**：包含实现类 `AnthropicProvider(BaseLLMProvider)`

**核心职责**：
1. 在 `__init__` 中实例化 `AsyncAnthropic` 客户端
2. 实现 `generate_chat_response`，处理 Claude 独特的 API 逻辑（`system` 参数脱离 `messages` 数组独立存在）
3. 实现 `count_tokens`，使用 Claude 官方 Token 计数逻辑
4. 实现 `generate_stream_response`，通过 `stream=True` 参数启用流式输出

---

## 3. 实例化工厂

**文件**：`services/llm/factory.py`

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

---

## 4. 工具层

**文件**：`services/llm/tools.py`

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

---

## 5. 依赖注入

**文件**：`api/dependencies.py`

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
