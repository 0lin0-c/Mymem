# 📚 Repository 层测试：CRUD + 真实向量检索
import pytest
import struct
from datetime import datetime, timezone

from tables import User, Category, Resource
from repositories import (
    UserRepository,
    CategoryRepository,
    ResourceRepository,
    ResourceCategoryRepository,
)


class TestUserRepository:
    """UserRepository CRUD 测试"""

    @pytest.mark.asyncio
    async def test_create_user(self, db_session):
        """测试创建用户"""
        repo = UserRepository(db_session)
        user = await repo.create(
            username="new_user_001",
            password="hashed_password",
        )

        assert user.id is not None
        assert user.username == "new_user_001"
        assert user.created_at is not None

    @pytest.mark.asyncio
    async def test_get_by_id(self, db_session, test_user: User):
        """测试通过 ID 获取用户"""
        repo = UserRepository(db_session)
        fetched = await repo.get_by_id(test_user.id)

        assert fetched is not None
        assert fetched.id == test_user.id
        assert fetched.username == test_user.username

    @pytest.mark.asyncio
    async def test_get_by_username(self, db_session, test_user: User):
        """测试通过用户名获取用户"""
        repo = UserRepository(db_session)
        fetched = await repo.get_by_username(test_user.username)

        assert fetched is not None
        assert fetched.id == test_user.id

    @pytest.mark.asyncio
    async def test_update_templates(self, db_session, test_user: User):
        """测试更新用户模板"""
        repo = UserRepository(db_session)
        updated = await repo.update_templates(
            test_user.id,
            user_prompt_template=b"Updated prompt",
            agent_persona_template=b"Updated persona",
        )

        assert updated is not None
        assert updated.user_prompt_template == b"Updated prompt"
        assert updated.agent_persona_template == b"Updated persona"

    @pytest.mark.asyncio
    async def test_exists(self, db_session, test_user: User):
        """测试检查用户存在性"""
        repo = UserRepository(db_session)

        exists = await repo.exists(test_user.id)
        assert exists is True

        not_exists = await repo.exists("non-existent-id")
        assert not_exists is False

    @pytest.mark.asyncio
    async def test_delete_user(self, db_session):
        """测试删除用户"""
        repo = UserRepository(db_session)

        # 创建用户
        user = await repo.create(
            username="user_to_delete",
            password="password",
        )

        # 删除
        deleted = await repo.delete(user.id)
        assert deleted is True

        # 验证已删除
        fetched = await repo.get_by_id(user.id)
        assert fetched is None


