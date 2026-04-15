# Session 模块

本文档定义会话服务的设计规范。

> **详细流程设计**：详见 `input-pipeline` skill 第 2 节（用户识别）、第 4 节（缓存机制）

---

## 1. 核心数据结构

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

---

## 2. SessionManager 与存储抽象

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

---

## 3. SessionManager 接口

| 方法 | 功能 |
|------|------|
| `get_or_create(session_id)` | 获取或创建会话 |
| `add_pending_chat()` | 添加待存储对话 |
| `clear_pending_chats()` | 清空并返回待存储对话 |
| `set_user()` | 设置用户身份 |
| `cleanup_expired()` | 清理过期会话 |

---

## 4. UserIdentifier

用户识别服务：

> **详细流程设计**：详见 `input-pipeline` skill 2.1 节（增强型用户识别）

| 方法 | 功能 |
|------|------|
| `identify_or_ask()` | 识别用户或询问身份 |

**识别逻辑**：
1. 提取 Metadata (JWT / DeviceID / SessionID)
2. 未绑定 UserID → LLM 引导询问身份
3. 匹配数据库：已有用户直接识别，新用户自动创建
4. 成功后下发加密 Cookie/Token，后续请求静默识别
