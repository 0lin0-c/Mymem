# 检索分数与阈值配置

本文档定义检索分数计算逻辑与过滤阈值。

---

## 1. 可配置四因子乘法评分公式

```
score =
  power(GREATEST(cosine_similarity, 0), similarity_power)
  × power(log(access_count + 2), access_power)
  × power(exp(-0.693 × days_ago / recency_decay_days), recency_power)
  × power(0.7 + importance_score / 10.0, importance_power)
```

**参数说明**：

| 参数 | 说明 | 来源 |
|------|------|------|
| `cosine_similarity` | 向量余弦相似度，`1 - cosine_distance`，下限截断为 0 | 实时计算 |
| `access_count` | 访问次数 | 表字段 `access_count` |
| `days_ago` | 距上次更新的天数 | `(now - updated_at).total_seconds() / 86400` |
| `recency_decay_days` | 时间衰减半衰期 | `RetrievalScoringConfig` |
| `importance_score` | 重要性评分 | 表字段 `importance_score` (0-3) |
| `similarity_power` | 相似度指数 | `RetrievalScoringConfig` |
| `access_power` | 访问次数指数 | `RetrievalScoringConfig` |
| `recency_power` | 时间衰减指数 | `RetrievalScoringConfig` |
| `importance_power` | 重要性指数 | `RetrievalScoringConfig` |

**默认值** 位于 `services/retrieval/scoring_config.py`：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `recency_decay_days` | 60 | Category/Resource 默认半衰期 |
| `similarity_power` | 1.5 | 默认提高相似度差异对排序的影响 |
| `access_power` | 1.0 | 保持访问次数原始影响 |
| `recency_power` | 1.0 | 保持时间衰减原始影响 |
| `importance_power` | 1.0 | 保持重要性原始影响 |

**常量说明**：
- `0.693 = ln(2)`，保证半衰期语义

---

## 2. 四因子含义

| 因子 | 作用 | 影响 |
|------|------|------|
| `power(GREATEST(cosine_similarity, 0), similarity_power)` | 语义匹配度 | 核心检索指标，默认 `similarity_power=1.5` |
| `power(log(access_count + 2), access_power)` | 访问加成 | `+2` 避免 0 次访问把总分乘成 0 |
| `power(exp(-0.693 × days_ago / recency_decay_days), recency_power)` | 时间衰减 | 近期记忆权重更高 |
| `power(0.7 + importance_score / 10.0, importance_power)` | 重要性加成 | 兼容 0-3 分制，避免重要性过度支配 |

---

## 3. 四因子评分阈值

由于四因子评分综合了多个因子，其值域与纯相似度不同。阈值配置：

| 阈值常量 | 值 | 用途 |
|----------|-----|------|
| `FOUR_FACTOR_THRESHOLD_HIGH` | 0.6 | 降级策略：LLM 充足性判断失败时，最高分 >= 0.6 判定为"足够" |
| `FOUR_FACTOR_THRESHOLD_MEDIUM` | 0.2 | 预留 |
| `FOUR_FACTOR_THRESHOLD_LOW` | 0.03 | 过滤阈值：分数 < 0.03 的结果直接丢弃 |

**过滤逻辑**：
- 所有检索结果按四因子评分降序排序
- 分数 < 0.03 的结果被过滤掉
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

- **最高分场景**：similarity=1.0, access_count=100, days_ago=0, importance=3
  - score = 1.0^1.5 × ln(102) × exp(0) × 1.0 ≈ **4.62**
- **中等分场景**：similarity=0.8, access_count=5, days_ago=30, importance=2
  - score = 0.8^1.5 × ln(7) × exp(-0.347) × 0.9 ≈ **0.88**
- **低分场景**：similarity=0.4, access_count=1, days_ago=90, importance=1
  - score = 0.4^1.5 × ln(3) × exp(-1.04) × 0.8 ≈ **0.078**

**注意**：四因子评分值域范围较广，实际阈值应根据业务数据分布调整。
