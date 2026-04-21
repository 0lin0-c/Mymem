# 原子化记忆表 (`categories`)

本文档定义原子化记忆表的字段结构。

---

## 功能定位

存储从对话摘要中提取的原子化信息。每条记录是一条独立的信息，归属一个固定的分类。

---

## 字段定义

| 字段名 (`Column`) | 数据类型 (`Type`) | 约束与属性 | 设计意图与功能 |
| --- | --- | --- | --- |
| `id` | `String` | `Primary Key`, 默认生成 UUID | 唯一标识。 |
| `user_id` | `String` | `ForeignKey('users.id', ondelete='CASCADE')`, `Index` | 绑定用户。`CASCADE` 确保注销用户时自动清理记忆残余。 |
| `category_name` | `String` | `Index` | 归属的分类名（核心自我/情景时间轴/语义知识库/社交关系图谱/动态分类）。 |
| `content` | `Text` | - | 原子化的记忆内容（一条独立的信息）。 |
| `content_vector` | `Vector(1536)` | `pgvector` 专有类型，`Nullable` | 记忆内容的向量嵌入，用于 Category 层向量检索。 |
| `importance_score` | `Integer` | 默认 `2` | 该条信息的重要性评分 (0-3)。检索默认不按重要性提前硬过滤，排序阶段通过可配置四因子评分使用该值。 |
| `access_count` | `Integer` | 默认 `0` | 被检索引用的次数。用于检索分数的访问加成计算。 |
| `created_at` | `DateTime` | `timezone=True`, 默认 `func.now()` | 分类首次建立时间。**强制带时区**。 |
| `updated_at` | `DateTime` | `timezone=True`, `server_default=func.now()`, `onupdate=func.now()` | 更新时间。用于检索分数的时间衰减计算。**强制带时区**。 |
