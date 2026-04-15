# 记忆来源关联表 (`resource_categories`)

本文档定义记忆来源关联表的字段结构。

---

## 功能定位

记录原子化记忆（Category）与对话摘要（Resource）之间的关系，支持追踪每条记忆的完整历史来源。

---

## 字段定义

| 字段名 (`Column`) | 数据类型 (`Type`) | 约束与属性 | 设计意图与功能 |
| --- | --- | --- | --- |
| `id` | `String` | `Primary Key`, 默认生成 UUID | 唯一标识。 |
| `resource_id` | `String` | `ForeignKey('resources.id', ondelete='CASCADE')`, `Index` | 关联的对话摘要 ID。 |
| `category_id` | `String` | `ForeignKey('categories.id', ondelete='CASCADE')`, `Index` | 关联的原子化记忆 ID。 |
| `relation_type` | `String` | 默认 `"created"` | 关联类型：`created`/`updated`。 |
| `note` | `Text` | `Nullable` | 关联说明（可选）。 |
| `created_at` | `DateTime` | `timezone=True`, 默认 `func.now()` | 关联创建时间。**强制带时区**。 |

---

## 关联类型说明

| 类型 | 说明 |
| --- | --- |
| `created` | 该 Resource 首次创建了这个原子化记忆 |
| `updated` | 该 Resource 更新了这个原子化记忆 |

> **重复提及的处理**：当用户重复提及某条记忆时，直接增加 `Category.importance_score`，不创建新的关联记录。
