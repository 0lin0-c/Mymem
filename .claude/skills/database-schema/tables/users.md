# 用户表 (`users`)

本文档定义用户表的字段结构。

---

## 功能定位

系统的全局配置锚点。未来如果有多个用户共用该系统，此表用于实现数据和人设的绝对物理隔离。

---

## 字段定义

| 字段名 (`Column`) | 数据类型 (`Type`) | 约束与属性 | 设计意图与功能 |
| --- | --- | --- | --- |
| `id` | `String` | `Primary Key`, 默认生成 UUID | 唯一标识。 |
| `username` | `String` | `Unique`, `Index` | 用于登录或身份识别的唯一代号。 |
| `password` | `String` | - | 用户登录密码（存储哈希值）。 |
| `user_prompt_template` | `Text` | `Nullable` | **替代传统的 `USER.md`**。存储该用户的全局客观画像。使用 Text 类型便于在数据库后台直接预览和调试。 |
| `agent_persona_template` | `Text` | `Nullable` | **替代传统的 `SOUL.md`**。存储当前助手的性格、语气指令。使用 Text 类型便于在数据库后台直接预览和调试。 |
| `llm_provider` | `String` | `Nullable` | LLM 提供商: openai/deepseek/qwen/glm/anthropic/custom。 |
| `llm_api_key` | `String` | `Nullable` | LLM API Key。 |
| `llm_base_url` | `String` | `Nullable` | LLM API Base URL。 |
| `llm_model` | `String` | `Nullable` | LLM 模型名称。 |
| `llm_warmed_up` | `Boolean` | 默认 `False` | LLM 是否已预热。 |
| `created_at` | `DateTime` | `timezone=True`, 默认 `func.now()` | 记录账户/人设的初始创建时间。**强制带时区**，防止 NAS 环境与服务器时区不一致。 |
| `updated_at` | `DateTime` | `timezone=True`, `server_default=func.now()`, `onupdate=func.now()` | 任何字段更新时自动更新。**强制带时区**。 |
