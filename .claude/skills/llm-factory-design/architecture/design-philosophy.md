# 核心架构与设计哲学

本文档定义 LLM Factory 模块的设计原则和代码目录结构。

---

## 1. 设计原则

| 设计原则 | 说明 |
|---------|------|
| **依赖倒置原则** | 上层业务代码绝对不允许直接 `import openai` 或 `import anthropic`，只依赖于抽象基类（契约）。保证未来厂商 SDK 破坏性更新或接入新模型时，核心业务代码无需修改。 |
| **简单工厂模式** | 根据 `.env` 中的 `LLM_PROVIDER` 配置，由工厂类动态实例化对应的模型提供商对象，注入到 FastAPI 请求上下文。 |
| **强制异步** | 所有对外方法必须使用 `async/await`，确保等待外部 API 响应时，FastAPI 主事件循环仍能处理其他并发请求。 |
| **结构化输出约束** | 底层适配器负责引导并校验模型返回严谨的 JSON 结构（如记忆分类提取、重要性打分），而非发散的自然语言。 |

---

## 2. 代码目录拓扑

```
Mymem/
└── services/
    └── llm/
        ├── __init__.py          # [包声明] 暴露对外的核心类
        ├── base.py              # [接口契约] BaseLLMProvider 抽象基类
        ├── openai_sdk.py        # [适配器] OpenAI 及兼容标准 (DeepSeek 等)
        ├── anthropic_sdk.py     # [适配器] Claude 独立 API 结构
        ├── factory.py           # [总调度] 读取配置并分发适配器
        └── tools.py             # [工具层] Prompt 构建、Tool 定义、向量计算
```
