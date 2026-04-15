# 🏗️ Service 层架构设计

## 1. 整体目录结构

```
services/
├── llm/                    # 大模型服务
│   ├── __init__.py
│   ├── base.py             # BaseLLMProvider 抽象基类
│   ├── factory.py          # LLMFactory 工厂
│   ├── openai_sdk.py       # OpenAI 适配器
│   └── anthropic_sdk.py    # Anthropic 适配器
│
├── memory/                 # 记忆服务
│   ├── __init__.py
│   ├── writer.py           # MemoryWriter 写入服务
│   └── handlers/           # 模态处理器
│       ├── __init__.py
│       ├── base.py         # Handler 抽象基类
│       ├── text_handler.py
│       ├── image_handler.py
│       ├── video_handler.py
│       ├── voice_handler.py
│       └── document_handler.py
│
├── retrieval/              # 检索服务
│   ├── __init__.py
│   ├── base.py             # RetrievalStrategy 抽象基类
│   ├── retriever.py         # MemoryRetriever 检索服务
│   └── vector_strategy.py
│
├── session/                # 会话服务
│   ├── __init__.py
│   ├── state.py            # SessionState, PendingChat 数据类
│   ├── session_manager.py  # 会话状态管理
│   └── user_identifier.py  # 用户识别服务
│
├── oss/                    # 对象存储服务
│   ├── __init__.py
│   ├── base.py             # BaseOSSClient 抽象基类
│   └── local_client.py     # 本地存储实现
│
└── prompts/                # Prompt 模板
    ├── __init__.py
    ├── chat_prompt.py
    └── memory_prompt.py
```

---

## 2. LLM 模块 (`services/llm/`)

详见 [LLM_FACTORY_DESIGN.md](./LLM_FACTORY_DESIGN.md)

**核心接口**：
- `generate_chat_response()` - 生成对话回复
- `get_embedding()` - 生成文本向量
- `extract_memory_intent()` - 提取记忆意图

---

## 3. Memory 模块 (`services/memory/`)

### 3.1 MemoryWriter

记忆写入的统一入口，负责协调 Handler 完成写入流程。

```
save_chat(user_id, user_input, assistant_response, modality)
         ↓
    get_handler(modality) → 获取对应 Handler
         ↓
    handler.preprocess(user_input) → 统一转为文本
         ↓
    handler.store_raw_content(user_input) → 存储原始内容
         ↓
    handler.extract_intent() → LLM 提取意图
         ↓
    handler.get_vector() → LLM 生成向量
         ↓
    创建/更新 Category
         ↓
    创建 Resource
         ↓
    建立关联
```

### 3.2 Handler 基类

```python
class BaseHandler(ABC):
    """模态处理器基类"""

    @property
    @abstractmethod
    def supported_modality(self) -> str:
        """返回支持的模态类型"""
        pass

    @abstractmethod
    async def preprocess(self, content: Any) -> str:
        """预处理：将原始内容转为文本描述"""
        pass

    @abstractmethod
    async def get_vector(self, text: str) -> bytes:
        """将文本转为向量"""
        pass

    @abstractmethod
    async def store_raw_content(self, content: Any) -> str:
        """存储原始内容（文本直接返回，文件上传到 OSS）"""
        pass
```

> **注意**：意图提取已统一由 `MemoryWriter` 通过 `LLMProvider.extract_memory_intent()` 实现，Handler 不再单独处理。

### 3.3 异步写入工作流（Memory Backstage）

**痛点**：save_chat 流程（预处理 → 提取意图 → 生成向量 → 落库）是一个漫长的同步链条。如果放在对话主路径中，用户会感到明显的卡顿。

**解决方案**：将 save_chat 设计为任务分发器，采用三层架构：

| 层级 | 职责 | 耗时 |
|------|------|------|
| **即时层 (Hot)** | SessionManager 暂存原始对话 | ~1ms |
| **异步层 (Warm)** | BackgroundTasks 或 Celery 执行意图提取、向量化 | ~500ms-2s |
| **持久层 (Cold)** | Handler 完成处理后正式入库并建立关联 | ~50ms |

```
用户对话 → SessionManager 缓存（即时返回）
                ↓
        BackgroundTasks 触发
                ↓
        ┌─────────────────────────────┐
        │ 后台异步执行：               │
        │   ├─ extract_intent (LLM)   │
        │   ├─ get_vector (LLM)       │
        │   ├─ 创建 Category          │
        │   ├─ 创建 Resource          │
        │   └─ 建立关联               │
        └─────────────────────────────┘
```

