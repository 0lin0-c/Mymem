
# 🗄️ 数据库持久化层与 ORM 设计说明书

## 1. 模块需求概述

本模块的核心目标是在 PostgreSQL 数据库中建立一套支持**异步高并发**与**高维向量检索 (`pgvector`)** 的记忆数据表。
并使用 SQLAlchemy 2.0+ 将底层的关系型表结构映射为 Python 的面向对象模型 (ORM)，为上层的记忆检索与写入服务提供稳定、类型安全的数据存取接口。

## 2. 核心架构与设计哲学 (Why We Do This)

* **全异步 I/O (asyncpg)**：AI Agent 系统的主要瓶颈在于大模型 API 请求和向量数据库检索。强制在底层引擎层采用全异步驱动，确保在等待数据库返回几万条高维向量比对结果时，主线程不会阻塞。

* **三层记忆结构**：
  * **Resource 表（对话摘要层）**：存储对话粒度的综合摘要与 1536 维向量。追求**语义检索能力**。
  * **Category 表（原子化记忆层）**：存储从对话中提取的原子化信息。每条记录属于一个分类（核心自我/情景时间轴/语义知识库/社交关系图谱/动态分类）。
  * **ResourceCategory 表（关联层）**：记录对话摘要与原子化记忆之间的关系，支持追踪每条记忆的完整历史来源。

* **UUID 主键约束**：所有表放弃使用自增 Integer 作为主键，强制使用 UUIDv4。这在未来如果需要进行数据库分库分表，或者进行离线数据迁移时，能彻底杜绝主键冲突。

---

## 3. 代码目录拓扑 (仅限数据库层)

本模块涉及的代码结构被严格限制在 `core/` 和 `tables/` 目录中：

```text
Mymem/
├── init_db.py               # [独立脚本] 用于首次连接 NAS 数据库执行 DDL 建表指令
├── core/
│   └── database.py          # [引擎配置] 负责初始化 asyncpg 连接池与 Session 工厂
└── tables/
    ├── base.py              # [ORM 基类] 提供 SQLAlchemy 的 DeclarativeBase
    ├── user.py              # [实体] 用户与全局人设表
    ├── category.py          # [实体] 原子化记忆表
    ├── resource.py          # [实体] 对话摘要表（含向量）
    └── resource_category.py # [实体] 记忆来源关联表

```
  ┌────────────────────┬───────────────────────────────────────────────────────────┐
  │        文件        │                           功能                            │
  ├────────────────────┼───────────────────────────────────────────────────────────┤
  │ core/config.py     │ 读取 .env 配置（数据库URL、LLM API Key、向量化维度 1536） │
  ├────────────────────┼───────────────────────────────────────────────────────────┤
  │ core/database.py   │ 异步引擎 + get_db() 依赖注入                              │
  ├────────────────────┼───────────────────────────────────────────────────────────┤
  │ tables/user.py     │ 用户表（含 user_prompt_template、agent_persona_template） │
  ├────────────────────┼───────────────────────────────────────────────────────────┤
  │ tables/category.py │ 原子化记忆表（含 category_name、content、importance_score）│
  ├────────────────────┼───────────────────────────────────────────────────────────┤
  │ tables/resource.py │ 对话摘要表（含 description_vector 向量字段）              │
  ├────────────────────┼───────────────────────────────────────────────────────────┤
  │ init_db.py         │ 执行 CREATE EXTENSION vector + 建表                       │
  └────────────────────┴───────────────────────────────────────────────────────────┘

---

## 4. 详细表结构与字段级设计

### 4.1 用户表 (`users`)

**功能定位**：系统的全局配置锚点。未来如果有多个用户共用该系统，此表用于实现数据和人设的绝对物理隔离。

| 字段名 (`Column`) | 数据类型 (`Type`) | 约束与属性 | 设计意图与功能 |
| --- | --- | --- | --- |
| `id` | `String` | `Primary Key`, 默认生成 UUID | 唯一标识。 |
| `username` | `String` | `Unique`, `Index` | 用于登录或身份识别的唯一代号。 |
| `password` | `String` | - | 用户登录密码（存储哈希值）。 |
| `user_prompt_template` | `Text` | `Nullable` | **替代传统的 `USER.md`**。存储该用户的全局客观画像。使用 Text 类型便于在数据库后台直接预览和调试。 |
| `agent_persona_template` | `Text` | `Nullable` | **替代传统的 `SOUL.md`**。存储当前助手的性格、语气指令。使用 Text 类型便于在数据库后台直接预览和调试。 |
| `created_at` | `DateTime` | `timezone=True`, 默认 `func.now()` | 记录账户/人设的初始创建时间。**强制带时区**，防止 NAS 环境与服务器时区不一致。 |
| `updated_at` | `DateTime` | `timezone=True`, 触发器自动更新 | **核心字段**。任何字段更新时自动更新。**强制带时区**。 |

