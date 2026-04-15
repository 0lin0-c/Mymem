# 对话摘要表 (`resources`)

本文档定义对话摘要表的字段结构。

---

## 功能定位

存储对话粒度的综合摘要。每条记录对应一次对话交互（如 5 轮对话的总结）。配合 `pgvector` 插件进行高维语义空间搜索。

---

## 字段定义

| 字段名 (`Column`) | 数据类型 (`Type`) | 约束与属性 | 设计意图与功能 |
| --- | --- | --- | --- |
| `id` | `String` | `Primary Key`, 默认生成 UUID | 唯一标识。 |
| `user_id` | `String` | `ForeignKey('users.id', ondelete='CASCADE')`, `Index` | 绑定用户。`CASCADE` 确保注销用户时自动清理记忆残余。 |
| `modality` | `String` | 默认 `"text"` | **多模态扩展预留**。可填入 `"text"`, `"image"`, `"audio"`。 |
| `raw_content` | `Text` | - | 用户输入的原始文本（防篡改底稿）。 |
| `description` | `Text` | `Nullable` | LLM 生成的对话综合摘要（客观第三人称描述），用于向量化。 |
| `assistant_response` | `Text` | `Nullable` | AI 助手回复的摘要。 |
| `description_vector` | `Vector(1536)` | `pgvector` 专有类型，需启用扩展 | **语义检索核心**。存储由 OpenAI/特定模型生成的 1536 维向量。SQLAlchemy 使用 `pgvector.sqlalchemy.Vector` 映射。 |
| `importance_score` | `Integer` | 默认 `5` | 由 LLM 在入库前打分 (1-10)。用于在检索库过大时，硬性过滤掉分值低于 3 的日常"废话"。 |
| `access_count` | `Integer` | 默认 `0` | 被检索引用的次数。用于检索分数的访问加成计算。 |
| `created_at` | `DateTime` | `timezone=True`, 默认 `func.now()` | 记忆发生的确切时间戳。**强制带时区**。 |
| `updated_at` | `DateTime` | `timezone=True`, `server_default=func.now()`, `onupdate=func.now()` | 更新时间。用于检索分数的时间衰减计算。**强制带时区**。 |
