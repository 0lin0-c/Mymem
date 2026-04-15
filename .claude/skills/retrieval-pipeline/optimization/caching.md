# 性能优化与缓存策略

本文档定义检索流程的性能优化策略。

> **状态**：规划中，暂未实现。当前优先级为 P2。

---

## 1. 预过滤策略

```python
async def _search_in_categories(
    user_id: str,
    categories: list[str],  # LLM 指定的类别
    query: str,
    top_k: int,
    min_importance: int = 3,
) -> list[dict]:
    """
    在指定类别内检索
    使用向量相似度 + importance_score 综合排序
    """
    # 获取查询向量
    query_vector = await llm.get_embedding(query)

    # 执行三表 JOIN + 向量检索
    sql = text("""
        SELECT r.*, c.*, (r.description_vector <=> :query_vector) AS distance
        FROM resources r
        JOIN resource_categories rc ON r.id = rc.resource_id
        JOIN categories c ON rc.category_id = c.id
        WHERE r.user_id = :user_id
          AND c.category_name = ANY(:categories)
          AND r.importance_score >= :min_importance
        ORDER BY distance ASC
        LIMIT :top_k
    """)
    # ... 执行查询并返回结果
```

---

## 2. 缓存策略（规划中）

| 缓存类型 | 说明 | TTL | 状态 |
|----------|------|-----|------|
| 用户分类列表 | 用户的所有分类名 | 1 小时 | 规划中 |
| 热门记忆 | 高 importance 的记忆 | 30 分钟 | 规划中 |
| 查询结果缓存 | 相同查询的结果 | 5 分钟 | 规划中 |

---

## 3. 实现说明

当前版本暂未实现缓存策略，原因：
1. 优先保证核心检索功能的稳定性
2. 缓存失效策略需要更多业务场景验证
3. 后续可考虑使用 Redis 或内存缓存实现
