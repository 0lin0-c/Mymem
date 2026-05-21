# MyMem

MyMem 是一个面向 Agent 的长期记忆服务，基于 FastAPI、SQLAlchemy AsyncSession、PostgreSQL 和 pgvector 构建。项目采用 API、Schema、Service、Repository、ORM Model 五层架构，核心能力包括多轮对话缓存、异步记忆写入、原子化记忆抽取、分层存储、向量检索和个性化上下文构建。

系统将记忆拆分为对话摘要层 `Resource`、原子化记忆层 `Category` 和来源关联层 `ResourceCategory`，检索时通过 LLM 分类、Category 层召回、充足性判断、Resource 层兜底和四因子评分公式，尽量在召回准确性、可追溯性和工程可维护性之间取得平衡。

记忆分类包含四类固定分类：`Core Self`（核心自我）、`Episodic Memory`（情景时间轴）、`Knowledge Base`（语义知识库）、`Social Graph`（社交关系图谱），并支持根据用户画像和使用场景扩展动态分类。

## 测试目录

## 文件说明

| 文件 | 作用 |
|------|------|
| `test_db.py` | 测试数据库连接是否正常，验证 pgvector 插件是否启用 |
| `test_llm.py` | 测试 LLM 服务（对话、文本向量、记忆意图提取） |
| `test_repositories.py` | Repository 层单元测试，验证各表的 CRUD 操作 |
| `test_integration.py` | 完整集成测试：用户输入 → LLM 分析 → 数据库持久化 |
| `query_db.py` | 查询数据库最新插入的测试数据 |

## 运行命令

```bash
# 1. 测试数据库连接（首次部署时使用）
python -m test.test_db

# 2. 测试 LLM 服务（验证 API Key 和连接）
python -m test.test_llm

# 3. Repository 层单元测试（验证数据库 CRUD）
python -m test.test_repositories

# 4. 完整集成测试（LLM + 数据库串联）
python -m test.test_integration

# 5. 查询数据库最新数据（调试用）
python -m test.query_db
```

## 测试流程建议

1. **首次部署**：先跑 `test_db` 确认数据库连通
2. **LLM 配置后**：跑 `test_llm` 验证 API 连通
3. **Repository 开发时**：跑 `test_repositories` 验证 CRUD
4. **完整功能验证**：跑 `test_integration` 验证端到端
5. **查看数据**：跑 `query_db` 确认数据写入

## 注意事项

- 测试数据默认**不会自动清理**（方便调试），如需清理请手动删除或取消 `test_repositories.py` 和 `test_integration.py` 中的清理代码注释
- 所有测试使用 `.env` 中的 `DATABASE_URL` 配置
