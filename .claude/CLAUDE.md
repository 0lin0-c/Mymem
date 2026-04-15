# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此仓库中工作时提供指导。

## 架构

本项目是一个基于 FastAPI 的 Agent 记忆服务，采用严格的 5 层架构：

```
Mymem/
├── api/v1/        # 路由层：仅负责请求校验和响应封装 - 禁止包含业务逻辑
├── schemas/       # Schema 层：Pydantic 模型，定义 API 契约
├── services/      # Service 层：所有业务逻辑的唯一所在地
├── repositories/  # Repository 层：数据访问的唯一入口（使用 SQLAlchemy select()）
├── tables/        # Model 层：SQLAlchemy ORM 实体定义
└── core/          # 基础设施：配置、数据库连接
```

**层级规则：**
- API 层调用 Service，禁止直接调用 Repository
- Service 编排业务逻辑，调用 Repository
- Repository 使用 SQLAlchemy `select()` 语法，禁止原始 SQL 字符串
- 例外：`VectorStrategy` 使用原始 SQL 调用 pgvector 的 `<=>` 算子

## 🔴 SYSTEM DIRECTIVE: STRICT CODING WORKFLOW 🔴

你是本项目的核心开发 Agent。为了保证代码与架构设计文档（Skills）的绝对一致性，并在长上下文中极大地节省 Token，你在接到任何修改代码或开发新功能的指令时，**必须且只能**按照以下三个阶段（Pre-flight -> Execution -> Post-flight）进行工作。

---

## 阶段一：Pre-flight (精准检索与冲突检测) - 🚀 动代码前必须执行

**目标：根据当前修改的目录，精准定位并只读取最相关的文档，检测与人类指令是否存在冲突。**

### 1. 查找依赖树 (Locate Skill)
请严格根据你要修改的代码目录，对照下表找到对应的 Skill 目录：

| 触发代码目录/场景 | 对应的 Skill 目录 | 核心规范内容 |
|-------------------|-------------------|--------------|
| `api/v1/` 路由、对话流程 | `skills/input-pipeline/` | 用户识别、多轮对话缓存、记忆落库 |
| `services/`（非 llm 子目录） | `skills/service-design/` | Memory/Session/Retrieval/OSS 模块逻辑 |
| `services/llm/` | `skills/llm-factory-design/` | LLM Provider 适配、工厂模式实现 |
| `tables/`、`repositories/` | `skills/database-schema/` | 表结构、ORM 映射、Repository 接口定义 |
| 检索逻辑、相似度计算 | `skills/retrieval-pipeline/` | LLM 分类判断、向量检索、上下文构建策略 |
| 前端表单、初始化流程 | `skills/frontend-design/` | 用户画像表单、AI 定制表单字段定义 |

### 2. 精准读取 (Read on Demand)
- **严禁**直接 `cat` 整个目录或冗长的全量文档！
- 进入对应的 Skill 目录后，首先读取 `SKILL.md`，根据其内部的路由表定位到具体的子文档（如 `workflow/xxx.md`）。
- 使用 `grep` 搜索关键词，或只 `cat` 真正相关的子文档。

### 3. 冲突拦截器 (Conflict Guardrail)
对比【人类刚下达的代码修改指令】与【你刚读取的设计文档规范】。
- **若不一致 / 存在冲突：**
  - 🛑 **立即停止 (STOP)**：绝对不要开始写代码！
  - 🗣️ **向人类报告**：明确列出“指令要求什么” vs “文档规定什么”。
  - ❓ **请求决策**：询问用户：“请问我是应该严格按照文档执行，还是需要我先帮您把设计文档更新为最新需求？”
- **若完全一致：** 向人类简述你理解的规范要点，并请求开始编写代码。

---

## 阶段二：Execution (执行修改)

只有在阶段一确认无冲突，或人类给出明确的“偏好选择”后，你才可以进行代码修改。
- 必须严格遵守文档中约定的 API 契约（字段名、数据类型、HTTP 状态码）。
- 必须遵循当前项目的架构分层（如 Controller 不写 SQL，全部交由 Repository）。

---

## 阶段三：Post-flight (一致性校验) - 🏁 写完代码后必须执行

**目标：自我 QA，防止大模型幻觉和细节遗漏。**


1. **差异对比**：修改完成后，必须使用 `git diff` 审视你刚刚生成或修改的代码。
2. **回溯核对**：将 `git diff` 的结果与阶段一中提取的【设计文档规范】进行逐条交叉比对。
3. **安全检查单 (Checklist)**：
   - [ ] 字段命名、层级是否与文档 100% 对应？
   - [ ] 是否漏掉了文档中规定的边界条件或异常捕获（Error Handling）？
   - [ ] 新增的代码是否破坏了其他 Skill 模块的既定规则？
4. **输出报告**：向人类输出一份简短的 QA 报告。如果自我审查发现遗漏，主动进行二次修复。

## 编码规范

- **全异步**：所有 I/O 操作使用 `await` 和 `AsyncSession`
- **禁止 print()**：使用 `logging` 模块
- **禁止硬编码密钥**：所有配置通过 `core/config.py` 的 Settings 从 `.env` 读取
- **向量存储**：`description_vector` 使用 pgvector 的 `Vector(1536)` 类型，可直接在 SQL 中使用 `<=>` 操作符进行余弦距离计算