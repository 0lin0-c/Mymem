# Resource 层向量检索（第二层）

本文档定义检索流程的第四步：根据 Category 关联检索 Resource 表。

---

## 1. 触发条件

LLM 充足性判断结果为"不足"时，进入 Resource 层检索。

---

## 2. 表结构说明

**Resource 表关键字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | String(36) | 主键 |
| `user_id` | String(36) | 用户 ID |
| `description` | Text | 对话摘要 |
| `description_vector` | Vector(1536) | 摘要的向量嵌入 |
| `importance_score` | Integer | 重要性评分 (0-3) |
| `access_count` | Integer | 访问次数（用于检索分数计算） |
| `updated_at` | DateTime | 更新时间（用于时间衰减计算） |

---

## 3. 检索逻辑

```
1. 根据已检索的 Category ID 找到关联的 Resource ID（通过 resource_categories 关联表）
2. 过滤条件：user_id + resource_id IN (关联的 Resource 列表) + description_vector IS NOT NULL
3. 四因子评分：power(GREATEST(cosine_similarity, 0), similarity_power) × power(log(access_count+2), access_power) × power(recency, recency_power) × power(importance_factor, importance_power)
4. 按评分降序返回 Top-K
```

---

## 4. SQL 实现要点

三表 JOIN：
- `resources` 表：存储对话摘要和向量
- `categories` 表：存储原子化记忆和分类信息
- `resource_categories` 表：关联 resources 和 categories

过滤条件使用 `c.category_name = ANY(:target_categories)` 限定在 LLM 指定的类别内。

---

## 5. 参数配置

| 参数 | 值 | 说明 |
|------|------|------|
| `recency_decay_days` | 60 | Resource 层默认半衰期 |
| `similarity_power` | 1.5 | 默认提高相似度差异对排序的影响 |
| `access_power` | 1.0 | 访问次数指数 |
| `recency_power` | 1.0 | 时间衰减指数 |
| `importance_power` | 1.0 | 重要性指数 |
| 综合分数阈值 | 0.03 | 低于此值过滤 |

---

## 6. 结果合并

Resource 层检索结果与 Category 层检索结果合并后：
- 按综合分数排序
- 去重（同一 Resource 可能被多个 Category 关联）
- 构建最终上下文供 LLM 回答
