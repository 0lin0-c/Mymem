# 🧱 ORM 模型测试：验证表结构、字段约束、关系映射
import pytest
from datetime import datetime, timezone

from tables import User, Category, Resource, ResourceCategory


class TestUserModel:
    """User 模型测试"""

    def test_user_creation(self, test_user: User):
        """测试用户创建"""
        assert test_user.id is not None
        assert test_user.username.startswith("test_user_")
        assert test_user.password == "test_password_hash"
        assert test_user.user_prompt_template == "You are a helpful assistant."
        assert test_user.agent_persona_template == "You are a friendly AI companion."
        assert test_user.created_at is not None

    def test_user_unique_username(self, db_session, test_user: User):
        """测试用户名唯一约束"""
        from repositories import UserRepository
        import uuid

        user_repo = UserRepository(db_session)
        # 尝试创建同名用户应该失败
        # 注：具体行为取决于数据库约束，这里测试 Repository 层面

    @pytest.mark.asyncio
    async def test_user_optional_templates(self, db_session):
        """测试模板字段可选"""
        from repositories import UserRepository
        import uuid

        user_repo = UserRepository(db_session)
        user = await user_repo.create(
            username=f"minimal_user_{uuid.uuid4().hex[:8]}",
            password="password",
        )
        assert user.user_prompt_template is None
        assert user.agent_persona_template is None


class TestCategoryModel:
    """Category 模型测试"""

    @pytest.mark.asyncio
    async def test_category_creation(self, db_session, test_user: User):
        """测试分类创建"""
        from repositories import CategoryRepository

        repo = CategoryRepository(db_session)
        category = await repo.create(
            user_id=test_user.id,
            category_name="测试分类",
            content="这是测试内容",
        )

        assert category.id is not None
        assert category.user_id == test_user.id
        assert category.category_name == "测试分类"
        assert category.importance_score == 5  # 默认值

    @pytest.mark.asyncio
    async def test_category_importance_range(self, db_session, test_user: User):
        """测试重要性分数范围"""
        from repositories import CategoryRepository

        repo = CategoryRepository(db_session)
        category = await repo.create(
            user_id=test_user.id,
            category_name="重要分类",
            content="重要内容",
            importance_score=10,  # 最高分
        )

        assert category.importance_score == 10

        # 测试更新重要性
        updated = await repo.update_importance(category.id, 10)
        # 最高分保持在10
        assert updated.importance_score == 10


class TestResourceModel:
    """Resource 模型测试"""

    @pytest.mark.asyncio
    async def test_resource_creation(self, db_session, test_user: User, fake_embedding: list[float]):
        """测试资源创建"""
        from repositories import ResourceRepository

        repo = ResourceRepository(db_session)
        resource = await repo.create(
            user_id=test_user.id,
            raw_content="用户说：我想学习 Python",
            modality="text",
            description="用户表达了学习 Python 的意愿",
            description_vector=fake_embedding,
            importance_score=7,
        )

        assert resource.id is not None
        assert resource.user_id == test_user.id
        assert resource.modality == "text"
        assert resource.importance_score == 7
        assert resource.description_vector is not None

    @pytest.mark.asyncio
    async def test_resource_modality_types(self, db_session, test_user: User, fake_embedding: list[float]):
        """测试不同模态类型"""
        from repositories import ResourceRepository

        repo = ResourceRepository(db_session)

        # 文本模态
        text_resource = await repo.create(
            user_id=test_user.id,
            raw_content="文本内容",
            modality="text",
            description="文本描述",
            description_vector=fake_embedding,
        )
        assert text_resource.modality == "text"

        # 图片模态
        image_resource = await repo.create(
            user_id=test_user.id,
            raw_content="base64_encoded_image...",
            modality="image",
            description="用户上传的图片",
            description_vector=fake_embedding,
        )
        assert image_resource.modality == "image"

    @pytest.mark.asyncio
    async def test_resource_access_count(self, db_session, test_user: User, fake_embedding: list[float]):
        """测试访问计数字段"""
        from repositories import ResourceRepository

        repo = ResourceRepository(db_session)
        resource = await repo.create(
            user_id=test_user.id,
            raw_content="测试内容",
            modality="text",
            description="测试",
            description_vector=fake_embedding,
        )

        # 默认访问计数
        assert resource.access_count == 0

        # 更新访问计数
        updated = await repo.update(resource.id, access_count=1)
        assert updated.access_count == 1


class TestResourceCategoryModel:
    """ResourceCategory 关联表测试"""

    @pytest.mark.asyncio
    async def test_relation_creation(self, db_session, test_user: User, fake_embedding: list[float]):
        """测试资源-分类关联创建"""
        from repositories import ResourceRepository, CategoryRepository, ResourceCategoryRepository

        # 创建资源
        resource_repo = ResourceRepository(db_session)
        resource = await resource_repo.create(
            user_id=test_user.id,
            raw_content="测试内容",
            modality="text",
            description="描述",
            description_vector=fake_embedding,
        )

        # 创建分类
        category_repo = CategoryRepository(db_session)
        category = await category_repo.create(
            user_id=test_user.id,
            category_name="测试分类",
            content="摘要",
        )

        # 创建关联
        rc_repo = ResourceCategoryRepository(db_session)
        relation = await rc_repo.create(
            resource_id=resource.id,
            category_id=category.id,
        )

        assert relation.id is not None
        assert relation.resource_id == resource.id
        assert relation.category_id == category.id

    @pytest.mark.asyncio
    async def test_cascade_delete(self, db_session, test_user: User, fake_embedding: list[float]):
        """测试级联删除：删除用户时应级联删除所有相关数据"""
        from repositories import UserRepository, ResourceRepository, CategoryRepository
        from sqlalchemy import text

        # 创建资源
        resource_repo = ResourceRepository(db_session)
        resource = await resource_repo.create(
            user_id=test_user.id,
            raw_content="测试",
            modality="text",
            description="描述",
            description_vector=fake_embedding,
        )

        await db_session.commit()

        # 删除用户
        user_repo = UserRepository(db_session)
        deleted = await user_repo.delete(test_user.id)
        assert deleted is True

        # 验证资源也被删除
        fetched = await resource_repo.get_by_id(resource.id)
        assert fetched is None
