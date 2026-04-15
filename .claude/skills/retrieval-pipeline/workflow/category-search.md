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
| `importance_score` | Integer | 重要性评分 (1-10) |
| `access_count` | Integer | 访问次数（用于检索分数计算） |
| `updated_at` | DateTime | 更新时间（用于时间衰减计算） |

---

## 2. 检索逻辑

```
1. 过滤条件：user_id + category_name IN (目标类别列表) + 相似度 >= 0.55
2. 四因子评分：cosine_similarity × log(access_count+1) × exp(-0.693 × days_ago / 60) × (importance_score / 5)
3. 按评分降序返回 Top-K
```

---

## 3. 参数配置

| 参数 | 值 | 说明 |
|------|------|------|
| `recency_decay_days` | 60 | Category 层半衰期更长 |
| 相似度阈值 | 0.55 | 低于此值过滤 |

---

## 4. 后续流程

检索完成后进入 LLM 充足性判断，详见 `sufficiency-check.md`。
