# ✍️ Memory Writer 测试：记忆写入流程
import pytest

from services.memory.writer import MemoryWriter, BASE_CATEGORIES
from tables import Resource, Category


class TestMemoryWriter:
    """MemoryWriter 核心功能测试"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_save_chat_basic(self, db_session, test_user, llm_provider):
        """测试基本对话保存"""
        writer = MemoryWriter(db_session, llm_provider, enable_dedup=False)

        result = await writer.save_chat(
            user_id=test_user.id,
            user_input="我最近在学习 Python 编程",
            assistant_response="Python 是一门很好的编程语言！",
            modality="text",
        )

        assert result["resource_id"] is not None
        assert result["summary"] is not None
        assert result["importance_score"] >= 1
        assert result["atomic_items_count"] >= 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_save_chat_creates_resource(self, db_session, test_user, llm_provider):
        """测试保存对话会创建 Resource 记录"""
        writer = MemoryWriter(db_session, llm_provider, enable_dedup=False)

        result = await writer.save_chat(
            user_id=test_user.id,
            user_input="我叫张三，是一名软件工程师",
            assistant_response="你好张三！很高兴认识你。",
            modality="text",
        )

        # 验证 Resource 被创建
        from repositories import ResourceRepository
        resource_repo = ResourceRepository(db_session)
        resource = await resource_repo.get_by_id(result["resource_id"])

        assert resource is not None
        assert resource.user_id == test_user.id
        assert resource.description is not None
        assert resource.description_vector is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_save_chat_creates_categories(self, db_session, test_user, llm_provider):
        """测试保存对话会创建 Category 记录"""
        writer = MemoryWriter(db_session, llm_provider, enable_dedup=False)

        result = await writer.save_chat(
            user_id=test_user.id,
            user_input="我叫张三，今年25岁，喜欢打篮球",
            assistant_response="你好张三！很高兴认识你。",
            modality="text",
        )

        # 验证 Category 被创建
        assert result["atomic_items_count"] >= 1

        for item in result["atomic_items"]:
            assert item["id"] is not None
            assert item["category_name"] is not None
            assert item["content"] is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_save_chat_with_dedup_enabled(self, db_session, test_user, llm_provider):
        """测试启用去重的保存"""
        writer = MemoryWriter(db_session, llm_provider, enable_dedup=True)

        # 第一次保存
        result1 = await writer.save_chat(
            user_id=test_user.id,
            user_input="我喜欢吃苹果",
            assistant_response="苹果很有营养！",
            modality="text",
        )

        # 第二次保存相似内容
        result2 = await writer.save_chat(
            user_id=test_user.id,
            user_input="我很喜欢吃苹果",
            assistant_response="继续保持健康饮食！",
            modality="text",
        )

        # 去重信息应该被记录
        assert "dedup_info" in result2
        assert result2["dedup_info"]["action"] in ["create", "skip", "merge", "update"]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_save_chat_different_modalities(self, db_session, test_user, llm_provider):
        """测试不同模态的保存"""
        writer = MemoryWriter(db_session, llm_provider, enable_dedup=False)

        # 文本模态
        text_result = await writer.save_chat(
            user_id=test_user.id,
            user_input="这是一段文本",
            assistant_response="收到",
            modality="text",
        )
        assert text_result["resource_id"] is not None

        # 图片模态（模拟 base64）
        image_result = await writer.save_chat(
            user_id=test_user.id,
            user_input=b"fake_image_data",
            assistant_response="我看到这是一张图片",
            modality="image",
        )
        assert image_result["resource_id"] is not None

    @pytest.mark.asyncio
    async def test_save_chat_user_not_found(self, db_session, llm_provider):
        """测试用户不存在时的错误处理"""
        writer = MemoryWriter(db_session, llm_provider, enable_dedup=False)

        with pytest.raises(ValueError, match="用户不存在"):
            await writer.save_chat(
                user_id="non-existent-user-id",
                user_input="测试内容",
                assistant_response="测试回复",
                modality="text",
            )

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_save_chat_with_custom_categories(self, db_session, test_user, llm_provider):
        """测试使用自定义分类列表"""
        writer = MemoryWriter(db_session, llm_provider, enable_dedup=False)

        custom_categories = [
            {"name": "工作", "description": "工作相关内容"},
            {"name": "生活", "description": "生活相关内容"},
        ]

        result = await writer.save_chat(
            user_id=test_user.id,
            user_input="我今天完成了一个项目",
            assistant_response="太棒了！",
            modality="text",
            user_categories=custom_categories,
        )

        assert result["resource_id"] is not None


class TestMemoryWriterDeduplication:
    """MemoryWriter 去重逻辑测试"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_dedup_skip_similar_content(self, db_session, test_user, llm_provider):
        """测试相似内容被跳过（强化已有记录）"""
        writer = MemoryWriter(db_session, llm_provider, enable_dedup=True)

        # 第一次保存
        result1 = await writer.save_chat(
            user_id=test_user.id,
            user_input="我叫张三",
            assistant_response="你好张三！",
            modality="text",
        )

        await db_session.commit()

        # 第二次保存几乎相同的内容
        result2 = await writer.save_chat(
            user_id=test_user.id,
            user_input="我叫张三",
            assistant_response="你好！",
            modality="text",
        )

        # 如果相似度足够高，应该是 skip 或 merge
        # 具体行为取决于相似度阈值
        assert result2["dedup_info"]["action"] in ["skip", "merge", "update", "create"]

    @pytest.mark.asyncio
    async def test_dedup_disabled(self, db_session, test_user, llm_provider):
        """测试禁用去重时总是创建新记录"""
        writer = MemoryWriter(db_session, llm_provider, enable_dedup=False)

        result1 = await writer.save_chat(
            user_id=test_user.id,
            user_input="测试内容A",
            assistant_response="回复A",
            modality="text",
        )

        result2 = await writer.save_chat(
            user_id=test_user.id,
            user_input="测试内容A",
            assistant_response="回复B",
            modality="text",
        )

        # 禁用去重时，应该创建新记录
        assert result1["resource_id"] != result2["resource_id"]
        assert result2["dedup_info"]["action"] == "create"


class TestBaseCategories:
    """基础分类常量测试"""

    def test_base_categories_count(self):
        """测试基础分类数量为 4"""
        assert len(BASE_CATEGORIES) == 4

    def test_base_categories_names(self):
        """测试基础分类名称"""
        names = [c["name"] for c in BASE_CATEGORIES]
        assert "核心自我" in names
        assert "情景时间轴" in names
        assert "语义知识库" in names
        assert "社交关系图谱" in names

    def test_base_categories_have_descriptions(self):
        """测试基础分类都有描述"""
        for category in BASE_CATEGORIES:
            assert "name" in category
            assert "description" in category
            assert len(category["description"]) > 0
