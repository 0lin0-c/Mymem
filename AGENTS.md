# AGENTS.md

## 架构

本项目是一个基于 FastAPI 的 Agent 记忆服务，采用严格的 5 层架构：

```text
Mymem/
├── api/v1/        # 路由层：仅负责请求校验和响应封装，禁止包含业务逻辑
├── schemas/       # Schema 层：Pydantic 模型，定义 API 契约
├── services/      # Service 层：所有业务逻辑的唯一所在地
├── repositories/  # Repository 层：数据访问的唯一入口（使用 SQLAlchemy select()）
├── tables/        # Model 层：SQLAlchemy ORM 实体定义
└── core/          # 基础设施：配置、数据库连接
```

**层级规则：**

- API 层调用 Service，禁止直接调用 Repository。
- Service 编排业务逻辑，调用 Repository。
- Repository 使用 SQLAlchemy `select()` 语法，禁止原始 SQL 字符串。
- 例外：`VectorStrategy` 可以使用原始 SQL 调用 pgvector 的 `<=>` 算子。

## 项目 Skills 说明

`.claude/skills` 是本仓库内的强制性技术规范文档目录。Codex 可以读取并遵守这些文档，但它们不是当前 Codex 运行环境的内置自动 Skill；需要根据本文件的路由规则，在修改代码或做代码审查前按需读取。

当用户提出代码修改、功能开发、重构、Bug 修复或代码审查请求时，必须先根据触发目录或任务类型定位相关 `.claude/skills/*/SKILL.md`，再按该 `SKILL.md` 内部路由读取最相关的子文档。不要一次性读取整个 skill 目录。

如果一次修改跨越多个目录，必须读取所有相关 skill 的入口文档。例如修改 `api/v1/` + `services/` + `repositories/` 时，需要分别读取 `input-pipeline`、`service-design`、`database-schema`。如果检索逻辑涉及 `services/`，同时读取 `service-design` 与 `retrieval-pipeline`。

## 严格开发流程

你是本项目的核心开发 Agent。为了保证代码与 `.claude/skills` 中的架构设计文档保持一致，在接到任何修改代码或开发新功能的指令时，必须按照以下三个阶段工作。

### 阶段一：Pre-flight（精准检索与冲突检测）

目标：根据当前修改的目录或任务类型，精准定位并只读取最相关的文档，检测用户指令是否与规范冲突。

#### 1. 查找依赖树

| 触发代码目录/场景 | 对应的 Skill 目录 | 核心规范内容 |
|-------------------|-------------------|--------------|
| `api/v1/` 路由、对话流程 | `.claude/skills/input-pipeline/` | 用户识别、多轮对话缓存、记忆落库 |
| `services/`（非 `services/llm/`） | `.claude/skills/service-design/` | Memory/Session/Retrieval/OSS 模块逻辑 |
| `services/llm/` | `.claude/skills/llm-factory-design/` | LLM Provider 适配、工厂模式实现 |
| `tables/`、`repositories/` | `.claude/skills/database-schema/` | 表结构、ORM 映射、Repository 接口定义 |
| 检索逻辑、相似度计算、上下文构建 | `.claude/skills/retrieval-pipeline/` | LLM 分类判断、向量检索、上下文构建策略 |
| 前端表单、初始化流程 | `.claude/skills/frontend-design/` | 用户画像表单、AI 定制表单字段定义 |
| `review`、`code review`、`PR review`、`审查代码`、`检查改动`、`看看有没有 bug` | `.claude/skills/code-review/` | 代码审查流程与风险检查 |

#### 2. 精准读取

- 进入对应 Skill 目录后，首先读取 `SKILL.md`。
- 根据 `SKILL.md` 的路由表定位具体子文档，例如 `workflow/xxx.md`、`modules/xxx.md`、`api/endpoints.md`。
- 使用 `rg` 搜索关键词，或只读取真正相关的子文档。
- 禁止直接读取整个目录或无关的大量文档。

#### 3. 冲突拦截器

对比【用户刚下达的修改指令】与【刚读取的设计文档规范】：

- 若不一致或存在冲突：立即停止，不要开始写代码；向用户明确列出“指令要求什么”与“文档规定什么”，并请求用户决策。
- 若无冲突：简述关键规范要点，然后继续执行；除非当前协作模式或用户明确要求先计划，否则不需要额外询问是否开始写代码。

### 阶段二：Execution（执行修改）

只有在阶段一确认无冲突，或用户给出明确偏好选择后，才可以进行代码修改。