### 4.2 对话摘要表 (`resources`)

**功能定位**：存储对话粒度的综合摘要。每条记录对应一次对话交互（如 5 轮对话的总结）。配合 `pgvector` 插件进行高维语义空间搜索。

| 字段名 (`Column`) | 数据类型 (`Type`) | 约束与属性 | 设计意图与功能 |
| --- | --- | --- | --- |
| `id` | `String` | `Primary Key`, 默认生成 UUID | 唯一标识。 |
| `user_id` | `String` | `ForeignKey('users.id', ondelete='CASCADE')`, `Index` | 绑定用户。`CASCADE` 确保注销用户时自动清理记忆残余。 |
| `modality` | `String` | 默认 `"text"` | **多模态扩展预留**。可填入 `"text"`, `"image"`, `"audio"`。 |
| `raw_content` | `Text` | - | 用户输入的原始文本（防篡改底稿）。 |
| `description` | `Text` | `Nullable` | LLM 生成的对话综合摘要（客观第三人称描述），用于向量化。 |
| `assistant_response` | `Text` | `Nullable` | AI 助手回复的摘要。 |
| `description_vector` | `Vector(1536)` | `pgvector` 专有类型，需启用扩展 | **语义检索核心**。存储由 OpenAI/特定模型生成的 1536 维向量。SQLAlchemy 使用 `pgvector.sqlalchemy.Vector` 映射。 |
| `importance_score` | `Integer` | 默认 `2` | 由 LLM 在入库前打分 (0-3)。检索默认不按重要性提前硬过滤，排序阶段通过可配置四因子评分使用该值。 |
| `access_count` | `Integer` | 默认 `0` | 被检索引用的次数。用于遗忘机制的访问加成计算。 |
| `created_at` | `DateTime` | `timezone=True`, 默认 `func.now()` | 记忆发生的确切时间戳。**强制带时区**。 |
| `updated_at` | `DateTime` | `timezone=True`, `Nullable` | 更新时间（合并/覆盖时更新，用于遗忘曲线计算）。**强制带时区**。 |

### 4.3 原子化记忆表 (`categories`)

**功能定位**：存储从对话摘要中提取的原子化信息。每条记录是一条独立的信息，归属一个固定的分类。

| 字段名 (`Column`) | 数据类型 (`Type`) | 约束与属性 | 设计意图与功能 |
| --- | --- | --- | --- |
| `id` | `String` | `Primary Key`, 默认生成 UUID | 唯一标识。 |
| `user_id` | `String` | `ForeignKey('users.id', ondelete='CASCADE')`, `Index` | 绑定用户。`CASCADE` 确保注销用户时自动清理记忆残余。 |
| `category_name` | `String` | `Index` | 归属的分类名（核心自我/情景时间轴/语义知识库/社交关系图谱/动态分类）。 |
| `content` | `Text` | - | 原子化的记忆内容（一条独立的信息）。 |
| `importance_score` | `Integer` | 默认 `2` | 该条信息的重要性评分 (0-3)。检索默认不按重要性提前硬过滤，排序阶段通过可配置四因子评分使用该值。 |
| `access_count` | `Integer` | 默认 `0` | 被检索引用的次数。用于遗忘机制的访问加成计算。 |
| `created_at` | `DateTime` | `timezone=True`, 默认 `func.now()` | 分类首次建立时间。**强制带时区**。 |
| `updated_at` | `DateTime` | `timezone=True`, 触发器自动更新 | 更新时间。**强制带时区**。 |

---

### 4.4 记忆来源关联表 (`resource_categories`)

**功能定位**：记录原子化记忆（Category）与对话摘要（Resource）之间的关系，支持追踪每条记忆的完整历史来源。

