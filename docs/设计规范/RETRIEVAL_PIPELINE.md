# 🔍 记忆检索流程设计

## 1. 检索流程概览

采用 **LLM 驱动的串行检索** 架构：

```
用户查询
    │
    ▼
┌─────────────────────────────────────────┐
│ 1. LLM 分类判断                          │
│    "这个问题属于哪些类别？"               │
│    → 动态输出 1-N 个相关类别             │
│    → 例如：[项目研发] 或 [核心自我, 考试与升学] │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ 2. 分类内检索                            │
│    只在 LLM 指定的类别中检索              │
│    按 importance_score + 向量相似度排序  │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ 3. 结果作为上下文                        │
│    检索到的记忆作为 system prompt 上下文  │
│    供 LLM 回答时参考                     │
└─────────────────────────────────────────┘
```

---

## 2. LLM 分类判断

### 2.1 设计原则

**动态数量**：LLM 根据问题复杂度决定类别数量，而非固定值。

| 问题类型 | 类别数量 | 示例 |
|----------|----------|------|
| 单一明确 | 1 个 | "我的项目进度" → [项目研发] |
| 多维度 | 2-3 个 | "我最近学习情况怎么样" → [核心自我, 考试与升学] |
| 开放式 | 可能多个 | "帮我回顾一下最近的事" → [情景时间轴, 核心自我] |

### 2.2 分类判断 Prompt

```
# Role
你是一个记忆分类专家。根据用户查询，判断需要检索哪些类别的记忆。

# 用户查询
{user_query}

# 可用分类
{available_categories}

# 判断规则
1. 只返回与查询直接相关的分类
2. 数量不限，但不要过度泛化
3. 如果查询明确指向某个领域，只返回该领域
4. 如果查询模糊，可以返回多个相关分类

# 输出格式
返回 JSON 数组：
["分类名1", "分类名2", ...]
```

### 2.3 返回示例

**查询**："我那个 Python 项目进度怎么样了？"

**LLM 返回**：
```json
["项目研发"]
```

**查询**："最近有什么重要的事情需要我处理吗？"

**LLM 返回**：
```json
["情景时间轴", "项目研发"]
```

---

## 3. 分类内检索

### 3.1 检索逻辑

在 LLM 指定的类别内执行检索：

```
1. 过滤条件：user_id + category_name IN (目标类别列表)
2. 重要性过滤：importance_score >= min_importance（当前默认 0，兼容 0-3 分制）
3. 向量相似度：计算 query_vector 与 description_vector 的距离
4. 综合排序：可配置四因子评分，默认提高向量相似度的相对影响
5. 返回 Top-K
```

### 3.2 SQL 实现

```sql
SELECT *,
       (description_vector <=> :query_vector) AS cosine_distance
FROM resources
WHERE user_id = :user_id
  AND category_name IN (:target_categories)  -- LLM 指定的类别
  AND importance_score >= :min_importance
  AND description_vector IS NOT NULL
ORDER BY
    power(GREATEST((1 - cosine_distance), 0), :similarity_power)
    * power(ln(access_count + 2), :access_power)
    * power(exp(-0.693 * EXTRACT(EPOCH FROM (NOW() - updated_at)) / 86400 / :recency_decay_days), :recency_power)
    * power((0.7 + (importance_score / 10.0)), :importance_power) DESC
LIMIT :top_k
```

### 3.3 排序权重

当前实现不再使用线性固定权重，而是使用 `RetrievalScoringConfig` 控制四因子指数。默认配置放在 `services/retrieval/scoring_config.py`：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `recency_decay_days` | 60 | 时间衰减半衰期 |
| `similarity_power` | 1.5 | 提高相似度差异的影响；0-1 范围内指数大于 1 会压低低相似结果 |
| `access_power` | 1.0 | 访问次数因子的指数 |
| `recency_power` | 1.0 | 时间衰减因子的指数 |
| `importance_power` | 1.0 | 重要性因子的指数 |

测试/CLI 可以覆盖这些参数做实验，但 `/v1/retrieve` 当前不暴露这些参数为公开 API 契约。

