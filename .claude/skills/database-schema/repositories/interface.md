# Repository 层接口设计

本文档定义 Repository 层的方法接口和依赖注入方式。

---

## 1. Repository 模式定位

Repository 层作为**数据访问抽象**，位于 Service 层与 ORM 模型之间：

- **上层（Service）**：调用 Repository 提供的方法，专注业务逻辑，不直接接触 SQL
- **本层（Repository）**：封装所有 CRUD 操作，提供类型安全的数据接口
- **下层（ORM/SQLAlchemy）**：通过 AsyncSession 执行实际数据库操作

---

## 2. 目录结构

```text
Mymem/
├── repositories/
│   ├── __init__.py              # 统一导出
│   ├── base.py                  # Repository 基类（封装通用 CRUD）
│   ├── user_repository.py       # 用户操作
│   ├── category_repository.py   # 原子化记忆操作
│   ├── resource_repository.py   # 对话摘要+向量操作
│   └── resource_category_repository.py # 关联关系操作
```

---

## 3. 各 Repository 职责

### 3.1 UserRepository

| 方法 | 功能 |
|------|------|
| `create()` | 创建新用户 |
| `get_by_id()` | 通过 ID 获取用户 |
| `get_by_username()` | 通过用户名获取用户 |
| `update()` | 更新用户信息（人设模板等） |
| `delete()` | 删除用户（CASCADE 联动删除记忆） |

### 3.2 CategoryRepository

| 方法 | 功能 |
|------|------|
| `create_item()` | 创建一条原子化记忆 |
| `create_items_batch()` | 批量创建原子化记忆 |
| `get_by_id()` | 通过 ID 获取原子化记忆 |
| `get_by_user_id()` | 获取某用户所有原子化记忆 |
| `get_by_category_name()` | 获取某分类下所有原子化记忆 |
| `get_high_importance_items()` | 获取高重要性的原子化记忆 |
| `search_by_vector()` | **核心**：向量相似度检索（Category 层） |
| `search_by_content()` | 按内容关键词搜索 |
| `get_with_distance()` | 获取分类项及其与查询向量的余弦距离 |
| `update_content()` | 更新内容（合并/覆盖时使用） |
| `update_importance()` | 更新重要性分数 |
| `update_dynamic_category_names()` | 更新动态分类名称 |
| `get_category_stats()` | 获取各分类的统计信息 |
| `delete()` | 删除原子化记忆 |

### 3.3 ResourceRepository

| 方法 | 功能 |
|------|------|
| `create()` | 创建新对话摘要（含向量） |
| `get_by_id()` | 通过 ID 获取对话摘要 |
| `get_by_user_id()` | 获取某用户所有对话摘要 |
| `get_by_modality()` | 按模态筛选对话摘要 |
| `get_by_importance_range()` | 按重要性评分筛选 |
| `get_high_importance_resources()` | 获取高重要性资源（检索前预过滤） |
| `get_low_importance_resources()` | 获取低重要性资源（遗忘清理用） |
| `get_old_resources()` | 获取过期资源（遗忘清理用） |
| `search_by_vector()` | **核心**：向量相似度检索 |
| `search_by_vector_in_category()` | 在指定分类内进行向量检索 |
| `get_with_distance()` | 获取资源及其与查询向量的余弦距离 |
| `update_description_vector()` | 更新描述和向量 |
| `update_importance()` | 更新重要性分数 |
| `update_content()` | 更新内容（合并/覆盖时使用） |
| `delete()` | 删除对话摘要 |
| `delete_by_user()` | 删除某用户的所有对话摘要 |

### 3.4 ResourceCategoryRepository

| 方法 | 功能 |
|------|------|
| `create_relation()` | 创建关联关系 |
| `create_relations_batch()` | 批量创建关联关系 |
| `get_categories_for_resource()` | 获取某对话摘要提取的所有原子化记忆 |
| `get_resources_for_category()` | 获取某原子化记忆的所有来源 |
| `get_relation()` | 获取特定的关联关系 |
| `delete()` | 删除关联 |
| `delete_by_resource()` | 删除某对话摘要的所有关联 |
| `delete_by_category()` | 删除某原子化记忆的所有关联 |

---

## 4. BaseRepository 通用设计

BaseRepository 作为所有 Repository 的基类，封装通用的 CRUD 操作：

- **初始化**：接收 `AsyncSession` 和 ORM 模型类
- **get_by_id**：通过主键获取单个实体
- **get_all**：分页获取所有实体（支持 skip/limit）
- **create**：创建新实体，flush 后返回
- **update**：更新实体字段（仅更新提供的字段），返回更新后的实体
- **delete**：通过 ID 删除实体，返回是否成功
- **exists**：检查实体是否存在

---

## 5. 向量检索实现要点

### 5.1 CategoryRepository.search_by_vector()

Category 层向量检索：
1. 使用 `<=>` 操作符计算 `content_vector` 与查询向量的余弦距离
2. 按 `user_id` 和 `category_name` 筛选
3. 按四因子乘法评分排序（详见 `retrieval-pipeline/config/scoring.md`）
4. **返回值**：`list[tuple[Category, float]]`，每个元组包含 Category 对象和四因子评分

### 5.2 ResourceRepository.search_by_vector()

Resource 层向量检索：
1. 使用 `<=>` 操作符计算 `description_vector` 与查询向量的余弦距离
2. 按 `user_id` 和 `importance_score` 筛选候选集
3. 按四因子乘法评分排序（详见 `retrieval-pipeline/config/scoring.md`）
4. **返回值**：`list[Resource]`，仅返回 Resource 对象列表

> **注意**：向量字段使用 `Vector(settings.embedding_dimensions)` 类型，可直接在 SQL 中使用 `<=>` 操作符，无需手动编解码。维度通过 `.env` 的 `EMBEDDING_DIMENSIONS` 配置。

---

## 6. 依赖注入方式

Repository 的实例化遵循以下流程：

1. FastAPI 路由通过 `Depends(get_db)` 获取 `AsyncSession`
2. Service 层接收 session，实例化所需的 Repository
3. Repository 通过 session 执行数据库操作
4. 请求结束后 session 自动关闭