| 字段名 (`Column`) | 数据类型 (`Type`) | 约束与属性 | 设计意图与功能 |
| --- | --- | --- | --- |
| `id` | `String` | `Primary Key`, 默认生成 UUID | 唯一标识。 |
| `resource_id` | `String` | `ForeignKey('resources.id', ondelete='CASCADE')`, `Index` | 关联的对话摘要 ID。 |
| `category_id` | `String` | `ForeignKey('categories.id', ondelete='CASCADE')`, `Index` | 关联的原子化记忆 ID。 |
| `relation_type` | `String` | 默认 `"created"` | 关联类型：`created`/`updated`。 |
| `note` | `Text` | `Nullable` | 关联说明（可选）。 |
| `created_at` | `DateTime` | `timezone=True`, 默认 `func.now()` | 关联创建时间。**强制带时区**。 |

#### 关联类型说明

| 类型 | 说明 |
| --- | --- |
| `created` | 该 Resource 首次创建了这个原子化记忆 |
| `updated` | 该 Resource 更新了这个原子化记忆 |

> **重复提及的处理**：当用户重复提及某条记忆时，直接增加 `Category.importance_score`，不创建新的关联记录。

---

## 5. 表关系图

```
┌─────────────────┐         ┌──────────────────────┐         ┌─────────────────┐
│    Resource     │         │  resource_categories │         │    Category     │
│   (对话摘要)     │◄───────►│     (关联表)          │◄───────►│  (原子化记忆)    │
└─────────────────┘         └──────────────────────┘         └─────────────────┘
     1条                        多条关联                           多条
```

---

## 6. 基础设施文件功能规范

### 6.1 `core/database.py` (基础设施)

* **功能**：负责读取 NAS 数据库的连接字符串，实例化 SQLAlchemy 的 `AsyncEngine` 和 `async_sessionmaker`。
* **后续如何被调用**：在此文件内提供一个 `get_db()` 的异步生成器函数。后续在 FastAPI 的路由中，通过 `Depends(get_db)` 作为依赖注入，使得每个 HTTP 请求都能获得一个独立的、生命周期受控的数据库连接会话（Session），并在请求结束后自动关闭，防止内存泄漏。

### 6.2 `tables/base.py` (映射契约)

* **功能**：仅包含 `class Base(DeclarativeBase): pass`。
* **为什么独立出一个文件**：为了避免循环导入 (Circular Import)。所有的具体数据表模型必须继承自同一个 Base 对象，这样 SQLAlchemy 的 MetaData 才能收集到所有的表结构，从而执行统一的 `create_all` 建表操作。

### 6.3 `tables/*.py` (实体类)

* **功能**：利用 SQLAlchemy 2.0 的 `Mapped` 和 `mapped_column` 类型提示，清晰地定义字段约束。
* **后续如何被调用**：在业务逻辑层（如 `memory/writer.py`）中，我们不需要写 SQL 语句，而是通过 Repository 层的方法操作数据。

### 6.4 `init_db.py` (执行脚本)

* **功能**：一个极其简单的一次性脚本。它会导入所有的实体类，连接到 NAS 数据库，强制执行 `CREATE EXTENSION IF NOT EXISTS vector;` 激活向量大脑，随后通过 `Base.metadata.create_all` 向数据库发送 DDL (Data Definition Language) 语句，完成物理建表。
* **生命周期**：仅在项目环境搭建初期，或修改了表结构（且未使用 Alembic 迁移工具时）由开发者手动在终端执行一次。

---

## 7. Repository 层设计思路

### 7.1 Repository 模式定位

Repository 层作为**数据访问抽象**，位于 Service 层与 ORM 模型之间：
- **上层（Service）**：调用 Repository 提供的方法，专注业务逻辑，不直接接触 SQL
- **本层（Repository）**：封装所有 CRUD 操作，提供类型安全的数据接口
- **下层（ORM/SQLAlchemy）**：通过 AsyncSession 执行实际数据库操作

### 7.2 目录结构

```text
Mymem/
├── repositories/
│   ├── __init__.py              # 统一导出
│   ├── base.py                  # Repository 基类（封装通用 CRUD）
│   ├── user_repository.py       # 用户操作
│   ├── category_repository.py   # 原子化记忆操作
│   ├── resource_repository.py   # 对话摘要+向量操作
│   └── resource_category_repository.py # 关联关系操作
```

### 7.3 各 Repository 职责

#### UserRepository

| 方法 | 功能 |
|------|------|
| `create()` | 创建新用户 |
| `get_by_id()` | 通过 ID 获取用户 |
| `get_by_username()` | 通过用户名获取用户 |
| `update()` | 更新用户信息（人设模板等） |
| `delete()` | 删除用户（CASCADE 联动删除记忆） |

