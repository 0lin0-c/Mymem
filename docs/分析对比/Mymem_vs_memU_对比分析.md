# Mymem vs memU 对比分析

## 一、架构设计对比

| 维度 | Mymem | memU |
|------|-------|------|
| **核心隐喻** | 双轨记忆（Fast/Slow Track） | 文件系统（资源→条目→类别） |
| **层次结构** | 2 层：Resource + Category | 3 层：Resource → MemoryItem → MemoryCategory |
| **工作流引擎** | 无，硬编码流程 | 有，可插拔的 Pipeline 系统 |
| **存储后端** | PostgreSQL + pgvector | InMemory / SQLite / PostgreSQL 可切换 |

## 二、短期记忆对比

| 维度 | Mymem | memU |
|------|-------|------|
| **实现方式** | Session 的 `pending_chats` 列表 | 无独立短期记忆概念 |
| **上下文注入** | 最近 5 轮对话直接拼接 | 通过检索召回 |
| **压缩触发** | 5 轮后 LLM 生成摘要存入长期记忆 | 无显式压缩机制 |
| **超时处理** | 30 分钟无活动自动落库 | 无 |

**差异点评**：Mymem 有明确的短期→长期记忆流转机制，memU 则将所有记忆统一管理，通过显著性评分区分重要性。

## 三、长期记忆对比

| 维度 | Mymem | memU |
|------|-------|------|
| **记忆类型** | 4 类固定分类（核心自我/情景时间轴/语义知识库/社交关系图谱） | 6 种记忆类型（profile/event/knowledge/behavior/skill/tool） |
| **分类方式** | LLM 提取时自动归类到 4 大类 | 动态创建类别，LLM 持续更新类别摘要 |
| **原子化程度** | Category 存储原子化信息 | MemoryItem 是原子单位，更细粒度 |
| **去重机制** | 向量相似度 + LLM 判断（SKIP/MERGE/CREATE） | 内容哈希 + 强化计数 |

## 四、检索机制对比

| 维度 | Mymem | memU |
|------|-------|------|
| **检索模式** | 单一 RAG 模式 | 双模式：RAG + LLM Reasoning |
| **检索流程** | LLM 分类判断 → 分类内检索 → 向量兜底 | 类别检索 → 充分性检查 → 条目检索 → 充分性检查 → 资源检索 |
| **充分性检查** | 无 | 有，每层检索后判断是否足够 |
| **评分公式** | `Similarity × 0.6 + Importance × 0.4` | `Salience = Similarity × log(n+1) × e^(-Δt/τ)` |

**memU 优势**：充分性检查可在类别层就满足 ~40% 的查询，无需深入检索，节省计算成本。

## 五、遗忘机制对比

| 维度 | Mymem | memU |
|------|-------|------|
| **衰减公式** | `Importance × e^(-Days/(Importance×5)) × (1+log(Access+1))` | `e^(-ln2 × Δt / τ)`（半衰期衰减） |
| **强化机制** | 去重时 importance +1 | reinforcement_count 累加，显著性重算 |
| **排除分类** | 核心自我、社交关系图谱不参与遗忘 | 无显式排除 |

## 六、关键差异总结

### Mymem 的优点

1. **短期记忆机制完善**：明确的 Session 管理、上下文注入、自动落库
2. **双轨记忆清晰**：Fast Track（原子事实）+ Slow Track（综合摘要）
3. **重要性评分精细**：1-10 分，有明确的评分标准
4. **遗忘机制成熟**：考虑了重要性、时间、访问次数三个因子

### memU 的优点（值得学习的地方）

| 特性 | 说明 | 学习价值 |
|------|------|----------|
| **Workflow 引擎** | 可插拔的工作流系统，支持步骤替换、插入、删除、版本管理 | ⭐⭐⭐⭐⭐ 高度可扩展 |
| **充分性检查** | 每层检索后判断是否足够，可提前终止 | ⭐⭐⭐⭐⭐ 节省 LLM 调用成本 |
| **三层记忆模型** | Resource → MemoryItem → MemoryCategory，粒度更细 | ⭐⭐⭐⭐ 更好的溯源能力 |
| **6 种记忆类型** | profile/event/knowledge/behavior/skill/tool，分类更细 | ⭐⭐⭐ 更精细的记忆分类 |
| **动态类别摘要** | LLM 持续更新类别摘要，形成"活目录" | ⭐⭐⭐⭐ 检索效率更高 |
| **引用系统** | `[ref:ID]` 支持记忆间关联和溯源 | ⭐⭐⭐ 可追溯性 |
| **显著性评分** | 融合相似度、强化次数、时间衰减 | ⭐⭐⭐⭐ 更科学的评分 |
| **多后端支持** | InMemory/SQLite/PostgreSQL 可切换 | ⭐⭐⭐ 灵活部署 |
| **运行器注册** | 支持注册自定义工作流运行器（如 Temporal） | ⭐⭐⭐ 分布式扩展 |

---

## 七、值得 Mymem 学习的核心点

### 1. Workflow 引擎（最重要）

memU 的工作流引擎有以下特性：
- **步骤声明依赖**：每个步骤声明 `requires` 和 `produces`，系统自动验证依赖
- **运行时修改**：支持 `insert_after`、`insert_before`、`replace_step`、`remove_step`
- **版本管理**：每次修改自动创建新版本，可追溯
- **拦截器机制**：支持 before/after/on_error 三种拦截点

