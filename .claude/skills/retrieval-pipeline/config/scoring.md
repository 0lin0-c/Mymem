# 检索分数与阈值配置

本文档定义检索分数计算逻辑与过滤阈值。

---

## 1. 四因子乘法评分公式

```
score = cosine_similarity × log(access_count + 1) × exp(-0.693 × days_ago / recency_decay_days) × (importance_score / 5)
```

**参数说明**：

| 参数 | 说明 | 来源 |
|------|------|------|
| `cosine_similarity` | 向量余弦相似度，`1 - cosine_distance` | 实时计算 |
| `access_count` | 访问次数 | 表字段 `access_count` |
| `days_ago` | 距上次更新的天数 | `(now - updated_at).total_seconds() / 86400` |
| `recency_decay_days` | 时间衰减半衰期 | 分层默认值 |
| `importance_score` | 重要性评分 | 表字段 `importance_score` (1-10) |

**分层默认值**：

| 检索层 | `recency_decay_days` | 说明 |
|--------|----------------------|------|
| Category 层 | 60 | 原子化记忆半衰期 |
| Resource 层 | 60 | 对话摘要半衰期 |

**常量说明**：
- `0.693 = ln(2)`，保证半衰期语义

---

## 2. 四因子含义

| 因子 | 作用 | 影响 |
|------|------|------|
| `cosine_similarity` | 语义匹配度 | 核心检索指标 |
| `log(access_count + 1)` | 访问加成 | 多次访问的记忆权重更高 |
| `exp(-0.693 × days_ago / recency_decay_days)` | 时间衰减 | 近期记忆权重更高 |
| `importance_score / 5` | 重要性加成 | 高价值记忆权重更高 |

---

## 3. 四因子评分阈值

由于四因子评分综合了多个因子，其值域与纯相似度不同。阈值配置：

| 阈值常量 | 值 | 用途 |
|----------|-----|------|
| `FOUR_FACTOR_THRESHOLD_HIGH` | 0.6 | 降级策略：LLM 充足性判断失败时，最高分 >= 0.6 判定为"足够" |
| `FOUR_FACTOR_THRESHOLD_MEDIUM` | 0.2 | 预留 |
| `FOUR_FACTOR_THRESHOLD_LOW` | 0.1 | 过滤阈值：分数 < 0.1 的结果直接丢弃 |

**过滤逻辑**：
- 所有检索结果按四因子评分降序排序
- 分数 < 0.1 的结果被过滤掉
- 其余结果保留并返回

**降级策略逻辑**（在 `_check_sufficiency()` 中）：
```
LLM 充足性判断失败时：
  if 最高分 >= 0.6 → 判定为"足够"，跳过 Resource 层检索
  if Category 结果 >= 3 条 → 判定为"足够"
  else → 进入 Resource 层检索
```

---

## 4. 计算示例

- **最高分场景**：similarity=1.0, access_count=100, days_ago=0, importance=10
  - score = 1.0 × ln(101) × exp(0) × 2.0 ≈ **9.23**
- **中等分场景**：similarity=0.8, access_count=5, days_ago=30, importance=7
  - score = 0.8 × ln(6) × exp(-0.347) × 1.4 ≈ **1.42**
- **低分场景**：similarity=0.6, access_count=1, days_ago=90, importance=3
  - score = 0.6 × ln(2) × exp(-1.04) × 0.6 ≈ **0.088**

**注意**：四因子评分值域范围较广，实际阈值应根据业务数据分布调整。