**触发条件**：
- 定量触发：`chat_count >= 5`
- 定时触发：`last_active_at > 30min` 且缓存非空
- 指令触发：用户说"再见"或手动保存

---

### 3.4 Handler 实现状态

| Handler | 功能 | 状态 |
|---------|------|------|
| `TextHandler` | 文本预处理 + 摘要生成 | ✅ 完整实现 |
| `ImageHandler` | 图片 OCR/VLM 描述 | 🔜 骨架 |
| `VideoHandler` | 帧抽取 + 场景识别 | 🔜 骨架 |
| `VoiceHandler` | ASR 语音转文字 | 🔜 骨架 |
| `DocumentHandler` | PDF/Word 解析 | 🔜 骨架 |

---

## 4. Session 模块 (`services/session/`)

### 4.1 核心数据结构

```python
@dataclass
class SessionState:
    """单个会话的完整状态"""
    session_id: str
    user_id: str | None           # None 表示尚未识别
    user_name: str | None
    chat_count: int = 0           # 累积的 chat 轮数
    pending_chats: list[PendingChat]
    created_at: datetime          # 会话创建时间
    last_active_at: datetime      # 最后活跃时间，用于定时落库判断

    # 用户识别相关
    is_identified: bool = False
    identification_attempts: int = 0

@dataclass
class PendingChat:
    """待存储的单轮对话"""
    user_input: str
    assistant_response: str
    timestamp: datetime
```

### 4.2 SessionManager 与存储抽象

**痛点**：目前 SessionManager 是内存实现。如果部署在多台服务器或 Docker 重启，内存中的 PendingChat 会丢失。

**解决方案**：提供 `BaseSessionStore` 抽象基类：

```python
class BaseSessionStore(ABC):
    """Session 存储抽象基类"""

    @abstractmethod
    async def get(self, session_id: str) -> SessionState | None:
        pass

    @abstractmethod
    async def set(self, session_id: str, state: SessionState) -> None:
        pass

    @abstractmethod
    async def delete(self, session_id: str) -> None:
        pass
```

**实现对比**：

| 实现类 | 适用场景 | 特点 |
|--------|----------|------|
| `LocalSessionStore` | 开发/单机部署 | 内存存储，简单快速 |
| `RedisSessionStore` | 生产/分布式部署 | 支持分布式、自动过期、持久化 |

### 4.3 SessionManager 接口

| 方法 | 功能 |
|------|------|
| `get_or_create(session_id)` | 获取或创建会话 |
| `add_pending_chat()` | 添加待存储对话 |
| `clear_pending_chats()` | 清空并返回待存储对话 |
| `set_user()` | 设置用户身份 |
| `cleanup_expired()` | 清理过期会话 |

### 4.4 UserIdentifier

用户识别服务：

| 方法 | 功能 |
|------|------|
| `identify_or_ask()` | 识别用户或询问身份 |

**识别逻辑**：
1. 提取 Metadata (JWT / DeviceID / SessionID)
2. 未绑定 UserID → LLM 引导询问身份
3. 匹配数据库：已有用户直接识别，新用户自动创建
4. 成功后下发加密 Cookie/Token，后续请求静默识别

---

## 5. Retrieval 模块 (`services/retrieval/`)

### 5.1 LLM 驱动的串行检索

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
│ 2. 分类内检索                        │
│    只在 LLM 指定的类别中检索          │
│    按 importance_score + 向量相似度  │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 3. 结果作为上下文                    │
│    检索到的记忆作为 system prompt    │
│    上下文供 LLM 回答时参考           │
└─────────────────────────────────────┘
```

### 5.2 MemoryRetriever 接口

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

    async def _search_in_categories(
        self,
        user_id: str,
        categories: list[str],
        query: str,
        top_k: int,
        min_importance: int = 3,
    ) -> list[dict]:
        """
        在指定类别内检索
        使用向量相似度 + importance_score 综合排序
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

> **注意**：`_classify_query` 和 `_search_in_categories` 为内部方法，外部调用使用 `retrieve()` 或 `build_context()`。

### 5.3 动态类别判断

**特点**：LLM 根据问题复杂度决定类别数量，而非固定值。

| 问题类型 | 类别数量 | 示例 |
|----------|----------|------|
| 单一明确 | 1 个 | "我的项目进度" → [项目研发] |
| 多维度 | 2-3 个 | "我最近学习情况怎么样" → [核心自我, 考试与升学] |
| 开放式 | 可能多个 | "帮我回顾一下最近的事" → [情景时间轴, 核心自我] |

### 5.4 策略对比

| 策略 | 检索方式 | 适用场景 |
|------|---------|---------|
| `VectorStrategy` | pgvector 四因子评分 | 语义相似度搜索 |

---

## 6. OSS 模块 (`services/oss/`)

### 6.1 OSS 客户端接口

```python
class BaseOSSClient(ABC):
    """对象存储客户端基类"""

    @abstractmethod
    async def upload(
        self,
        file_content: bytes,
        filename: str,
        modality: str,
        user_id: str,
    ) -> str:
        """上传文件，返回存储路径"""
        pass

    @abstractmethod
    async def download(self, path: str) -> bytes:
        """下载文件"""
        pass

    @abstractmethod
    async def get_url(self, path: str, expire_seconds: int = 3600) -> str:
        """获取临时访问 URL"""
        pass

    @abstractmethod
    async def delete(self, path: str) -> bool:
        """删除文件"""
        pass
