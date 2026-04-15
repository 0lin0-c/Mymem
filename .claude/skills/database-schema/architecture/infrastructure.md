# 核心 Python 文件功能规范

本文档定义数据库层基础设施文件的功能定位。

---

## 1. `core/database.py` (基础设施)

* **功能**：负责读取 NAS 数据库的连接字符串，实例化 SQLAlchemy 的 `AsyncEngine` 和 `async_sessionmaker`。
* **后续如何被调用**：在此文件内提供一个 `get_db()` 的异步生成器函数。后续在 FastAPI 的路由中，通过 `Depends(get_db)` 作为依赖注入，使得每个 HTTP 请求都能获得一个独立的、生命周期受控的数据库连接会话（Session），并在请求结束后自动关闭，防止内存泄漏。

---

## 2. `tables/base.py` (映射契约)

* **功能**：仅包含 `class Base(DeclarativeBase): pass`。
* **为什么独立出一个文件**：为了避免循环导入 (Circular Import)。所有的具体数据表模型必须继承自同一个 Base 对象，这样 SQLAlchemy 的 MetaData 才能收集到所有的表结构，从而执行统一的 `create_all` 建表操作。

---

## 3. `tables/*.py` (实体类)

* **功能**：利用 SQLAlchemy 2.0 的 `Mapped` 和 `mapped_column` 类型提示，清晰地定义字段约束。
* **后续如何被调用**：在业务逻辑层（如 `memory/writer.py`）中，我们不需要写 SQL 语句，而是通过 Repository 层的方法操作数据。

---

## 4. `init_db.py` (执行脚本)

* **功能**：一个极其简单的一次性脚本。它会导入所有的实体类，连接到 NAS 数据库，强制执行 `CREATE EXTENSION IF NOT EXISTS vector;` 激活向量大脑，随后通过 `Base.metadata.create_all` 向数据库发送 DDL (Data Definition Language) 语句，完成物理建表。
* **生命周期**：仅在项目环境搭建初期，或修改了表结构（且未使用 Alembic 迁移工具时）由开发者手动在终端执行一次。
