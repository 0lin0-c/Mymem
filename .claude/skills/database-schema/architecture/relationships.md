# 表关系与代码目录拓扑

本文档定义表之间的关系和代码目录结构。

---

## 1. 表关系图

```
┌─────────────────┐         ┌──────────────────────┐         ┌─────────────────┐
│    Resource     │         │  resource_categories │         │    Category     │
│   (对话摘要)     │◄───────►│     (关联表)          │◄───────►│  (原子化记忆)    │
└─────────────────┘         └──────────────────────┘         └─────────────────┘
     1条                        多条关联                           多条
```

---

## 2. 代码目录拓扑

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

| 文件 | 功能 |
|------|------|
| `core/config.py` | 读取 .env 配置（数据库URL、LLM API Key、向量化维度 1536） |
| `core/database.py` | 异步引擎 + get_db() 依赖注入 |
| `tables/user.py` | 用户表（含 user_prompt_template、agent_persona_template） |
| `tables/category.py` | 原子化记忆表（含 content_vector 向量字段） |
| `tables/resource.py` | 对话摘要表（含 description_vector 向量字段） |
| `init_db.py` | 执行 CREATE EXTENSION vector + 建表 |