- 必须严格遵守文档中约定的 API 契约，包括字段名、数据类型、HTTP 状态码和响应结构。
- 必须遵循当前项目的架构分层，例如 API 层不写 SQL，数据库访问交给 Repository。
- Service 层可以调用其他 Service 或 Repository，但禁止直接操作 ORM 模型。
- 所有 I/O 操作优先使用 `async/await` 和 `AsyncSession`。

### 阶段三：Post-flight（一致性校验）

修改完成后必须自我 QA：

1. 使用 `git diff` 审视刚刚生成或修改的代码。
2. 将 diff 与阶段一读取的设计文档规范交叉核对。
3. 检查字段命名、层级、异常处理、边界条件是否符合文档。
4. 检查新增代码是否破坏其他 Skill 模块的既定规则。
5. 向用户输出简短 QA 报告；如果发现遗漏，主动二次修复。

## 编码规范

- **全异步**：所有 I/O 操作使用 `await` 和 `AsyncSession`。
- **禁止 `print()`**：使用 `logging` 模块。
- **禁止硬编码密钥**：所有配置通过 `core/config.py` 的 `Settings` 从 `.env` 读取。
- **向量存储**：`description_vector` 使用 pgvector 的 `Vector(1536)` 类型，可在 SQL 中使用 `<=>` 操作符进行余弦距离计算。
## 测试命令速查

优先使用 `pytest` 作为官方测试与评估入口。下面这些命令默认在仓库根目录执行。

### 基础校验

```powershell
conda run -n memory_agent python -m py_compile services\chat_orchestrator.py tests\evals\converted_data\runner.py tests\evals\converted_data\report_json.py tests\contract\test_chat_orchestrator_contract.py tests\unit\test_converted_data_reporting.py tests\unit\test_converted_data_postprocess.py
```

```powershell
conda run -n memory_agent python -m pytest -q tests\contract\test_chat_orchestrator_contract.py tests\unit\test_converted_data_reporting.py tests\unit\test_converted_data_postprocess.py
```

### converted_data 官方 pytest 入口

运行单个 sample：

```powershell
conda run -n memory_agent python -m pytest -q tests\evals\converted_data --converted-sample 0
```

指定评估模式：

```powershell
conda run -n memory_agent python -m pytest -q tests\evals\converted_data --converted-sample 0 --converted-eval-mode storage_eval
conda run -n memory_agent python -m pytest -q tests\evals\converted_data --converted-sample 0 --converted-eval-mode retrieval_eval
conda run -n memory_agent python -m pytest -q tests\evals\converted_data --converted-sample 0 --converted-eval-mode assistant_eval
```

指定数据目录、角色、top_k：

```powershell
conda run -n memory_agent python -m pytest -q tests\evals\converted_data --converted-sample 0 --converted-data-dir data\converted_data_recent_2026q1_name_trimmed --converted-character caroline --converted-top-k 5
```

只跑已入库数据，不重新导入：

```powershell
conda run -n memory_agent python -m pytest -q tests\evals\converted_data --converted-sample 0 --converted-eval-mode assistant_eval --converted-data-dir data\converted_data_recent_2026q1_name_trimmed --converted-character caroline --converted-retrieval-only
```

限制题量做冒烟测试：

```powershell
conda run -n memory_agent python -m pytest -q tests\evals\converted_data --converted-sample 0 --converted-eval-mode assistant_eval --converted-character caroline --converted-max-questions 10
```

主评估结束后补做失败样本 bad-case diagnosis：

```powershell
conda run -n memory_agent python -m pytest -q tests\evals\converted_data --converted-sample 0 --converted-eval-mode assistant_eval --converted-character caroline --converted-postprocess-bad-cases
```

### CLI 兼容入口

兼容脚本仍可用，但推荐优先使用上面的 pytest 入口：

```powershell
$env:PYTHONPATH='.'
conda run --no-capture-output -n memory_agent python scripts\run_converted_data_eval.py --sample 0 --data-dir data\converted_data_recent_2026q1_name_trimmed --eval-mode assistant_eval --character caroline --retrieval-only --max-questions 10 --postprocess-bad-cases
```

### 长任务建议

- 长时间 `assistant_eval` 建议使用 `--retrieval-only`，避免重复导入数据。
- 需要深诊断时再加 `--converted-postprocess-bad-cases` 或 `--postprocess-bad-cases`。
- 长跑任务默认按 6 小时外层超时准备，完整 90 题 assistant_eval 预估约 1.5 到 2 小时。

### 测试目录约定

- 测试代码统一放在 `tests/`，性能/诊断脚本放在 `tests/performance/` 并使用 `perf_*.py` 命名。
- 评估输入 fixture 放在 `tests/fixtures/`。
- 运行产物放在 `test_results/<domain>/`，缓存只放在 `test_results/cache/`。