---

## 4. 检索分数计算

### 4.1 综合检索分数公式

```python
def calculate_retrieval_score(
    cosine_distance: float,
    access_count: int,
    days_ago: float,
    importance_score: int,
    config: RetrievalScoringConfig,
) -> float:
    """
    计算单条记忆的检索分数。分数越高，越应该被返回。
    """
    similarity = max(1 - cosine_distance, 0)
    access_factor = math.log(access_count + 2)
    recency_factor = math.exp(-0.693 * days_ago / config.recency_decay_days)
    importance_factor = 0.7 + (importance_score / 10.0)

    return (
        similarity ** config.similarity_power
        * access_factor ** config.access_power
        * recency_factor ** config.recency_power
        * importance_factor ** config.importance_power
    )
```

对应 SQL 公式：

```sql
power(GREATEST((1 - (vector <=> CAST(:query_vector AS vector))), 0), :similarity_power)
* power(ln(access_count + 2), :access_power)
* power(exp(-0.693 * EXTRACT(EPOCH FROM (NOW() - updated_at)) / 86400 / :recency_decay_days), :recency_power)
* power((0.7 + (importance_score / 10.0)), :importance_power)
```

### 4.2 分数组成

| 维度 | 当前实现 | 说明 |
|------|----------|------|
| **向量相似度** | `power(GREATEST(similarity, 0), similarity_power)` | 语义匹配的核心指标，默认 `similarity_power=1.5` |
| **访问次数** | `power(ln(access_count + 2), access_power)` | `+2` 保证 0 次访问也不把结果乘成 0 |
| **时间衰减** | `power(exp(-0.693 * days_ago / recency_decay_days), recency_power)` | 默认半衰期 60 天 |
| **重要性分数** | `power(0.7 + importance_score / 10.0, importance_power)` | 兼容 0-3 分制，避免 importance 过度支配 |

### 4.3 向量相似度阈值

| 相似度 | 判定 | 处理方式 |
|--------|------|----------|
| ≥ 0.85 | 高度相关 | 优先返回 |
| 0.70 - 0.85 | 相关 | 正常返回 |
| 0.55 - 0.70 | 弱相关 | 仅在候选不足时返回 |
| < 0.55 | 不相关 | 旧设计建议过滤；当前实现主要依赖综合分数阈值过滤 |

### 4.4 最低重要性过滤

当前记忆重要性为 0-3 分制。检索默认 `min_importance=0`，避免在检索阶段提前丢弃可能语义相关的低分记忆；结果质量主要由综合分数、top-k、去重和 LLM 最终使用判断控制。

---

## 5. 上下文构建

### 5.1 上下文构建逻辑

检索到的记忆不直接返回给用户，而是作为 **System Prompt 上下文** 供 LLM 回答时参考：

```python
async def build_context_from_results(
    results: list[Resource],
    llm: BaseLLMProvider,
    max_tokens: int = 2000,
) -> str:
    """
    将检索结果构建为上下文字符串
    """
    context_parts = []
    current_tokens = 0

    for r in results:
        # 构建单条记忆的文本表示（包含相关性分数）
        memory_text = f"[{r.category_name}] {r.description} (相关性: {r.score:.2f})"
        memory_tokens = await llm.count_tokens(memory_text)

        if current_tokens + memory_tokens > max_tokens:
            break

        context_parts.append(memory_text)
        current_tokens += memory_tokens

    return "\n".join(context_parts)
```

### 5.2 上下文格式说明

采用英文方括号 + 相关性分数的格式：

```
[项目研发] Python 数据分析项目进度：已完成数据清洗模块... (相关性: 0.92)
[核心自我] 小明对数据可视化特别感兴趣... (相关性: 0.85)
```

**格式优势**：
- 英文方括号在 JSON/Markdown 中更通用
- 相关性分数帮助 LLM 判断记忆重要性

### 5.3 Token 计算

使用 `llm.count_tokens()` 进行精确计算，而非字符估算：

