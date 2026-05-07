# 📋 测试结构说明

## 目录结构

```
tests/
├── conftest.py                    # 公共 fixtures: db session, test user, mock LLM
├── test_tables.py                 # ORM 模型测试：字段约束、关系映射
├── test_repositories.py           # Repository 层测试：CRUD + 真实向量检索
├── fixtures/                      # 评估输入夹具，不存放运行产物
├── performance/                   # 手动性能/诊断脚本，perf_*.py 不被默认 pytest 收集
│
├── test_services/
│   ├── test_llm.py                # LLM 服务测试：真实 API 调用
│   ├── test_memory_writer.py      # 记忆写入测试：save_chat 流程
│   ├── test_deduplication.py      # 去重逻辑测试：向量相似度 + LLM 判断
│   ├── test_retrieval.py          # 检索测试：LLM 分类 + 向量检索 + 分数计算
│   ├── test_session.py            # 会话管理测试：SessionManager + UserIdentifier
│   ├── test_oss.py                # OSS 存储测试：本地存储 + 阿里云 OSS
│   ├── test_lifecycle.py          # 记忆生命周期测试：遗忘机制 + 重要性衰减
│   ├── test_profile_service.py    # 用户画像服务测试：初始化 + 定制
│   ├── test_boundary_conditions.py # 边界条件测试：空输入、超长文本、特殊字符、并发
│   ├── test_error_handling.py     # 异常处理测试：LLM 超时、数据库断连
│   ├── test_performance.py        # 性能测试：大量数据、批量写入、并发请求
│   ├── test_security.py           # 安全测试：SQL 注入、XSS、权限隔离
│   └── test_mocks.py              # Mock 集成测试：LLL 响应 Mock、快速单元测试
│
└── test_api/
    ├── test_chat.py               # Chat API 端到端测试
    ├── test_memory.py             # Memory API 端到端测试
    └── test_retrieve.py           # Retrieve API 端到端测试
```

## 目录约定

- 测试代码统一放在 `tests/`，由 `pytest.ini` 的 `testpaths = tests` 管理。
- 评估输入 fixture 放在 `tests/fixtures/`，例如 unsupported-success recheck 输入。
- 运行产物放在 `test_results/<domain>/`，缓存只放在 `test_results/cache/`。
- 性能诊断脚本放在 `tests/performance/`，文件名使用 `perf_*.py`，避免默认 pytest 误跑真实 LLM/HTTP 探针。

## 运行测试

```bash
# 运行所有测试
pytest

# 运行特定文件
pytest tests/test_repositories.py

# 运行特定测试类
pytest tests/test_repositories.py::TestVectorSearch

# 只运行集成测试（真实 API 调用）
pytest -m integration

# 排除集成测试（快速验证）
pytest -m "not integration"

# 排除慢速测试
pytest -m "not slow"

# 运行向量相关测试
pytest -m vector

# 运行安全测试
pytest tests/test_services/test_security.py

# 运行 Mock 测试（最快，无外部依赖）
pytest tests/test_services/test_mocks.py

# 显示详细输出
pytest -v --tb=short

# 显示打印输出
pytest -s

# 生成覆盖率报告
pytest --cov=. --cov-report=html
```

## 测试标记

| 标记 | 说明 | 用途 |
|------|------|------|
| `@pytest.mark.integration` | 集成测试 | 会调用真实 LLM API，需要 API Key |
| `@pytest.mark.slow` | 慢速测试 | 运行时间较长 |
| `@pytest.mark.vector` | 向量测试 | 涉及 pgvector 计算 |

## Fixtures 说明

| Fixture | 作用域 | 说明 |
|---------|--------|------|
| `db_engine` | session | 测试数据库引擎，整个测试会话共享 |
| `db_session` | function | 测试数据库会话，每个测试独立，自动回滚 |
| `test_user` | function | 创建测试用户 |
| `another_user` | function | 创建另一个测试用户（用于隔离测试） |
| `llm_provider` | function | 真实 LLM Provider |
| `sample_embedding` | function | 真实 embedding 向量样本 |
| `fake_embedding` | function | 假的 1536 维向量 |
| `similar_embeddings` | function | 两个相似的向量（用于测试） |
| `session_id` | function | 测试会话 ID |
| `temp_storage` | function | 临时存储目录（自动清理） |

## 测试分类

### 1. 功能测试（基础覆盖）

