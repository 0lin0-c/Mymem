# 监控与度量

本文档定义 Service 层的监控埋点和核心指标。

---

## 1. 核心指标

| 指标 | 说明 | 告警阈值 |
|------|------|----------|
| **LLM Latency** | 意图提取的平均耗时 | > 3s |
| **Vector Accuracy** | 用户对检索结果的反馈（点赞/点踩） | 点赞率 < 70% |
| **Storage Overhead** | 各模态文件在 OSS 中的占用比例 | 单用户 > 1GB |
| **Session TTL** | 会话平均存活时间 | - |
| **Pending Flush** | 待落库对话积压数量 | > 100 条 |

---

## 2. 埋点位置

| 模块 | 埋点方法 | 记录指标 |
|------|----------|----------|
| `Memory` | `MemoryWriter.save_chat()` | 写入耗时、意图提取耗时 |
| `Retrieval` | `MemoryRetriever.retrieve()` | 检索耗时、结果数量 |
| `Session` | `SessionManager.add_pending_chat()` | 缓存命中率、会话时长 |
| `LLM` | `BaseLLMProvider.generate_chat_response()` | LLM 响应时间 |
