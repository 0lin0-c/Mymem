# Mymem 项目架构文档

## 目录结构

```
Mymem/
│
├── main.py                  # 🚀 全局入口：启动 FastAPI 实例，挂载路由，配置 CORS 和异常处理
│
├── core/                    # ⚙️ 基础设施层：系统运行的底层支撑
│   ├── config.py            # 配置管理：读取 .env 环境变量
│   └── database.py          # 数据库引擎：PostgreSQL 异步连接池 + Session 工厂
│
├── tables/                  # 🗄️ Model 层：SQLAlchemy ORM 实体定义
│   ├── base.py              # DeclarativeBase 基类
│   ├── user.py              # 用户表（含 user_prompt_template、agent_persona_template）
│   ├── resource.py          # 对话摘要表（含 description_vector 向量字段）
│   ├── category.py          # 原子化记忆表
│   └── resource_category.py # 记忆来源关联表
│
├── schemas/                 # 📝 Schema 层：Pydantic 数据校验与 API 契约
│   ├── auth_schema.py       # 认证相关
│   ├── chat_schema.py       # 对话请求/响应
│   ├── llm_schema.py        # LLM 结构化输出
│   ├── llm_settings_schema.py # LLM 配置
│   ├── onboarding_schema.py # 用户初始化表单
│   ├── retrieve_schema.py   # 检索请求/响应
│   └── user_schema.py       # 用户信息
│
├── repositories/            # 📦 Repository 层：数据访问抽象
│   ├── base.py              # 通用 CRUD 基类
│   ├── user_repository.py   # 用户操作
│   ├── resource_repository.py # 对话摘要 + 向量检索
│   ├── category_repository.py # 原子化记忆操作
│   └── resource_category_repository.py # 关联关系操作
│
├── services/                # 🧠 Service 层：核心业务逻辑
│   │
│   ├── llm/                 # 🤖 LLM 中枢服务
│   │   ├── base.py          # BaseLLMProvider 抽象基类
│   │   ├── factory.py       # LLMFactory 工厂（全局配置）
│   │   ├── user_llm_factory.py # UserLLMFactory（用户级配置）
│   │   ├── openai_sdk.py    # OpenAI 适配器
│   │   ├── anthropic_sdk.py # Anthropic 适配器
│   │   └── tools.py         # Prompt 构建、Tool 定义、向量计算
│   │
│   ├── memory/              # 💾 记忆写入服务
│   │   ├── writer.py        # MemoryWriter 统一入口
│   │   ├── deduplicator.py  # 记忆去重逻辑
│   │   ├── dedup_config.py  # 去重阈值配置
│   │   ├── lifecycle.py     # 遗忘机制与生命周期管理
│   │   └── handlers/        # 多模态处理器
│   │       ├── base.py
│   │       ├── text_handler.py
│   │       ├── image_handler.py
│   │       ├── video_handler.py
│   │       ├── voice_handler.py
│   │       └── document_handler.py
│   │
│   ├── retrieval/           # 🔍 检索服务
│   │   ├── base.py          # RetrievalStrategy 抽象基类
│   │   ├── retriever.py     # MemoryRetriever 主入口
│   │   └── vector_strategy.py   # 向量检索策略
│   │
│   ├── session/             # 📋 会话管理服务
│   │   ├── state.py         # SessionState、PendingChat 数据类
│   │   ├── session_manager.py # 会话状态管理
│   │   ├── user_identifier.py # 用户识别服务
│   │   ├── flush_service.py   # 缓存刷库服务
│   │   └── redis_store.py     # Redis 存储实现
│   │
│   ├── oss/                 # ☁️ 对象存储服务
│   │   ├── base.py          # BaseOSSClient 抽象基类
│   │   ├── local_client.py  # 本地文件存储
│   │   └── aliyun_client.py # 阿里云 OSS
│   │
│   ├── prompts/             # 📄 Prompt 模板
│   │   ├── chat_prompt.py
│   │   ├── memory_prompt.py
│   │   ├── lifecycle_prompt.py
│   │   └── onboarding_prompt.py
│   │
│   ├── profile_service.py   # 👤 用户画像服务（冷启动）
│   └── memory_retriever.py  # 🔍 记忆检索入口（兼容旧接口）
│
├── api/                     # 🚪 API 层：HTTP 路由
│   ├── dependencies.py      # 依赖注入（get_db、get_llm_service 等）
│   └── v1/                  # API v1 版本
│       ├── auth.py          # 认证接口
│       ├── chat.py          # 对话接口
│       ├── memory.py        # 记忆管理接口
│       ├── profile.py       # 用户画像接口
│       ├── retrieve.py      # 检索接口
│       └── llm_settings.py  # LLM 配置接口
│
├── frontend/                # 🖥️ 前端预览相关
│   └── preview_screenshots.py
│
├── scripts/                 # 🔧 脚本工具
│   ├── init_db.py           # 数据库初始化
│   ├── query_db.py          # 数据库查询
│   ├── fix_persona_template.py # 修复人设模板
│   └── test_chat_cli.py     # 命令行测试工具
│
├── tests/                   # 🧪 测试用例
│   ├── conftest.py          # pytest 配置
│   ├── test_tables.py
│   ├── test_repositories.py
│   ├── test_api/
│   └── test_services/
│
├── tests/performance/       # 📊 手动性能/诊断脚本（perf_*.py，不被默认 pytest 收集）
│   ├── perf_async_timing.py
│   └── perf_onboarding_performance.py
│
├── storage/                 # 📁 本地文件存储目录
│
└── data/                    # 📊 数据文件目录
```

---

## 五层架构设计