```

### 6.2 存储路径命名规范

**格式**：`{user_id}/{modality}/{yyyy-mm-dd}/{uuid}.{ext}`

**示例**：
```
a1b2c3d4-e5f6-7890-abcd-ef1234567890/
├── text/
│   └── 2024-03-20/
│       └── 550e8400-e29b-41d4-a716-446655440000.json
├── image/
│   └── 2024-03-21/
│       └── 660f9511-f39c-52e5-b827-557766551111.png
└── voice/
    └── 2024-03-22/
        └── 770fa622-g40d-63f6-c938-668877662222.mp3
```

**设计意图**：
- 按 `user_id` 隔离：便于用户数据导出/删除（GDPR 合规）
- 按 `modality` 分类：便于存储审计和容量统计
- 按 `yyyy-mm-dd` 分区：便于数据清洗和冷热分离

### 6.3 实现状态

| 客户端 | 说明 | 状态 |
|--------|------|------|
| `LocalOSSClient` | 本地文件存储（开发用） | ✅ 已实现 |
| `AliyunOSSClient` | 阿里云 OSS | ✅ 已实现 |

---

## 7. 监控与度量

### 7.1 核心指标

| 指标 | 说明 | 告警阈值 |
|------|------|----------|
| **LLM Latency** | 意图提取的平均耗时 | > 3s |
| **Vector Accuracy** | 用户对检索结果的反馈（点赞/点踩） | 点赞率 < 70% |
| **Storage Overhead** | 各模态文件在 OSS 中的占用比例 | 单用户 > 1GB |
| **Session TTL** | 会话平均存活时间 | - |
| **Pending Flush** | 待落库对话积压数量 | > 100 条 |

### 7.2 埋点位置

| 模块 | 埋点方法 | 记录指标 |
|------|----------|----------|
| `Memory` | `MemoryWriter.save_chat()` | 写入耗时、意图提取耗时 |
| `Retrieval` | `MemoryRetriever.retrieve()` | 检索耗时、结果数量 |
| `Session` | `SessionManager.add_pending_chat()` | 缓存命中率、会话时长 |
| `LLM` | `BaseLLMProvider.generate_chat_response()` | LLM 响应时间 |

---

## 8. 完成情况

### 7.1 已完成

**LLM 模块**
- [x] `BaseLLMProvider` 抽象基类
- [x] `LLMFactory` 工厂模式
- [x] `OpenAIProvider` 适配器
- [x] `AnthropicProvider` 适配器

**Memory 模块**
- [x] `MemoryWriter.save_chat()` 完整流程
- [x] `BaseHandler` 抽象基类
- [x] `TextHandler` 完整实现
- [x] Image/Video/Voice/Document Handler 骨架

**Session 模块**
- [x] `SessionState`, `PendingChat` 数据结构
- [x] `SessionManager` 会话管理
- [x] `UserIdentifier` 用户识别

**Retrieval 模块**
- [x] `RetrievalStrategy` 抽象基类
- [x] `VectorStrategy` 向量检索
- [x] `MemoryRetriever` 双层检索（Category 层 + Resource 层）

**OSS 模块**
- [x] `BaseOSSClient` 抽象基类
- [x] `LocalOSSClient` 本地存储

### 7.2 待扩展

- [ ] `AliyunOSSClient` 阿里云 OSS 实现
- [ ] `ImageHandler` 完整实现（VLM/OCR）
- [ ] `VoiceHandler` 完整实现（ASR）
- [ ] `VideoHandler` 完整实现（帧抽取 + VLM）
- [ ] `DocumentHandler` 完整实现（PDF/Word 解析）
