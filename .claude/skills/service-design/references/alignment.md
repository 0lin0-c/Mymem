# 文档映射与完成情况

本文档确保 service-design 与其他 skill 文档的一致性，并记录实现进度。

---

## 1. 与 `input-pipeline` 的映射

| service-design 位置 | input-pipeline 位置 | 内容 |
|---------------------|---------------------|------|
| 3.2 异步写入工作流 | 4.2-4.4 多轮对话缓存 | 缓存策略与落库触发条件 |
| 4.2 SessionManager | 4.1 设计目标 | 5 轮批量存储机制 |
| 4.4 UserIdentifier | 2.1 增强型用户识别 | JWT/DeviceID 绑定逻辑 |

---

## 2. 与 `database-schema` 的映射

| service-design 位置 | database-schema 位置 | 内容 |
|---------------------|---------------------|------|
| 3.3 Handler 基类 | 4.2 resources 表 | 向量字段 `Vector(1536)` |
| 5.3 策略对比 | 7.5 向量检索实现要点 | `<=>` 操作符使用 |
| 6.2 存储路径规范 | 4.1 users 表 | user_id 作为存储隔离键 |

---

## 3. 与 `retrieval-pipeline` 的映射

| service-design 位置 | retrieval-pipeline 位置 | 内容 |
|---------------------|-------------------------|------|
| 5.1 LLM 驱动的串行检索 | 1 检索流程概览 | 串行检索架构 |
| 5.2 MemoryRetriever | 2 LLM 分类判断 | _classify_query 接口 |
| 5.2 MemoryRetriever | 3 分类内检索 | _search_in_categories 接口 |
| 5.2 MemoryRetriever | 5 检索结果作为上下文 | build_context 接口 |

---

## 4. 与 `llm-factory-design` 的映射

| service-design 位置 | llm-factory-design 位置 | 内容 |
|---------------------|-------------------------|------|
| 2 LLM 模块 | 4 核心接口与标准协议 | generate_chat_response, get_embedding |
| 3.1 MemoryWriter | 4.3 extract_memory_intent | 记忆意图提取（由 MemoryWriter 调用 LLM） |

---

## 5. 与 `frontend-design` 的映射

| service-design 位置 | frontend-design 位置 | 内容 |
|---------------------|---------------------|------|
| 4.4 UserIdentifier | 1.1 整体流程 | 用户画像初始化 |
| 3.1 MemoryWriter | 3.2 模板生成逻辑 | user_prompt_template 生成 |

---

## 6. 完成情况

### 6.1 已完成

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
- [x] `AliyunOSSClient` 阿里云 OSS 实现

### 6.2 待扩展

- [ ] `ImageHandler` 完整实现（VLM/OCR）
- [ ] `VoiceHandler` 完整实现（ASR）
- [ ] `VideoHandler` 完整实现（帧抽取 + VLM）
- [ ] `DocumentHandler` 完整实现（PDF/Word 解析）
- [ ] `RedisSessionStore` 分布式 Session 存储
