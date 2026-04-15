# 测试目录

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
