# 整体目录结构

本文档定义 Service 层的代码组织方式。

---

## 目录拓扑

```
services/
├── constants.py             # 公共常量（BASE_CATEGORIES 等）
├── profile_service.py       # 用户画像与 AI 助手定制服务
│
├── llm/                     # 大模型服务
│   ├── __init__.py
│   ├── base.py              # BaseLLMProvider 抽象基类
│   ├── factory.py           # LLMFactory 工厂
│   ├── openai_sdk.py        # OpenAI 适配器
│   ├── anthropic_sdk.py     # Anthropic 适配器
│   ├── user_llm_factory.py  # 用户级 LLM 工厂
│   └── tools.py             # LLM 工具定义
│
├── memory/                  # 记忆服务
│   ├── __init__.py
│   ├── writer.py            # MemoryWriter 写入服务
│   ├── lifecycle.py         # 记忆生命周期管理（遗忘机制）
│   ├── deduplicator.py      # 记忆去重服务
│   ├── dedup_config.py      # 去重配置（阈值等）
│   └── handlers/            # 模态处理器
│       ├── __init__.py
│       ├── base.py          # Handler 抽象基类
│       ├── text_handler.py
│       ├── image_handler.py
│       ├── video_handler.py
│       ├── voice_handler.py
│       └── document_handler.py
│
├── retrieval/               # 检索服务
│   ├── __init__.py
│   ├── base.py              # RetrievalStrategy 抽象基类
│   ├── retriever.py         # MemoryRetriever 检索服务（双层检索）
│   └── vector_strategy.py   # Resource 向量检索策略
│
├── session/                 # 会话服务
│   ├── __init__.py
│   ├── state.py             # SessionState, PendingChat 数据类
│   ├── session_manager.py   # 会话状态管理
│   ├── user_identifier.py   # 用户识别服务
│   ├── flush_service.py     # 会话刷新服务
│   └── redis_store.py       # Redis 存储实现
│
├── oss/                     # 对象存储服务
│   ├── __init__.py
│   ├── base.py              # BaseOSSClient 抽象基类
│   ├── local_client.py      # 本地存储实现
│   └── aliyun_client.py     # 阿里云 OSS 实现
│
└── prompts/                 # Prompt 模板
    ├── __init__.py
    ├── chat_prompt.py
    ├── memory_prompt.py
    ├── lifecycle_prompt.py  # 生命周期相关 Prompt
    └── onboarding_prompt.py # 初始化相关 Prompt
```