```python
part_tokens = await llm.count_tokens(part)
```

**降级策略**：若 count_tokens 调用失败，使用 `len(part) // 4` 粗略估算。

### 5.4 System Prompt 示例

```
# 用户画像
{user_prompt_template}

# AI 人设
{agent_persona_template}

# 相关记忆（供参考）
{retrieved_context}

---

请根据以上信息回答用户的问题。
```

### 5.5 最终发送给 LLM 的内容

```
# 用户画像
用户小明，高中生，高二文科方向。

# AI 人设
你是小智，用户的学习导师。
性格：温柔耐心、严谨专业。
称呼用户"小明"，自称"小智"。

# 相关记忆（供参考）
[项目研发] Python 数据分析项目进度：已完成数据清洗模块，正在开发可视化部分。 (相关性: 0.92)
[项目研发] 项目截止日期为 3 月 30 日，需要完成报告撰写。 (相关性: 0.88)
[核心自我] 小明对数据可视化特别感兴趣，希望深入学习。 (相关性: 0.85)

---

用户问题：我的项目进度怎么样了？
```

### 5.6 ChatOrchestrator 上下文契约

真实 `/v1/chat` 不直接在路由层拼接检索上下文，而是通过 `services/chat_orchestrator.py` 统一编排：

```
system_prompt:
  assistant rules
  profile/persona
  memory-use priority rules

context:
  # Recent Conversation
  ...

  # Retrieved Memories
  ...

user_query:
  current user message only
```

优先级规则必须进入 system prompt：

```
When answering, prioritize information in this order:
1. The user's current message.
2. Relevant retrieved memories.
3. Stable user profile.
4. Assistant persona and style.

Use retrieved memories when they help answer the current message.
If the user's current message updates or contradicts older information, follow the current message.
Do not infer the user's current intent only from profile interests.
```

`ChatOrchestrator.build_context()` 可以返回 `trace` 给测试、评估和开发者调试使用。`trace` 至少包含：

| 字段 | 说明 |
|------|------|
| `retrieved_results` | 原始检索结果列表 |
| `retrieved_context` | 格式化后的检索上下文 |
| `recent_context` | 最近 pending conversation 上下文 |
| `context` | 最终传给 LLM 的 context |

`/v1/chat` 默认不把 `trace`、`retrieved_results` 或 `retrieved_context` 暴露给最终用户。

---

## 6. API 接口

### 6.1 POST /v1/retrieve

**请求**:
```json
{
    "user_id": "用户ID",
    "query": "用户查询",
    "top_k": 10,
    "min_importance": 3
}
```

**响应**:
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

### 6.2 GET /v1/retrieve/stats

获取检索统计信息，用于优化检索策略。

---

## 7. 性能优化

### 7.1 预过滤策略

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

### 7.2 缓存策略（规划中）

| 缓存类型 | 说明 | TTL | 状态 |
|----------|------|-----|------|
| 用户分类列表 | 用户的所有分类名 | 1 小时 | 规划中 |
| 热门记忆 | 高 importance 的记忆 | 30 分钟 | 规划中 |
| 查询结果缓存 | 相同查询的结果 | 5 分钟 | 规划中 |

> **状态**：缓存策略优先级为 P2，当前版本暂未实现。

---

## 8. 与其他模块的关系

| 本文档位置 | 相关模块 | 说明 |
|------------|----------|------|
| 上下文构建 | input-pipeline | user_prompt_template 加载机制 |
| 分类判断 | service-design | MemoryRetriever 实现 |
| 向量存储 | database-schema | Vector(1536) 字段 |
| LLM 调用 | llm-factory-design | generate_chat_response |

---

## 9. 实现优先级

| 优先级 | 功能 | 理由 |
|--------|------|------|
| P0 | LLM 分类判断 | 决定检索范围 |
| P0 | 分类内向量检索 | 核心检索能力 |
| P1 | 检索分数计算 | 必要的排序逻辑 |
| P1 | 上下文构建 | 连接检索与回答 |
| P2 | 缓存优化 | 性能提升 |
