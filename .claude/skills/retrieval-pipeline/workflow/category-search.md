# Category 层向量检索（第一层）

本文档定义检索流程的第二步：在 LLM 指定的类别内执行 Category 表的向量检索。

---

## 1. 表结构说明

**Category 表关键字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | String(36) | 主键 |
| `user_id` | String(36) | 用户 ID |
| `category_name` | String(100) | 分类名称（在 categories 表，不在 resources 表） |
| `content` | Text | 原子化的记忆内容 |
| `content_vector` | Vector(1536) | 记忆内容的向量嵌入 |
| `importance_score` | Integer | 重要性评分 (0-3) |
| `access_count` | Integer | 访问次数（用于检索分数计算） |
| `updated_at` | DateTime | 更新时间（用于时间衰减计算） |

---

## 2. 检索逻辑

```
1. 过滤条件：user_id + category_name IN (目标类别列表) + content_vector IS NOT NULL
2. 四因子评分：power(GREATEST(cosine_similarity, 0), similarity_power) × power(log(access_count+2), access_power) × power(recency, recency_power) × power(importance_factor, importance_power)
3. 按评分降序返回 Top-K
```

---

## 3. 参数配置

| 参数 | 值 | 说明 |
|------|------|------|
| `recency_decay_days` | 60 | Category 层默认半衰期 |
| `similarity_power` | 1.5 | 默认提高相似度差异对排序的影响 |
| `access_power` | 1.0 | 访问次数指数 |
| `recency_power` | 1.0 | 时间衰减指数 |
| `importance_power` | 1.0 | 重要性指数 |
| 综合分数阈值 | 0.03 | 低于此值过滤 |

---

## 4. 后续流程

检索完成后进入 LLM 充足性判断，详见 `sufficiency-check.md`。
