# Retrieval 模块

本文档定义检索服务的设计规范。

> **详细流程设计**：详见 `retrieval-pipeline` skill

---

## 1. LLM 驱动的双层检索

```
用户查询
    │
    ▼
┌─────────────────────────────────────┐
│ 1. LLM 分类判断                      │
│    "这个问题属于哪些类别？"           │
│    → 动态输出 1-N 个相关类别         │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 2. Category 层向量检索（第一层）     │
│    在 LLM 指定的类别中检索 Category  │
│    按 content_vector 相似度排序      │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 3. LLM 充足性判断                    │
│    "这些记忆足够回答问题吗？"         │
│    → 足够：直接构建上下文            │
│    → 不足：进入 Resource 层检索       │
└─────────────────────────────────────┘
    │ (不足时)
    ▼
┌─────────────────────────────────────┐
│ 4. Resource 层向量检索（第二层）     │
│    根据已检索 Category 关联的 Resource │
│    按 description_vector 相似度排序   │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 5. 结果合并与上下文构建              │
│    合并两层检索结果作为 system prompt │
│    供 LLM 回答时参考                 │
└─────────────────────────────────────┘
```

> **详细流程设计**：详见 `retrieval-pipeline` skill

---

## 2. MemoryRetriever 接口

```python
class MemoryRetriever:
    """记忆检索器"""

    async def _classify_query(
        self,
        user_id: str,
        query: str,
    ) -> list[str]:
        """
        LLM 判断查询属于哪些类别
        动态获取用户的分类列表，返回相关类别名称
        """
        pass

    async def _search_category_layer(
        self,
        user_id: str,
        categories: list[str],
        query: str,
        top_k: int,
    ) -> list[dict]:
        """
        Category 层向量检索（第一层）
        使用 content_vector 相似度 + 检索分数排序
        """
        pass

    async def _check_sufficiency(
        self,
        query: str,
        category_results: list[dict],
    ) -> bool:
        """
        LLM 判断 Category 层结果是否足够回答问题
        """
        pass

    async def _search_resource_layer(
        self,
        user_id: str,
        categories: list[str],
        query: str,
        top_k: int,
    ) -> list[dict]:
        """
        Resource 层向量检索（第二层）
        根据分类关联检索 Resource，使用 description_vector 相似度排序
        """
        pass

    async def build_context(
        self,
        user_id: str,
        query: str,
        max_tokens: int = 2000,
    ) -> str:
        """
        执行检索并将结果构建为上下文字符串
        供 System Prompt 使用
        """
        pass
```

> **注意**：内部方法为私有方法，外部调用使用 `retrieve()` 或 `build_context()`。

---

## 3. 动态类别判断

**特点**：LLM 根据问题复杂度决定类别数量，而非固定值。

| 问题类型 | 类别数量 | 示例 |
|----------|----------|------|
| 单一明确 | 1 个 | "我的项目进度" → [项目研发] |
| 多维度 | 2-3 个 | "我最近学习情况怎么样" → [核心自我, 考试与升学] |
| 开放式 | 可能多个 | "帮我回顾一下最近的事" → [情景时间轴, 核心自我] |

---

## 4. 检索分数计算

四因子乘法评分：

```
score = cosine_similarity × log(access_count + 1) × exp(-0.693 × days_ago / 60) × (importance_score / 5)
```

详见 `retrieval-pipeline/config/scoring.md`。

---

## 5. 上下文构建

检索结果作为 System Prompt 上下文：

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
