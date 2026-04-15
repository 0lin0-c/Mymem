# [独立脚本] 用于首次连接数据库执行 DDL 建表指令
"""
数据库初始化脚本

使用方式：
    python init_db.py           # 创建表结构
    python init_db.py drop      # 删除所有表（谨慎使用）
    python init_db.py migrate   # 执行迁移

生命周期：
仅在项目环境搭建初期，或修改了表结构时由开发者手动执行。
"""
import asyncio
import sys

# Windows 编码设置
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from sqlalchemy import text

from core.config import settings
from core.database import engine
from tables.base import Base
from tables.user import User
from tables.category import Category
from tables.resource import Resource
from tables.resource_category import ResourceCategory


async def migrate_db():
    """迁移数据库表结构"""
    print("🔄 正在执行表结构迁移...")

    # 1. users 表迁移
    print("📋 迁移 users 表...")
    try:
        async with engine.begin() as conn:
            await conn.execute(text("""
                ALTER TABLE users ADD COLUMN IF NOT EXISTS password VARCHAR(255) NOT NULL DEFAULT '';
            """))
            await conn.execute(text("""
                ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
            """))
            # LLM 配置字段
            await conn.execute(text("""
                ALTER TABLE users ADD COLUMN IF NOT EXISTS llm_provider VARCHAR(50);
            """))
            await conn.execute(text("""
                ALTER TABLE users ADD COLUMN IF NOT EXISTS llm_api_key VARCHAR(255);
            """))
            await conn.execute(text("""
                ALTER TABLE users ADD COLUMN IF NOT EXISTS llm_base_url VARCHAR(255);
            """))
            await conn.execute(text("""
                ALTER TABLE users ADD COLUMN IF NOT EXISTS llm_model VARCHAR(100);
            """))
            await conn.execute(text("""
                ALTER TABLE users ADD COLUMN IF NOT EXISTS llm_warmed_up BOOLEAN NOT NULL DEFAULT FALSE;
            """))
        print("   ✅ users 表迁移完成")
    except Exception as e:
        print(f"   ⚠️ users 表迁移: {e}")

    # 2. resources 表迁移
    print("📋 迁移 resources 表...")
    try:
        async with engine.begin() as conn:
            await conn.execute(text("""
                ALTER TABLE resources ADD COLUMN IF NOT EXISTS assistant_response TEXT;
            """))
            await conn.execute(text("""
                ALTER TABLE resources ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE;
            """))
        print("   ✅ resources 表迁移完成")
    except Exception as e:
        print(f"   ⚠️ resources 表迁移: {e}")

    # 3. categories 表迁移（新结构）
    print("📋 迁移 categories 表...")
    try:
        async with engine.begin() as conn:
            # 检查是否存在旧结构的字段
            result = await conn.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'categories' AND column_name IN ('is_fixed', 'content_summary', 'source_resource_id');
            """))
            old_columns = [row[0] for row in result.fetchall()]

            if old_columns:
                # 重命名旧表
                await conn.execute(text("""
                    ALTER TABLE categories RENAME TO categories_old;
                """))

                # 创建新表
                await conn.execute(text("""
                    CREATE TABLE categories (
                        id VARCHAR(36) PRIMARY KEY,
                        user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        category_name VARCHAR(100) NOT NULL,
                        content TEXT NOT NULL,
                        importance_score INTEGER DEFAULT 5,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """))

                # 创建索引
                await conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_categories_user_id ON categories(user_id);
                """))
                await conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_categories_category_name ON categories(category_name);
                """))

                print("   ✅ categories 表结构已更新（旧表备份为 categories_old）")
            else:
                # 确保新表存在
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS categories (
                        id VARCHAR(36) PRIMARY KEY,
                        user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        category_name VARCHAR(100) NOT NULL,
                        content TEXT NOT NULL,
                        importance_score INTEGER DEFAULT 5,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """))
                print("   ✅ categories 表已创建")
    except Exception as e:
        print(f"   ⚠️ categories 表迁移: {e}")

    # 4. 创建 resource_categories 表
    print("📋 创建 resource_categories 表...")
    try:
        async with engine.begin() as conn:
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS resource_categories (
                    id VARCHAR(36) PRIMARY KEY,
                    resource_id VARCHAR(36) NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
                    category_id VARCHAR(36) NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
                    relation_type VARCHAR(20) DEFAULT 'created',
                    note TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_resource_categories_resource_id ON resource_categories(resource_id);
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_resource_categories_category_id ON resource_categories(category_id);
            """))
        print("   ✅ resource_categories 表创建成功")
    except Exception as e:
        print(f"   ⚠️ resource_categories 表创建: {e}")

    print("\n✅ 迁移完成！")


async def init_db():
    """初始化数据库表结构"""
    print("🔄 正在连接数据库...")

    async with engine.begin() as conn:
        # 1. 激活 pgvector 扩展
        print("📦 正在创建 pgvector 扩展...")
        try:
            await conn.execute(
                text("CREATE EXTENSION IF NOT EXISTS vector;")
            )
            print("✅ pgvector 扩展已激活")
        except Exception as e:
            print(f"⚠️ pgvector 扩展创建失败: {e}")

        # 2. 创建所有表
        print("📋 正在创建数据表...")
        await conn.run_sync(Base.metadata.create_all)
        print("✅ 所有数据表创建成功")

    print("\n🎉 数据库初始化完成！")
    print(f"   数据库地址: {settings.database_url}")


async def drop_db():
    """删除所有数据表（谨慎使用）"""
    print("⚠️  正在删除所有数据表...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        print("✅ 所有数据表已删除")


async def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "drop":
            await drop_db()
        elif sys.argv[1] == "migrate":
            await migrate_db()
        else:
            print("未知命令，可用: python init_db.py [drop|migrate]")
    else:
        await init_db()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