**应用场景**：Mymem 可以将 `memorize` 和 `retrieve` 流程改造为可配置的工作流，方便 A/B 测试不同策略。

### 2. 充分性检查

```python
# memU 的检索流程
1. 类别层检索 → LLM 判断："信息是否足够？"
   ├─ 足够 → 返回答案，跳过后续步骤
   └─ 不足 → 进入条目层检索
2. 条目层检索 → LLM 判断："信息是否足够？"
   ├─ 足够 → 返回答案
   └─ 不足 → 进入资源层检索
```

**应用场景**：Mymem 可以在 Category 检索后增加充分性判断，避免不必要的向量检索。

### 3. 显著性评分公式

```
memU: Salience = Similarity × log(reinforcement_count + 1) × e^(-ln2 × Δt / τ)
Mymem: Score = Similarity × 0.6 + (Importance / 10) × 0.4
```

memU 的公式更科学：
- **对数缩放**：防止高频记忆分数失控
- **半衰期衰减**：τ=30 天，30 天后权重减半
- **强化感知**：被重复提及的记忆权重更高

### 4. 三层记忆模型

```
memU:
Resource (原始资源)
    ↓ 提取
MemoryItem (原子记忆，6种类型)
    ↓ 聚合
MemoryCategory (动态类别，LLM 更新摘要)

Mymem:
Resource (对话摘要 + 向量)
    ↓ 提取
Category (原子化信息，4 大类)
```

memU 的 MemoryItem 额外记录了 `memory_type`，可以区分"用户说过什么"和"用户做过什么"。

### 5. 动态类别摘要

memU 的每个 Category 有一个 `summary` 字段，由 LLM 持续更新：

```python
# 类别摘要示例
Category: "habits"
Summary: "The user exercises regularly, preferring morning workouts at 6 AM.
          They follow a vegetarian diet and enjoy reading before bed."
```

检索时先匹配类别摘要，命中后再检索具体条目。Mymem 的 Category 只有 `content`（单条原子信息），没有聚合摘要。

---

## 八、建议优先学习顺序

| 优先级 | 特性 | 理由 |
|--------|------|------|
| 1 | **充分性检查** | 改动小，收益大，可立即降低 LLM 调用成本 |
| 2 | **动态类别摘要** | 提升检索效率，需要在 Category 表增加 `summary` 字段 |
| 3 | **显著性评分公式** | 替换现有评分，更科学 |
| 4 | **Workflow 引擎** | 架构级改造，长期收益，但工作量大 |
| 5 | **引用系统** | 增强可追溯性，可选 |
| 6 | **三层记忆模型** | 需要重构数据模型，成本最高 |

---

## 九、核心数据模型对比

### Mymem 数据模型

```python
# Resource 表 - 对话粒度的综合摘要
class Resource:
    id: str
    user_id: str
    description: str           # 综合摘要
    description_vector: list   # 1536 维向量
    importance_score: int      # 1-10
    access_count: int
    modality: str              # text/image/video/voice/document

# Category 表 - 原子化记忆
class Category:
    id: str
    user_id: str
    category_name: str         # 核心自我/情景时间轴/语义知识库/社交关系图谱
    content: str               # 单条原子信息
    importance_score: int
    is_fixed: bool             # 是否为基线记忆
```

### memU 数据模型

```python
# Resource 表 - 原始资源元数据
class Resource:
    id: str
    name: str
    uri: str
    content_type: str          # conversation/document/image/video/audio
    caption: str               # LLM 生成的描述
    embedding: list            # caption 的向量

# MemoryItem 表 - 原子记忆单元
class MemoryItem:
    id: str
    category_id: str
    memory_type: str           # profile/event/knowledge/behavior/skill/tool
    summary: str               # 记忆内容
    embedding: list            # 向量
    salience: float            # 显著性评分
    reinforcement_count: int   # 强化次数
    reference: str             # 引用的资源 ID

# MemoryCategory 表 - 记忆类别
class MemoryCategory:
    id: str
    name: str
    description: str
    memory_type: str
    summary: str               # LLM 持续更新的类别摘要
    embedding: list            # 摘要向量
    size: int                  # 包含的记忆项数量
```

---

## 十、检索流程对比图

### Mymem 检索流程

```
用户查询
    ↓
LLM 分类判断 → 判断 query 属于哪些分类
    ↓
分类内检索 → 在指定分类中向量检索
    ↓ (结果不足)
向量兜底 → 全局向量检索
    ↓
去重排序 → 按 resource_id 去重，按分数排序
    ↓
阈值过滤 → 相似度 < 0.55 的过滤掉
    ↓
返回 Top-K 结果
```

### memU 检索流程

```
用户查询
    ↓
route_intention → LLM 判断是否需要检索 + 查询重写
    ↓ needs_retrieval=True
route_category → 向量检索 Top-K 类别（基于摘要嵌入）
    ↓
sufficiency_after_category → LLM 判断类别信息是否足够
    ├─ 足够 → 返回答案（跳过后续步骤）
    └─ 不足 → 继续
    ↓
recall_items → 向量检索 Top-K 条目（支持 salience 排序）
    ↓
sufficiency_after_items → LLM 判断条目信息是否足够
    ├─ 足够 → 返回答案
    └─ 不足 → 继续
    ↓
recall_resources → 向量检索 Top-K 原始资源
    ↓
build_context → 组装最终响应
```

---

*本分析基于 memU 项目 v0.1.0 版本和 Mymem 项目当前状态，于 2026 年 4 月整理。*
