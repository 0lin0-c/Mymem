# 检索 API 定义

本文档定义检索相关的 API 接口。

---

## 1. POST /v1/retrieve

### 请求

```json
{
    "user_id": "用户ID",
    "query": "用户查询",
    "top_k": 10,
    "min_importance": 3
}
```

### 响应

```json
{
    "categories_detected": ["项目研发", "情景时间轴"],
    "results": [
        {
            "resource_id": "uuid-xxx",
            "description": "记忆内容摘要",
            "category_name": "项目研发",
            "importance_score": 8,
            "retrieval_score": 0.92,
            "created_at": "2024-03-20"
        }
    ],
    "total": 5,
    "context_text": "【项目研发】Python 项目进度：已完成..."
}
```

---

## 2. GET /v1/retrieve/stats

获取检索统计信息，用于优化检索策略。