#### CategoryRepository

| 方法 | 功能 |
|------|------|
| `create_item()` | 创建一条原子化记忆 |
| `create_items_batch()` | 批量创建原子化记忆 |
| `get_by_id()` | 通过 ID 获取原子化记忆 |
| `get_by_user_id()` | 获取某用户所有原子化记忆 |
| `get_by_category_name()` | 获取某分类下所有原子化记忆 |
| `get_high_importance_items()` | 获取高重要性的原子化记忆 |
| `update_importance()` | 更新重要性分数 |
| `get_category_stats()` | 获取各分类的统计信息 |
| `search_by_content()` | 按内容关键词搜索 |
| `delete()` | 删除原子化记忆 |

#### ResourceRepository

| 方法 | 功能 |
|------|------|
| `create()` | 创建新对话摘要（含向量） |
| `get_by_id()` | 通过 ID 获取对话摘要 |
| `get_by_user_id()` | 获取某用户所有对话摘要 |
| `get_by_modality()` | 按模态筛选对话摘要 |
| `get_by_importance_range()` | 按重要性评分筛选 |
| `search_by_vector()` | **核心**：向量相似度检索 |
| `search_by_vector_in_category()` | 在指定分类内进行向量检索 |
| `update_description_vector()` | 更新描述和向量 |
| `update_importance()` | 更新重要性分数 |
| `update_content()` | 更新内容（合并/覆盖时使用） |
| `delete()` | 删除对话摘要 |
| `delete_by_user()` | 删除某用户的所有对话摘要 |

#### ResourceCategoryRepository

| 方法 | 功能 |
|------|------|
| `create_relation()` | 创建关联关系 |
| `create_relations_batch()` | 批量创建关联关系 |
| `get_categories_for_resource()` | 获取某对话摘要提取的所有原子化记忆 |
| `get_resources_for_category()` | 获取某原子化记忆的所有来源 |
| `get_relation()` | 获取特定的关联关系 |
| `delete()` | 删除关联 |
| `delete_by_resource()` | 删除某对话摘要的所有关联 |
| `delete_by_category()` | 删除某原子化记忆的所有关联 |

### 7.4 BaseRepository 通用设计

BaseRepository 作为所有 Repository 的基类，封装通用的 CRUD 操作：

- **初始化**：接收 `AsyncSession` 和 ORM 模型类
- **get_by_id**：通过主键获取单个实体
- **get_all**：分页获取所有实体（支持 skip/limit）
- **create**：创建新实体，flush 后返回
- **update**：更新实体字段（仅更新提供的字段），返回更新后的实体
- **delete**：通过 ID 删除实体，返回是否成功
- **exists**：检查实体是否存在

### 7.5 向量检索实现要点

`ResourceRepository.search_by_vector()` 的核心逻辑：

1. **使用 `<=>` 操作符**：pgvector 提供的余弦距离计算算子
2. **预过滤**：按 `user_id` 和 `importance_score` 筛选候选集
3. **向量比较**：将查询向量与 `description_vector` 比较距离
4. **排序返回**：按距离升序排列，限制 `top_k` 条数

> **注意**：向量字段使用 `Vector(1536)` 类型后，可直接在 SQL 中使用 `<=>` 操作符，无需手动编解码。

```python
async def search_by_vector(
    self,
    user_id: str,
    query_vector: bytes,
    top_k: int = 5,
    min_importance: int = 3
) -> list[Resource]:
    # 使用原生 SQL 配合 pgvector 的 ORDER BY cosine_distance
    sql = text("""
        SELECT *, (description_vector <=> :query_vector) AS cosine_distance
        FROM resources
        WHERE user_id = :user_id
          AND importance_score >= :min_importance
          AND description_vector IS NOT NULL
        ORDER BY cosine_distance ASC
        LIMIT :top_k
    """)
```

### 7.6 依赖注入方式

Repository 的实例化遵循以下流程：

1. FastAPI 路由通过 `Depends(get_db)` 获取 `AsyncSession`
2. Service 层接收 session，实例化所需的 Repository
3. Repository 通过 session 执行数据库操作
4. 请求结束后 session 自动关闭

---

这份文档完全聚焦于数据库层的"施工图纸"。你看这份设计是否符合你对底层数据结构的预期？如果有需要调整的字段，我们可以现在敲定；如果没有问题，下一步我们可以直接根据这份文档编写具体的 Python 代码了。
