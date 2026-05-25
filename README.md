# MyMem

MyMem 是一个面向 Agent 的长期记忆服务，基于 FastAPI、SQLAlchemy
AsyncSession、PostgreSQL 和 pgvector 构建。项目采用严格的五层架构：

```text
api/v1/        路由层：请求校验和响应封装
schemas/       Schema 层：Pydantic API 契约
services/      Service 层：业务逻辑唯一所在地
repositories/  Repository 层：数据访问唯一入口
tables/        Model 层：SQLAlchemy ORM 实体
core/          基础设施：配置和数据库连接
```

核心能力包括多轮对话缓存、异步记忆写入、原子化记忆抽取、分层存储、
向量检索、个性化上下文构建，以及面向 converted_data 和 PersonaMem-v2
的评估链路。

## 架构约定

- API 层调用 Service，不直接调用 Repository 或 ORM。
- Service 层编排业务逻辑，并通过 Repository 访问数据。
- Repository 使用 SQLAlchemy `select()` 语法；仅 pgvector `<=>` 检索路径可使用原始 SQL。
- 所有 I/O 路径优先使用 `async/await` 和 `AsyncSession`。
- 配置从 `.env` 读取，入口在 `core/config.py`。

## 环境准备

1. 创建并激活 `memory_agent` 环境。
2. 安装依赖：

```powershell
conda run -n memory_agent python -m pip install -r requirements.txt
```

3. 复制并填写环境变量：

```powershell
Copy-Item .env.example .env
```

4. 确认 PostgreSQL 已启用 pgvector，并在 `.env` 中配置数据库、Redis、LLM
   Provider 和模型密钥。

## 启动服务

```powershell
conda run -n memory_agent python -m uvicorn main:app --reload
```

默认 API 入口由 `main.py` 注册，路由位于 `api/v1/`。

## 官方验证入口

优先使用 `pytest`。以下命令默认在仓库根目录执行。

```powershell
# 核心文件语法检查
conda run -n memory_agent python -m py_compile services\chat_orchestrator.py tests\evals\converted_data\runner.py tests\evals\converted_data\report_json.py tests\contract\test_chat_orchestrator_contract.py tests\unit\test_converted_data_reporting.py tests\unit\test_converted_data_postprocess.py

# 核心契约测试与单元测试
conda run -n memory_agent python -m pytest -q tests\contract\test_chat_orchestrator_contract.py tests\unit\test_converted_data_reporting.py tests\unit\test_converted_data_postprocess.py

# converted_data 冒烟评估
conda run -n memory_agent python -m pytest -q tests\evals\converted_data --converted-sample 0 --converted-eval-mode assistant_eval --converted-character caroline --converted-max-questions 10
```

常用 converted_data 参数：

- `--converted-eval-mode storage_eval|retrieval_eval|assistant_eval`
- `--converted-data-dir <path>`
- `--converted-character <name>`
- `--converted-top-k <n>`
- `--converted-retrieval-only`
- `--converted-max-questions <n>`
- `--converted-postprocess-bad-cases`

PersonaMem-v2 评估也通过 pytest 控制面运行：

```powershell
conda run -n memory_agent python -m pytest -q tests\evals\personamem_v2 --personamem-v2 --personamem-v2-persona-id 66 --personamem-v2-max-questions 5
```

`scripts/run_*.py` 中的评估脚本仅作为兼容薄壳或诊断入口。新增正式评估参数应接入
`tests/conftest.py`，不要再复制新的 standalone `argparse` 控制面。

## 测试目录约定

- `tests/contract/`：服务边界和编排器契约测试。
- `tests/unit/`：纯逻辑、报告生成、后处理和评估契约单元测试。
- `tests/evals/`：数据集驱动评估，可能依赖真实数据库或模型。
- `tests/fixtures/`：评估输入 fixture。
- `tests/performance/`：手动性能/诊断脚本，文件名使用 `perf_*.py`。
- `test_results/<domain>/`：运行产物。
- `test_results/cache/`：缓存产物。

## 文档入口

- `AGENTS.md`：当前 Agent 工作规则、架构约束和验证入口。
- `.claude/skills/*/SKILL.md`：按目录和任务类型读取的强制技术规范。
- `tests/README.md`：测试目录和验证层级说明。
- `tests/README_memory_eval.md`：记忆评估模式、运行安全和结果格式说明。
