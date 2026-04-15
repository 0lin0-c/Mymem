# API 接口定义

本文档定义了 `input-pipeline` 模块对外暴露的所有 API 接口。

---

## 1. POST /v1/user/onboarding

初始化用户画像和 AI 定制（首次进入时调用）。

> **请求字段详情**：详见 `frontend-design` skill

### 响应

```json
{
  "success": true,
  "user_id": "uuid-xxx",
  "user_prompt_template": "用户小明，高中生，高二文科方向。",
  "agent_persona_template": "你是小智，用户的学习导师。性格：温柔耐心、严谨专业。称呼用户"小明"，自称"小智"。",
  "initial_categories": {
    "fixed": [
      {"name": "核心自我", "description": "个人画像、偏好习惯、长期目标", "is_fixed": true},
      {"name": "情景时间轴", "description": "绑定时间的事件和待办", "is_fixed": true},
      {"name": "语义知识库", "description": "纯粹的知识、灵感与资产", "is_fixed": true},
      {"name": "社交关系图谱", "description": "人际链接与关系备注", "is_fixed": true}
    ],
    "dynamic": [
      {"name": "学校生活", "description": "社团活动、选课考勤、校园琐事等学校日常", "is_fixed": false},
      {"name": "考试与升学", "description": "备考资料、分数追踪、升学规划等学业进度", "is_fixed": false}
    ]
  },
  "message": "身份初始化完成，可以开始对话了"
}
```

### 处理逻辑

1. 解析请求数据
2. 将 `username` 存入 User 表
3. 生成精简版 `user_prompt_template`（基本信息），存入 User 表
4. 生成 `agent_persona_template`，存入 User 表
5. 调用 LLM 生成 2 个动态分类名称
6. 将用户初始化信息作为原子化记忆存入 Category 表（`category_name` 设为"核心自我"等）

---

## 2. PUT /v1/user/profile

更新用户画像（会重新生成 `user_prompt_template` 并存入数据库）。

---

## 3. PUT /v1/user/ai-customization

更新 AI 助手定制（会重新生成 `agent_persona_template` 并存入数据库）。

---

## 4. POST /v1/chat

### 请求

```json
{
    "session_id": "会话ID",
    "query": "用户输入的问题",
    "modality": "text"
}
```

### 响应

```json
{
    "answer": "AI 的回复",
    "user_id": "用户ID",
    "user_name": "用户名",
    "is_identified": true,
    "resource_id": "资源ID",
    "category_name": "分类名",
    "importance_score": 7
}
```

---

## 5. POST /v1/chat/save

直接保存对话到记忆（不生成回复），适用于批量导入历史对话或第三方系统对接。

### 请求

```json
{
    "user_id": "用户ID",
    "user_input": "用户输入",
    "assistant_response": "AI 回复",
    "modality": "text"
}
```

### 响应

```json
{
    "success": true,
    "resource_id": "资源ID",
    "category_name": "分类名",
    "category_id": "分类ID",
    "importance_score": 7,
    "message": "记忆保存成功"
}
```

---

## 6. GET /v1/memory/atomic-items

获取用户的原子化记忆（Category 表）。

### 请求参数（Query）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | string | 是 | 用户ID |
| `category_name` | string | 否 | 按分类名筛选 |
| `limit` | int | 否 | 返回数量，默认 50 |

### 响应

```json
{
  "atomic_items": [
    {
      "id": "uuid-xxx",
      "category_name": "核心自我",
      "content": "用户喜欢编程",
      "importance_score": 7,
      "created_at": "2025-01-01T00:00:00Z"
    }
  ]
}
```

---

## 7. GET /v1/memory/resources

获取用户的对话摘要列表（Resource 表）。

### 请求参数（Query）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | string | 是 | 用户ID |
| `limit` | int | 否 | 返回数量，默认 20 |

### 响应

```json
{
  "resources": [
    {
      "id": "uuid-xxx",
      "modality": "text",
      "description": "用户讨论了...",
      "assistant_response": "AI回复内容",
      "importance_score": 7,
      "updated_at": "2025-01-01T00:00:00Z",
      "created_at": "2025-01-01T00:00:00Z"
    }
  ]
}
```

---

## 8. GET /v1/memory/resources/{resource_id}

获取单个对话摘要的详情（含关联的原子化记忆）。

### 请求参数（Query）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | string | 是 | 用户ID |

### 响应

```json
{
  "id": "uuid-xxx",
  "modality": "text",
  "raw_content": "原始对话内容",
  "description": "对话摘要",
  "assistant_response": "AI回复",
  "importance_score": 7,
  "updated_at": "2025-01-01T00:00:00Z",
  "created_at": "2025-01-01T00:00:00Z",
  "atomic_items": [
    {
      "id": "uuid-yyy",
      "category_name": "核心自我",
      "content": "用户喜欢编程",
      "importance_score": 7
    }
  ]
}
```

---

## 9. GET /v1/memory/category-stats

获取各分类的统计信息。

### 请求参数（Query）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | string | 是 | 用户ID |

### 响应

```json
{
  "success": true,
  "stats": {
    "核心自我": {"count": 10, "avg_importance": 6.5},
    "语义知识库": {"count": 5, "avg_importance": 5.0}
  }
}
```

---

## 10. GET /v1/memory/stats

获取记忆库整体统计信息。

### 请求参数（Query）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | string | 是 | 用户ID |

### 响应

```json
{
  "success": true,
  "total_resources": 42,
  "total_categories": 30,
  "avg_importance": 5.8
}
```

---

## 11. PUT /v1/memory/resources/{resource_id}

更新对话摘要。

### 请求

```json
{
  "user_id": "用户ID",
  "resource_id": "资源ID",
  "description": "新的摘要内容",
  "importance_score": 7
}
```

### 响应

```json
{
  "success": true,
  "message": "对话摘要已更新"
}
```

---

## 12. PUT /v1/memory/atomic-items/{item_id}

更新原子化记忆。

### 请求

```json
{
  "user_id": "用户ID",
  "item_id": "原子化记忆ID",
  "content": "新的记忆内容",
  "importance_score": 7
}
```

### 响应

```json
{
  "success": true,
  "message": "原子化记忆已更新"
}
```

---

## 13. DELETE /v1/memory/resources/{resource_id}

删除对话摘要及其关联的原子化信息。

### 请求参数（Query）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | string | 是 | 用户ID |

### 响应

```json
{
  "success": true,
  "message": "对话摘要已删除"
}
```

---

## 14. DELETE /v1/memory/atomic-items/{item_id}

删除单条原子化记忆。

### 请求参数（Query）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | string | 是 | 用户ID |

### 响应

```json
{
  "success": true,
  "message": "原子化记忆已删除"
}
```

---

## 15. POST /v1/memory/forget

清理低重要性记忆（遗忘机制）。

### 请求

```json
{
  "user_id": "用户ID",
  "threshold": 2.0
}
```

### 响应

```json
{
  "success": true,
  "deleted_categories": 5,
  "message": "已清理 5 条低重要性记忆"
}
```

---

## 16. POST /v1/memory/decay

执行重要性衰减（时间越久的重要性自动降低）。

### 请求参数（Query）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | string | 是 | 用户ID |

### 响应

```json
{
  "success": true,
  "updated_resources": 10,
  "updated_categories": 8,
  "message": "已更新 8 条原子化记忆的重要性"
}
```