| 测试文件 | 覆盖内容 |
|----------|----------|
| `test_tables.py` | ORM 模型字段约束、关系映射、级联删除 |
| `test_repositories.py` | CRUD 操作、向量检索、关联查询 |
| `test_llm.py` | 对话生成、Embedding、记忆意图提取 |
| `test_memory_writer.py` | save_chat 完整流程、去重开关 |
| `test_deduplication.py` | SKIP/MERGE/UPDATE/CREATE 决策 |
| `test_retrieval.py` | LLM 分类、向量检索、分数计算 |
| `test_session.py` | 会话管理、用户识别 |
| `test_oss.py` | 文件上传/下载/删除 |
| `test_lifecycle.py` | 遗忘公式、衰减计算 |
| `test_profile_service.py` | 用户初始化、模板生成 |
| `test_api/*.py` | 端到端 API 测试 |

### 2. 边界条件测试

| 测试场景 | 测试方法 |
|----------|----------|
| 空输入 | `test_empty_username`, `test_empty_user_input` |
| 超长文本 | `test_long_content_save`, `test_very_long_query` |
| 特殊字符 | `test_unicode_username`, `test_emoji_in_content` |
| SQL 注入尝试 | `test_sql_injection_attempt` |
| XSS 攻击尝试 | `test_xss_attempt` |
| 并发写入 | `test_concurrent_resource_creation`, `test_concurrent_read_write` |
| 数值边界 | `test_importance_score_min`, `test_top_k_boundaries` |

### 3. 异常处理测试

| 测试场景 | 测试方法 |
|----------|----------|
| LLM 超时 | `test_llm_chat_timeout`, `test_llm_embedding_timeout` |
| LLM 无效响应 | `test_llm_empty_response`, `test_llm_malformed_json` |
| 数据库错误 | `test_database_connection_error`, `test_database_constraint_violation` |
| OSS 错误 | `test_file_not_found`, `test_disk_full_simulation` |
| 服务降级 | `test_retrieval_without_llm_classification` |

### 4. 性能测试

| 测试场景 | 测试方法 |
|----------|----------|
| 批量写入 | `test_bulk_insert_performance` |
| 向量检索 | `test_vector_search_performance` |
| 并发读写 | `test_concurrent_reads`, `test_concurrent_writes` |
| 大结果集 | `test_large_result_set` |
| 内存使用 | `test_large_vector_memory`, `test_result_set_memory` |

### 5. 安全测试

| 测试场景 | 测试方法 |
|----------|----------|
| SQL 注入 | `test_sql_injection_in_username`, `test_sql_injection_in_content` |
| XSS 攻击 | `test_xss_in_content` |
| 权限隔离 | `test_user_cannot_access_other_user_resources` |
| 路径遍历 | `test_path_traversal_in_oss` |
| 数据验证 | `test_invalid_uuid_handling`, `test_unicode_normalization` |

### 6. Mock 测试（快速单元测试）

| 测试场景 | 测试方法 |
|----------|----------|
| Mock LLM | `test_mock_chat_response`, `test_mock_embedding` |
| Mock 写入 | `test_save_chat_with_mock` |
| Mock 去重 | `test_dedup_skip_with_mock`, `test_dedup_merge_with_mock` |
| Mock 检索 | `test_retrieval_with_mock`, `test_classification_with_mock` |
| 错误场景 | `test_llm_timeout_scenario`, `test_partial_failure_scenario` |

## 注意事项

1. **集成测试需要配置**：运行 `@pytest.mark.integration` 标记的测试需要：
   - 配置 `.env` 文件中的 LLM API Key
   - 配置数据库连接

2. **数据库隔离**：每个测试使用独立的数据库会话，测试结束后自动回滚

3. **向量测试**：涉及 pgvector 的测试需要 PostgreSQL 数据库支持

4. **Mock vs 真实**：
   - 集成测试使用真实 LLM API
   - `test_mocks.py` 提供 Mock 版本用于快速单元测试

5. **性能测试**：标记为 `@pytest.mark.slow`，默认可跳过

## 测试最佳实践

1. **测试命名**：`test_<功能>_<场景>_<预期结果>`
2. **测试隔离**：每个测试独立，不依赖其他测试
3. **断言清晰**：使用明确的断言消息
4. **Mock 外部依赖**：单元测试应 Mock LLM、OSS 等
5. **标记集成测试**：需要真实 API 的测试标记为 `@pytest.mark.integration`
