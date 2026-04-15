# 🤖 LLM 服务测试：真实 API 调用
import pytest

from services.llm.factory import LLMFactory
from services.llm.base import BaseLLMProvider


class TestLLMProvider:
    """LLM Provider 基础功能测试"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_provider_initialization(self):
        """测试 LLM Provider 初始化"""
        llm = LLMFactory.get_provider()
        assert llm is not None
        assert isinstance(llm, BaseLLMProvider)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_generate_chat_response(self, llm_provider: BaseLLMProvider):
        """测试对话生成"""
        response = await llm_provider.generate_chat_response(
            system_prompt="你是一个友好的助手",
            context="",
            user_query="你好，请简单介绍一下你自己",
        )

        assert response is not None
        assert len(response) > 0
        assert isinstance(response, str)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_embedding(self, llm_provider: BaseLLMProvider):
        """测试获取向量"""
        embedding = await llm_provider.get_embedding("这是一个测试句子")

        assert embedding is not None
        assert isinstance(embedding, list)
        assert len(embedding) == 1536  # OpenAI embedding 维度
        assert all(isinstance(x, float) for x in embedding)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_embedding_consistency(self, llm_provider: BaseLLMProvider):
        """测试向量一致性：相同文本应得到相似向量"""
        text = "这是一段测试文本"

        embedding1 = await llm_provider.get_embedding(text)
        embedding2 = await llm_provider.get_embedding(text)

        # 计算余弦相似度
        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        norm1 = sum(a * a for a in embedding1) ** 0.5
        norm2 = sum(b * b for b in embedding2) ** 0.5
        similarity = dot_product / (norm1 * norm2)

        # 相同文本的向量相似度应该接近 1
        assert similarity > 0.99

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_embedding_semantic_similarity(self, llm_provider: BaseLLMProvider):
        """测试语义相似性：相似语义的文本应有更高相似度"""
        texts = {
            "apple": "我喜欢吃苹果",
            "fruit": "我喜欢吃水果",
            "coding": "我正在学习编程",
        }

        embeddings = {}
        for key, text in texts.items():
            embeddings[key] = await llm_provider.get_embedding(text)

        def cosine_similarity(v1, v2):
            dot = sum(a * b for a, b in zip(v1, v2))
            n1 = sum(a * a for a in v1) ** 0.5
            n2 = sum(b * b for b in v2) ** 0.5
            return dot / (n1 * n2)

        # "苹果" 和 "水果" 语义相似度应该较高
        fruit_similarity = cosine_similarity(embeddings["apple"], embeddings["fruit"])

        # "苹果" 和 "编程" 语义相似度应该较低
        coding_similarity = cosine_similarity(embeddings["apple"], embeddings["coding"])

        assert fruit_similarity > coding_similarity


class TestMemoryIntentExtraction:
    """记忆意图提取测试"""

    # 默认分类列表
    DEFAULT_CATEGORIES = [
        {"name": "核心自我", "description": "用户的身份、性格、价值观、偏好等核心特征"},
        {"name": "情景时间轴", "description": "用户经历的重要事件、日常活动和时间相关记忆"},
        {"name": "语义知识库", "description": "用户掌握的知识、技能、学习内容等"},
        {"name": "社交关系图谱", "description": "用户的社交网络、人际关系信息"},
    ]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_extract_memory_intent_basic(self, llm_provider: BaseLLMProvider):
        """测试基本记忆意图提取"""
        result = await llm_provider.extract_memory_intent(
            text="我最近在学习 Python 编程，主要使用 FastAPI 框架开发 Web 应用",
            categories=self.DEFAULT_CATEGORIES,
        )

        assert result is not None
        # 返回结构包含 summary, importance_score, atomic_items
        assert "summary" in result
        assert "importance_score" in result
        assert "atomic_items" in result

        # 验证 atomic_items 结构
        assert isinstance(result["atomic_items"], list)
        assert len(result["atomic_items"]) > 0

        # 验证每个 atomic_item 的结构
        valid_names = [c["name"] for c in self.DEFAULT_CATEGORIES]
        for item in result["atomic_items"]:
            assert "category_name" in item
            assert "content" in item
            assert "importance_score" in item
            assert item["category_name"] in valid_names
            assert 1 <= item["importance_score"] <= 10

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_extract_memory_intent_with_context(self, llm_provider: BaseLLMProvider):
        """测试带上下文的记忆意图提取"""
        result = await llm_provider.extract_memory_intent(
            text="我今天去了医院看病",
            categories=self.DEFAULT_CATEGORIES,
            assistant_response="希望你早日康复！有什么我可以帮助你的吗？",
        )

        assert result is not None
        assert "atomic_items" in result
        assert len(result["atomic_items"]) > 0
        # "今天去了医院" 应该归类到 "情景时间轴" 或 "核心自我"
        for item in result["atomic_items"]:
            assert item["category_name"] in ["情景时间轴", "核心自我"]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_extract_memory_intent_importance_high(self, llm_provider: BaseLLMProvider):
        """测试高重要性内容识别"""
        result = await llm_provider.extract_memory_intent(
            text="我叫张三，我的生日是3月15日，我是软件工程师",
            categories=self.DEFAULT_CATEGORIES,
        )

        assert result is not None
        # 个人身份信息应该归类到核心自我，且重要性较高
        core_self_items = [
            item for item in result["atomic_items"]
            if item["category_name"] == "核心自我"
        ]
        assert len(core_self_items) > 0
        # 核心自我的项目重要性应该较高
        for item in core_self_items:
            assert item["importance_score"] >= 7

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_extract_memory_intent_low_importance(self, llm_provider: BaseLLMProvider):
        """测试低重要性内容识别"""
        result = await llm_provider.extract_memory_intent(
            text="今天天气不错",
            categories=self.DEFAULT_CATEGORIES,
        )

        assert result is not None
        # 简单的日常对话整体重要性应该较低
        assert result["importance_score"] <= 5


class TestLLMCountTokens:
    """Token 计数测试"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_count_tokens(self, llm_provider: BaseLLMProvider):
        """测试 Token 计数"""
        text = "这是一段用于测试 token 计数的中文文本"

        token_count = await llm_provider.count_tokens(text)

        assert token_count is not None
        assert token_count > 0
        assert isinstance(token_count, int)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_count_tokens_empty(self, llm_provider: BaseLLMProvider):
        """测试空文本 Token 计数"""
        token_count = await llm_provider.count_tokens("")
        assert token_count == 0