系统采用严格的五层架构，数据流像瀑布一样逐层传递，遵循"单向依赖"原则：

```
┌─────────────────────────────────────────────────────────────┐
│                        API Layer                             │
│                    api/v1/{chat,memory,profile,...}          │
│                    只负责请求校验和响应封装                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Schema Layer                            │
│                    Pydantic Models                           │
│                    定义进出系统的数据格式                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Service Layer                           │
│    ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│    │  Memory  │ │ Session  │ │Retrieval │ │   LLM    │      │
│    │  Writer  │ │ Manager  │ │ Strategy │ │ Factory  │      │
│    └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
│                    所有业务逻辑的唯一所在地                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Repository Layer                          │
│        UserRepository / ResourceRepository / CategoryRepo    │
│                    数据访问的唯一入口                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Model Layer                             │
│              User / Resource / Category / ResourceCategory   │
│                    SQLAlchemy ORM 实体定义                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    PostgreSQL + pgvector                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 层级职责

### 1. API 层（接入层）

**核心组件**：`main.py`, `api/` 目录

**职责**：系统的"迎宾员"
- 接收 HTTP 请求
- 通过 `dependencies.py` 进行鉴权和获取依赖
- 提取请求参数，调用 Service 层
- 封装响应返回给客户端

**规则**：
- ❌ 禁止包含业务逻辑
- ❌ 禁止直接操作数据库
- ✅ 只负责路由和校验

### 2. Schema 层（数据契约层）

**核心组件**：`schemas/` 目录（基于 Pydantic）

**职责**：系统的"海关"
- 严查所有进出系统的数据格式
- 定义 API 请求/响应体
- 定义 LLM 结构化输出格式

**设计亮点**：
- 将前端交互格式与 LLM 交互格式物理隔离
- 保证 API 变更不影响内部逻辑

### 3. Service 层（业务逻辑层）

**核心组件**：`services/` 目录

**职责**：系统的"大脑"，承载所有核心业务逻辑

| 模块 | 职责 |
|------|------|
| `llm/` | 大模型调用中枢，工厂模式抹平不同 SDK 差异 |
| `memory/` | 记忆写入、去重、生命周期管理 |
| `retrieval/` | LLM 分类判断 + 向量检索 |
| `session/` | 会话状态管理、用户识别、缓存刷库 |
| `oss/` | 对象存储抽象 |
| `prompts/` | Prompt 模板管理 |

**规则**：
- ✅ 编排业务逻辑
- ✅ 调用 Repository 或其他 Service
- ❌ 禁止直接操作 ORM 模型

### 4. Repository 层（数据访问层）

**核心组件**：`repositories/` 目录

**职责**：数据访问的唯一入口
- 封装所有 CRUD 操作
- 提供类型安全的数据接口
- 实现向量检索逻辑

**规则**：
- 使用 SQLAlchemy `select()` 语法
- 例外：`VectorStrategy` 使用原始 SQL 调用 pgvector

### 5. Model 层（实体层）

**核心组件**：`tables/` 目录

**职责**：ORM 实体定义
- 将 Python 对象映射到数据库表
- 定义字段约束和关系

---

## 核心数据流

### 对话处理流程

```
POST /v1/chat
        │
        ▼
┌─────────────────────────────────────────────────────┐
│ 1. API 层：获取会话、校验用户                         │
│    Depends(get_session_state) / Depends(get_current_user) │
└─────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────┐
│ 2. Service 层：检索相关记忆                          │
│    MemoryRetriever.build_context()                  │
│    → LLM 分类判断 → 分类内向量检索                   │
└─────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────┐
│ 3. Service 层：生成回复                              │
│    LLMFactory.get_provider().generate_chat_response()│
└─────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────┐
│ 4. Service 层：缓存对话（异步写入）                   │
│    SessionManager.add_pending_chat()                │
│    → chat 模态满 5 轮触发批量存储                    │
└─────────────────────────────────────────────────────┘
        │
        ▼
    ChatResponse
```

### 记忆写入流程

```
MemoryWriter.save_chat()
        │
        ▼
┌─────────────────────────────────────────────────────┐
│ 1. Handler 预处理                                    │
│    TextHandler / ImageHandler / VoiceHandler ...    │
└─────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────┐
│ 2. LLM 提取记忆意图                                  │
│    extract_memory_intent() → 分类、摘要、重要性      │
└─────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────┐
│ 3. 向量化                                            │
│    get_embedding() → 1536 维向量                    │
└─────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────┐
│ 4. 记忆去重                                          │
│    Deduplicator.check_and_dedup()                   │
│    → skip / merge / update / create                 │
└─────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────┐
│ 5. 持久化                                            │
│    ResourceRepository / CategoryRepository          │
└─────────────────────────────────────────────────────┘
```

---

## 技术栈

| 层级 | 技术 |
|------|------|
| Web 框架 | FastAPI (异步) |
| ORM | SQLAlchemy 2.0+ (异步) |
| 数据库 | PostgreSQL + pgvector |
| LLM SDK | OpenAI SDK, Anthropic SDK |
| 向量维度 | 1536 (text-embedding-3-small) |
| 缓存 | Redis (Session 存储) |
| 对象存储 | 本地存储 / 阿里云 OSS |

---

## 编码规范

- **全异步**：所有 I/O 操作使用 `await` 和 `AsyncSession`
- **禁止 print()**：使用 `logging` 模块
- **禁止硬编码密钥**：所有配置通过 `core/config.py` 的 Settings 从 `.env` 读取
- **向量存储**：`description_vector` 使用 pgvector 的 `Vector(1536)` 类型
- **层级隔离**：API 层禁止直接调用 Repository，必须通过 Service 层