class TestCategoryRepository:
    """CategoryRepository CRUD 测试"""

    @pytest.mark.asyncio
    async def test_create_category(self, db_session, test_user: User):
        """测试创建分类"""
        repo = CategoryRepository(db_session)
        category = await repo.create(
            user_id=test_user.id,
            category_name="核心自我",
            content_summary="用户的静态画像",
            is_fixed=True,
        )

        assert category.id is not None
        assert category.category_name == "核心自我"
        assert category.importance_score == 5  # 默认值
        assert category.is_fixed is True

    @pytest.mark.asyncio
    async def test_get_by_user_id(self, db_session, test_user: User):
        """测试获取用户所有分类"""
        repo = CategoryRepository(db_session)

        # 创建多个分类
        for name in ["分类A", "分类B", "分类C"]:
            await repo.create(
                user_id=test_user.id,
                category_name=name,
                content_summary=f"{name}的内容",
            )

        categories = await repo.get_by_user_id(test_user.id)
        assert len(categories) >= 3

    @pytest.mark.asyncio
    async def test_get_by_name_and_user(self, db_session, test_user: User):
        """测试按名称查找分类"""
        repo = CategoryRepository(db_session)
        await repo.create(
            user_id=test_user.id,
            category_name="唯一分类",
            content_summary="内容",
        )

        found = await repo.get_by_name_and_user("唯一分类", test_user.id)
        assert found is not None
        assert found.category_name == "唯一分类"

        not_found = await repo.get_by_name_and_user("不存在的分类", test_user.id)
        assert not_found is None

    @pytest.mark.asyncio
    async def test_increment_importance(self, db_session, test_user: User):
        """测试增加重要性"""
        repo = CategoryRepository(db_session)
        category = await repo.create(
            user_id=test_user.id,
            category_name="测试分类",
            content_summary="内容",
            importance_score=5,
        )

        reinforced = await repo.increment_importance(category.id)
        assert reinforced.importance_score == 6

        # 再次增加
        reinforced = await repo.increment_importance(category.id)
        assert reinforced.importance_score == 7

    @pytest.mark.asyncio
    async def test_set_fixed(self, db_session, test_user: User):
        """测试设置固定分类"""
        repo = CategoryRepository(db_session)
        category = await repo.create(
            user_id=test_user.id,
            category_name="普通分类",
            content_summary="内容",
            is_fixed=False,
        )

        fixed = await repo.set_fixed(category.id, True)
        assert fixed.is_fixed is True

        unfixed = await repo.set_fixed(category.id, False)
        assert unfixed.is_fixed is False

    @pytest.mark.asyncio
    async def test_get_fixed_categories(self, db_session, test_user: User):
        """测试获取固定分类"""
        repo = CategoryRepository(db_session)

        # 创建固定和非固定分类
        await repo.create(
            user_id=test_user.id,
            category_name="固定分类1",
            content_summary="内容",
            is_fixed=True,
        )
        await repo.create(
            user_id=test_user.id,
            category_name="普通分类",
            content_summary="内容",
            is_fixed=False,
        )

        fixed = await repo.get_fixed_categories(test_user.id)
        assert len(fixed) >= 1
        assert all(c.is_fixed for c in fixed)


class TestResourceRepository:
    """ResourceRepository CRUD 测试"""

    @pytest.mark.asyncio
    async def test_create_resource(self, db_session, test_user: User, fake_embedding: list[float]):
        """测试创建资源"""
        repo = ResourceRepository(db_session)
        resource = await repo.create(
            user_id=test_user.id,
            raw_content="原始对话内容",
            modality="text",
            description="这是描述",
            description_vector=fake_embedding,
            importance_score=7,
        )

        assert resource.id is not None
        assert resource.raw_content == "原始对话内容"
        assert resource.importance_score == 7

    @pytest.mark.asyncio
    async def test_get_by_user_id(self, db_session, test_user: User, fake_embedding: list[float]):
        """测试获取用户所有资源"""
        repo = ResourceRepository(db_session)

        for i in range(3):
            await repo.create(
                user_id=test_user.id,
                raw_content=f"内容{i}",
                modality="text",
                description=f"描述{i}",
                description_vector=fake_embedding,
            )

        resources = await repo.get_by_user_id(test_user.id)
        assert len(resources) >= 3

    @pytest.mark.asyncio
    async def test_get_by_modality(self, db_session, test_user: User, fake_embedding: list[float]):
        """测试按模态筛选"""
        repo = ResourceRepository(db_session)

        await repo.create(
            user_id=test_user.id,
            raw_content="文本内容",
            modality="text",
            description="文本",
            description_vector=fake_embedding,
        )
        await repo.create(
            user_id=test_user.id,
            raw_content="图片数据",
            modality="image",
            description="图片",
            description_vector=fake_embedding,
        )

        text_resources = await repo.get_by_modality(test_user.id, "text")
        assert all(r.modality == "text" for r in text_resources)

    @pytest.mark.asyncio
    async def test_get_by_importance_range(self, db_session, test_user: User, fake_embedding: list[float]):
        """测试按重要性范围筛选"""
        repo = ResourceRepository(db_session)

        for score in [3, 5, 8, 10]:
            await repo.create(
                user_id=test_user.id,
                raw_content=f"重要性{score}",
                modality="text",
                description=f"描述{score}",
                description_vector=fake_embedding,
                importance_score=score,
            )

        high_importance = await repo.get_by_importance_range(test_user.id, 7, 10)
        assert all(7 <= r.importance_score <= 10 for r in high_importance)

    @pytest.mark.asyncio
    async def test_update_description_vector(self, db_session, test_user: User, fake_embedding: list[float]):
        """测试更新描述和向量"""
        repo = ResourceRepository(db_session)
        resource = await repo.create(
            user_id=test_user.id,
            raw_content="内容",
            modality="text",
            description="原始描述",
            description_vector=fake_embedding,
        )

        # 生成新的向量
        import random
        new_vec = [random.gauss(0, 1) for _ in range(1536)]
        norm = sum(x * x for x in new_vec) ** 0.5
        new_vec = [x / norm for x in new_vec]

        updated = await repo.update_description_vector(
            resource.id,
            description="更新后的描述",
            description_vector=new_vec,
        )

        assert updated.description == "更新后的描述"


