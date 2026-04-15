# Memory 模块

本文档定义记忆服务的设计规范。

---

## 1. MemoryWriter

记忆写入的统一入口，负责协调 Handler 完成写入流程。

> **详细流程设计**：详见 `input-pipeline` skill 第 4-5 节

---

## 2. 异步写入工作流（Memory Backstage）

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

**触发条件**（详见 `input-pipeline` 4.3 节）：
- 定量触发：`chat_count >= 5`
- 定时触发：`last_active_at > 30min` 且缓存非空
- 指令触发：用户说"再见"或手动保存

---

## 3. Handler 基类

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

---

## 4. Handler 实现状态

| Handler | 功能 | 状态 |
|---------|------|------|
| `TextHandler` | 文本预处理 + 摘要生成 | ✅ 完整实现 |
| `ImageHandler` | 图片 OCR/VLM 描述 | 🔜 骨架 |
| `VideoHandler` | 帧抽取 + 场景识别 | 🔜 骨架 |
| `VoiceHandler` | ASR 语音转文字 | 🔜 骨架 |
| `DocumentHandler` | PDF/Word 解析 | 🔜 骨架 |
