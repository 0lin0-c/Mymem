# 测试结构说明

本目录统一由 `pytest` 管理。默认从仓库根目录运行测试，评估入口和额外参数集中在
`tests/conftest.py` 中注册。

## 目录结构

```text
tests/
├── conftest.py          # 公共 fixtures 和 pytest option
├── contract/            # 服务边界和编排器契约测试
├── unit/                # 纯逻辑、报告、后处理、评估契约单元测试
├── integration/         # 集成测试预留目录
├── evals/               # 数据集驱动评估
├── fixtures/            # 评估输入 fixture
├── performance/         # 手动性能/诊断脚本，使用 perf_*.py 命名
├── test_api/            # API 端到端测试
├── test_services/       # Service 层测试
├── test_repositories.py # Repository 层测试
└── test_tables.py       # ORM 映射测试
```

## 验证层级

1. 单元测试：不依赖真实 LLM 或完整评估链路，验证纯逻辑和局部契约。
2. 契约测试：验证 `MemoryWriter`、`MemoryRetriever`、`ChatOrchestrator`
   等服务边界。
3. 集成/评估测试：调用真实 DB、Repository、Service 或模型 Provider。
4. 端到端评估：验证用户可见回答链路，通常运行时间较长。

按照 AGENTS.md 的完成定义，前一层未通过时不要进入下一层。

## 常用命令

```powershell
# 核心文件语法检查
conda run -n memory_agent python -m py_compile services\chat_orchestrator.py tests\evals\converted_data\runner.py tests\evals\converted_data\report_json.py tests\contract\test_chat_orchestrator_contract.py tests\unit\test_converted_data_reporting.py tests\unit\test_converted_data_postprocess.py

# 快速核心验证
conda run -n memory_agent python -m pytest -q tests\contract\test_chat_orchestrator_contract.py tests\unit\test_converted_data_reporting.py tests\unit\test_converted_data_postprocess.py

# 评估报告和 PersonaMem 契约验证
conda run -n memory_agent python -m pytest -q tests\unit\test_personamem_p0_reporting.py tests\unit\test_personamem_results_organizer.py tests\unit\test_personamem_orthogonal_eval.py tests\unit\test_personamem_bm25_eval.py tests\unit\test_retrieval_tuning_ab.py

# converted_data 冒烟评估
conda run -n memory_agent python -m pytest -q tests\evals\converted_data --converted-sample 0 --converted-eval-mode assistant_eval --converted-character caroline --converted-max-questions 10
```

## 评估入口

converted_data 官方入口：

```powershell
conda run -n memory_agent python -m pytest -q tests\evals\converted_data --converted-sample 0 --converted-eval-mode storage_eval
conda run -n memory_agent python -m pytest -q tests\evals\converted_data --converted-sample 0 --converted-eval-mode retrieval_eval
conda run -n memory_agent python -m pytest -q tests\evals\converted_data --converted-sample 0 --converted-eval-mode assistant_eval
```

PersonaMem-v2 官方入口：

```powershell
conda run -n memory_agent python -m pytest -q tests\evals\personamem_v2 --personamem-v2 --personamem-v2-persona-id 66 --personamem-v2-max-questions 5
```

`scripts/run_*.py` 中的评估脚本仅作为兼容薄壳或诊断入口。新增正式评估能力应优先接入
`tests/conftest.py` 和 `tests/evals/*/test_eval_runner.py`。

## 运行安全

- 普通单元、契约测试不应写真实数据库。
- 真实 DB 只读评估应使用 `--converted-retrieval-only` 或对应只读模式。
- 真实 DB 写路径必须显式确认，并通过 `--allow-real-db-write`。
- 运行产物放在 `test_results/<domain>/`。
- 缓存产物只放在 `test_results/cache/`。
- 评估输入 fixture 放在 `tests/fixtures/`，不要混入运行产物。

## 结果组织

PersonaMem-v2 历史产物可用 `tests/evals/personamem_v2/result_organizer.py`
规划到 `official/`、`diagnostic/`、`legacy/`、`scratch/` 和 `logs/` 子目录。
整理器只移动并记录 SHA256 manifest，不删除产物。