class TestVectorSearch:
    """向量检索测试（使用真实 embedding）"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.vector
    async def test_search_by_vector_real(
        self,
        db_session,
        test_user: User,
        llm_provider,
        sample_embedding: list[float],
    ):
        """测试真实向量检索"""
        repo = ResourceRepository(db_session)

        # 创建几个带真实向量的资源
        texts = [
            "我喜欢吃苹果和香蕉",
            "我正在学习 Python 编程",
            "我每天早上跑步锻炼",
        ]

        for text in texts:
            embedding = await llm_provider.get_embedding(text)
            await repo.create(
                user_id=test_user.id,
                raw_content=text,
                modality="text",
                description=text,
                description_vector=embedding,
                importance_score=5,
            )

        await db_session.commit()

        # 用相似语义查询
        query = "我喜欢吃水果"
        query_embedding = await llm_provider.get_embedding(query)

        results = await repo.search_by_vector(
            user_id=test_user.id,
            query_vector=query_embedding,
            top_k=3,
        )

        assert len(results) >= 1
        # "我喜欢吃苹果和香蕉" 应该排在前面
        assert "苹果" in results[0].description or "香蕉" in results[0].description

    @pytest.mark.asyncio
    @pytest.mark.vector
    async def test_search_by_vector_similar(
        self,
        db_session,
        test_user: User,
        similar_embeddings: tuple[list[float], list[float]],
    ):
        """测试相似向量检索"""
        repo = ResourceRepository(db_session)
        base_vec, similar_vec = similar_embeddings

        # 创建带基础向量的资源
        resource = await repo.create(
            user_id=test_user.id,
            raw_content="原始内容",
            modality="text",
            description="原始描述",
            description_vector=base_vec,
            importance_score=5,
        )

        await db_session.commit()

        # 用相似向量查询
        results = await repo.search_by_vector(
            user_id=test_user.id,
            query_vector=similar_vec,
            top_k=1,
        )

        assert len(results) == 1
        assert results[0].id == resource.id

    @pytest.mark.asyncio
    @pytest.mark.vector
    async def test_search_by_vector_in_category(
        self,
        db_session,
        test_user: User,
        fake_embedding: list[float],
    ):
        """测试分类内向量检索"""
        resource_repo = ResourceRepository(db_session)
        category_repo = CategoryRepository(db_session)
        rc_repo = ResourceCategoryRepository(db_session)

        # 创建分类
        category = await category_repo.create(
            user_id=test_user.id,
            category_name="编程学习",
            content_summary="关于编程的学习内容",
        )

        # 创建资源并关联到分类
        resource = await resource_repo.create(
            user_id=test_user.id,
            raw_content="我在学习 FastAPI",
            modality="text",
            description="学习 FastAPI 框架",
            description_vector=fake_embedding,
            importance_score=5,
        )

        await rc_repo.create(
            resource_id=resource.id,
            category_id=category.id,
        )

        # 创建另一个不在该分类的资源
        other_resource = await resource_repo.create(
            user_id=test_user.id,
            raw_content="我喜欢看电影",
            modality="text",
            description="娱乐活动",
            description_vector=fake_embedding,
            importance_score=5,
        )

        await db_session.commit()

        # 在分类内搜索
        results = await resource_repo.search_by_vector_in_category(
            user_id=test_user.id,
            category_id=category.id,
            query_vector=fake_embedding,
            top_k=5,
        )

        # 应该只返回分类内的资源
        assert len(results) >= 1
        resource_ids = [r[0].id for r in results]
        assert resource.id in resource_ids
        assert other_resource.id not in resource_ids


class TestResourceCategoryRepository:
    """ResourceCategoryRepository CRUD 测试"""

    @pytest.mark.asyncio
    async def test_create_relation(self, db_session, test_user: User, fake_embedding: list[float]):
        """测试创建关联"""
        resource_repo = ResourceRepository(db_session)
        category_repo = CategoryRepository(db_session)
        rc_repo = ResourceCategoryRepository(db_session)

        resource = await resource_repo.create(
            user_id=test_user.id,
            raw_content="内容",
            modality="text",
            description="描述",
            description_vector=fake_embedding,
        )
        category = await category_repo.create(
            user_id=test_user.id,
            category_name="分类",
            content_summary="摘要",
        )

        relation = await rc_repo.create(
            resource_id=resource.id,
            category_id=category.id,
        )

        assert relation.id is not None
        assert relation.resource_id == resource.id
        assert relation.category_id == category.id

    @pytest.mark.asyncio
    async def test_exists(self, db_session, test_user: User, fake_embedding: list[float]):
        """测试检查关联存在性"""
        resource_repo = ResourceRepository(db_session)
        category_repo = CategoryRepository(db_session)
        rc_repo = ResourceCategoryRepository(db_session)

        resource = await resource_repo.create(
            user_id=test_user.id,
            raw_content="内容",
            modality="text",
            description="描述",
            description_vector=fake_embedding,
        )
        category = await category_repo.create(
            user_id=test_user.id,
            category_name="分类",
            content_summary="摘要",
        )
        await rc_repo.create(resource_id=resource.id, category_id=category.id)

        exists = await rc_repo.exists(resource.id, category.id)
        assert exists is True

        not_exists = await rc_repo.exists(resource.id, "non-existent-category")
        assert not_exists is False

    @pytest.mark.asyncio
    async def test_get_categories_for_resource(self, db_session, test_user: User, fake_embedding: list[float]):
        """测试获取资源的所有分类"""
        resource_repo = ResourceRepository(db_session)
        category_repo = CategoryRepository(db_session)
        rc_repo = ResourceCategoryRepository(db_session)

        resource = await resource_repo.create(
            user_id=test_user.id,
            raw_content="内容",
            modality="text",
            description="描述",
            description_vector=fake_embedding,
        )

        # 创建多个分类并关联
        for name in ["分类A", "分类B"]:
            category = await category_repo.create(
                user_id=test_user.id,
                category_name=name,
                content_summary=name,
            )
            await rc_repo.create(resource_id=resource.id, category_id=category.id)

        categories = await rc_repo.get_categories_for_resource(resource.id)
        assert len(categories) >= 2

    @pytest.mark.asyncio
    async def test_get_resources_for_category(self, db_session, test_user: User, fake_embedding: list[float]):
        """测试获取分类的所有资源"""
        resource_repo = ResourceRepository(db_session)
        category_repo = CategoryRepository(db_session)
        rc_repo = ResourceCategoryRepository(db_session)

        category = await category_repo.create(
            user_id=test_user.id,
            category_name="分类",
            content_summary="摘要",
        )

        # 创建多个资源并关联到同一分类
        for i in range(3):
            resource = await resource_repo.create(
                user_id=test_user.id,
                raw_content=f"内容{i}",
                modality="text",
                description=f"描述{i}",
                description_vector=fake_embedding,
            )
            await rc_repo.create(resource_id=resource.id, category_id=category.id)

        resources = await rc_repo.get_resources_for_category(category.id)
        assert len(resources) >= 3
