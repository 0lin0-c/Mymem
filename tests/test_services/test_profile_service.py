# 🧠 Profile Service 测试：用户初始化、画像更新、AI 定制
import pytest

from services.profile_service import ProfileService, BASE_CATEGORIES
from schemas.onboarding_schema import (
    OnboardingRequest,
    IdentityDetail,
    AICustomization,
    ProfileUpdateRequest,
    AICustomizationUpdateRequest,
)


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

    def test_base_categories_structure(self):
        """测试基础分类结构"""
        for category in BASE_CATEGORIES:
            assert "name" in category
            assert "description" in category
            assert isinstance(category["name"], str)
            assert isinstance(category["description"], str)


class TestGenerateUserPromptTemplate:
    """user_prompt_template 生成测试"""

    @pytest.fixture
    def profile_service(self, db_session, llm_provider):
        """创建 ProfileService 实例"""
        return ProfileService(db_session, llm_provider)

    def test_student_template(self, profile_service):
        """测试学生模板生成"""
        request = OnboardingRequest(
            username="张三",
            identity_type="student",
            identity_detail=IdentityDetail(
                education_stage="college",
                major="计算机科学",
            ),
            ai_customization=AICustomization(
                ai_name="小助手",
                ai_role="assistant",
            ),
        )

        template = profile_service._generate_user_prompt_template(request)

        assert "张三" in template
        assert "学生" in template
        assert "大学" in template
        assert "计算机科学" in template

    def test_worker_template(self, profile_service):
        """测试上班族模板生成"""
        request = OnboardingRequest(
            username="李四",
            identity_type="worker",
            identity_detail=IdentityDetail(
                industry="互联网",
                job_title="工程师",
            ),
            ai_customization=AICustomization(
                ai_name="小助手",
                ai_role="assistant",
            ),
        )

        template = profile_service._generate_user_prompt_template(request)

        assert "李四" in template
        assert "上班族" in template
        assert "互联网" in template
        assert "工程师" in template

    def test_teacher_template(self, profile_service):
        """测试教师模板生成"""
        request = OnboardingRequest(
            username="王老师",
            identity_type="teacher",
            identity_detail=IdentityDetail(
                subject="数学",
            ),
            ai_customization=AICustomization(
                ai_name="小助手",
                ai_role="assistant",
            ),
        )

        template = profile_service._generate_user_prompt_template(request)

        assert "王老师" in template
        assert "教师" in template
        assert "数学" in template

    def test_freelancer_template(self, profile_service):
        """测试自由职业者模板生成"""
        request = OnboardingRequest(
            username="赵六",
            identity_type="freelancer",
            identity_detail=IdentityDetail(
                field="设计",
            ),
            ai_customization=AICustomization(
                ai_name="小助手",
                ai_role="assistant",
            ),
        )

        template = profile_service._generate_user_prompt_template(request)

        assert "赵六" in template
        assert "自由职业者" in template

    def test_other_identity_template(self, profile_service):
        """测试其他身份模板生成"""
        request = OnboardingRequest(
            username="用户A",
            identity_type="other",
            ai_customization=AICustomization(
                ai_name="小助手",
                ai_role="assistant",
            ),
        )

        template = profile_service._generate_user_prompt_template(request)

        assert "用户A" in template
        assert "其他" in template


class TestGenerateAgentPersonaTemplate:
    """agent_persona_template 生成测试"""

    @pytest.fixture
    def profile_service(self, db_session, llm_provider):
        return ProfileService(db_session, llm_provider)

    def test_assistant_role(self, profile_service):
        """测试助手角色"""
        request = OnboardingRequest(
            username="张三",
            identity_type="student",
            ai_customization=AICustomization(
                ai_name="小助手",
                ai_role="assistant",
                personality=["耐心", "细致"],
                communication_style="casual",
            ),
        )

        template = profile_service._generate_agent_persona_template(request)

        assert "小助手" in template
        assert "助手" in template
        assert "耐心" in template or "细致" in template
        assert "轻松随意" in template

    def test_mentor_role(self, profile_service):
        """测试导师角色"""
        request = OnboardingRequest(
            username="李四",
            identity_type="worker",
            ai_customization=AICustomization(
                ai_name="导师A",
                ai_role="mentor",
                communication_style="academic",
            ),
        )

        template = profile_service._generate_agent_persona_template(request)

        assert "导师A" in template
        assert "导师" in template
        assert "学术专业" in template

    def test_friend_role(self, profile_service):
        """测试朋友角色"""
        request = OnboardingRequest(
            username="王五",
            identity_type="student",
            ai_customization=AICustomization(
                ai_name="小明",
                ai_role="friend",
                communication_style="daily",
            ),
        )

        template = profile_service._generate_agent_persona_template(request)

        assert "小明" in template
        assert "朋友" in template

    def test_with_personality(self, profile_service):
        """测试带性格特点"""
        request = OnboardingRequest(
            username="测试",
            identity_type="student",
            ai_customization=AICustomization(
                ai_name="AI",
                ai_role="assistant",
                personality=["幽默", "活泼", "热情"],
            ),
        )

        template = profile_service._generate_agent_persona_template(request)

        assert "幽默" in template or "活泼" in template


class TestDynamicCategoryGeneration:
    """动态分类生成测试"""

    @pytest.fixture
    def profile_service(self, db_session, llm_provider):
        return ProfileService(db_session, llm_provider)

    def test_get_default_categories_student(self, profile_service):
        """测试学生默认分类"""
        request = OnboardingRequest(
            username="张三",
            identity_type="student",
            ai_customization=AICustomization(
                ai_name="小助手",
                ai_role="assistant",
            ),
        )

        categories = profile_service._get_default_dynamic_categories(request)

        assert len(categories) == 2
        names = [c["name"] for c in categories]
        assert "学校生活" in names
        assert "考试与升学" in names

    def test_get_default_categories_worker(self, profile_service):
        """测试上班族默认分类"""
        request = OnboardingRequest(
            username="李四",
            identity_type="worker",
            ai_customization=AICustomization(
                ai_name="小助手",
                ai_role="assistant",
            ),
        )

        categories = profile_service._get_default_dynamic_categories(request)

        assert len(categories) == 2
        names = [c["name"] for c in categories]
        assert "项目研发" in names

    def test_get_default_categories_teacher(self, profile_service):
        """测试教师默认分类"""
        request = OnboardingRequest(
            username="王老师",
            identity_type="teacher",
            ai_customization=AICustomization(
                ai_name="小助手",
                ai_role="assistant",
            ),
        )

        categories = profile_service._get_default_dynamic_categories(request)

        assert len(categories) == 2
        names = [c["name"] for c in categories]
        assert "教学教务" in names

    def test_get_default_categories_freelancer(self, profile_service):
        """测试自由职业者默认分类"""
        request = OnboardingRequest(
            username="赵六",
            identity_type="freelancer",
            ai_customization=AICustomization(
                ai_name="小助手",
                ai_role="assistant",
            ),
        )

        categories = profile_service._get_default_dynamic_categories(request)

        assert len(categories) == 2
        names = [c["name"] for c in categories]
        assert "项目作品" in names

    def test_get_default_categories_other(self, profile_service):
        """测试其他身份默认分类"""
        request = OnboardingRequest(
            username="用户A",
            identity_type="other",
            ai_customization=AICustomization(
                ai_name="小助手",
                ai_role="assistant",
            ),
        )

        categories = profile_service._get_default_dynamic_categories(request)

        assert len(categories) == 2
        names = [c["name"] for c in categories]
        assert "生活记录" in names

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_generate_dynamic_categories_with_llm(self, profile_service):
        """测试 LLM 生成动态分类"""
        request = OnboardingRequest(
            username="张三",
            identity_type="student",
            identity_detail=IdentityDetail(
                education_stage="college",
                major="人工智能",
            ),
            interests=["编程", "机器学习"],
            ai_customization=AICustomization(
                ai_name="小助手",
                ai_role="mentor",
            ),
        )

        names = await profile_service._generate_dynamic_category_names(request)

        assert len(names) <= 2
        assert all(isinstance(name, str) for name in names)


class TestOnboarding:
    """用户初始化完整流程测试"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_onboarding_success(self, db_session, llm_provider):
        """测试成功初始化"""
        service = ProfileService(db_session, llm_provider)

        request = OnboardingRequest(
            username="测试用户",
            identity_type="student",
            identity_detail=IdentityDetail(
                education_stage="college",
                major="计算机",
            ),
            interests=["编程", "阅读"],
            use_cases=["学习辅导", "日常聊天"],
            ai_customization=AICustomization(
                ai_name="小助手",
                ai_role="assistant",
                personality=["耐心"],
                communication_style="casual",
            ),
        )

        response = await service.onboarding(request)

        assert response.success is True
        assert response.user_id is not None
        assert response.user_prompt_template is not None
        assert response.agent_persona_template is not None
        assert response.initial_categories is not None

        # 验证分类结构
        assert "fixed" in response.initial_categories
        assert "dynamic" in response.initial_categories
        assert len(response.initial_categories["fixed"]) == 4

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_onboarding_creates_user(self, db_session, llm_provider):
        """测试初始化创建用户"""
        from repositories import UserRepository

        service = ProfileService(db_session, llm_provider)

        request = OnboardingRequest(
            username="新用户A",
            identity_type="student",
            ai_customization=AICustomization(
                ai_name="AI",
                ai_role="assistant",
            ),
        )

        response = await service.onboarding(request)

        # 验证用户已创建
        user_repo = UserRepository(db_session)
        user = await user_repo.get_by_id(response.user_id)

        assert user is not None
        assert user.username == "新用户A"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_onboarding_stores_profile_in_categories(self, db_session, llm_provider):
        """测试初始化信息存入 Category"""
        from repositories import CategoryRepository

        service = ProfileService(db_session, llm_provider)

        request = OnboardingRequest(
            username="测试B",
            identity_type="student",
            interests=["音乐", "运动"],
            use_cases=["学习"],
            ai_customization=AICustomization(
                ai_name="AI",
                ai_role="assistant",
            ),
        )

        response = await service.onboarding(request)

        # 验证分类项已创建
        category_repo = CategoryRepository(db_session)
        categories = await category_repo.get_by_user_id(response.user_id)

        # 应该有核心自我的记录
        core_items = [c for c in categories if c.category_name == "核心自我"]
        assert len(core_items) >= 2  # 姓名 + 身份


class TestProfileUpdate:
    """用户画像更新测试"""

    @pytest.mark.asyncio
    async def test_update_profile_success(self, db_session, test_user, llm_provider):
        """测试成功更新画像"""
        service = ProfileService(db_session, llm_provider)

        request = ProfileUpdateRequest(
            user_id=test_user.id,
            identity_type="worker",
            identity_detail=IdentityDetail(
                industry="科技",
                job_title="开发工程师",
            ),
            interests=["Python", "AI"],
        )

        result = await service.update_profile(request)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_update_profile_user_not_found(self, db_session, llm_provider):
        """测试用户不存在时更新"""
        service = ProfileService(db_session, llm_provider)

        request = ProfileUpdateRequest(
            user_id="non-existent-user",
            identity_type="student",
        )

        result = await service.update_profile(request)

        assert result["success"] is False
        assert "不存在" in result["message"]


class TestAICustomizationUpdate:
    """AI 助手定制更新测试"""

    @pytest.mark.asyncio
    async def test_update_ai_customization_success(self, db_session, test_user, llm_provider):
        """测试成功更新 AI 定制"""
        service = ProfileService(db_session, llm_provider)

        request = AICustomizationUpdateRequest(
            user_id=test_user.id,
            ai_name="新名字",
            ai_role="mentor",
            personality=["专业", "严谨"],
            communication_style="academic",
        )

        result = await service.update_ai_customization(request)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_update_ai_customization_user_not_found(self, db_session, llm_provider):
        """测试用户不存在时更新 AI 定制"""
        service = ProfileService(db_session, llm_provider)

        request = AICustomizationUpdateRequest(
            user_id="non-existent-user",
            ai_name="AI",
        )

        result = await service.update_ai_customization(request)

        assert result["success"] is False


class TestJSONExtraction:
    """JSON 提取测试"""

    @pytest.fixture
    def profile_service(self, db_session, llm_provider):
        return ProfileService(db_session, llm_provider)

    def test_extract_json_from_response_direct(self, profile_service):
        """测试直接 JSON 响应"""
        response = '[{"name": "分类A"}, {"name": "分类B"}]'

        result = profile_service._extract_json_from_response(response)

        assert len(result) == 2
        assert result[0]["name"] == "分类A"

    def test_extract_json_from_response_wrapped(self, profile_service):
        """测试包装的 JSON 响应"""
        response = '{"dynamic_categories": [{"name": "分类A"}, {"name": "分类B"}]}'

        result = profile_service._extract_json_from_response(response)

        assert len(result) == 2

    def test_extract_json_from_response_mixed_text(self, profile_service):
        """测试混合文本的 JSON 响应"""
        response = '''
        根据用户画像，我建议以下分类：
        {"dynamic_categories": [{"name": "学习笔记"}, {"name": "生活记录"}]}
        希望这些建议有帮助！
        '''

        result = profile_service._extract_json_from_response(response)

        assert len(result) == 2

    def test_extract_json_from_response_invalid(self, profile_service):
        """测试无效 JSON 响应"""
        response = "这不是 JSON 格式的响应"

        result = profile_service._extract_json_from_response(response)

        assert result == []


class TestGetAllCategoryNames:
    """获取所有分类名称测试"""

    @pytest.fixture
    def profile_service(self, db_session, llm_provider):
        return ProfileService(db_session, llm_provider)

    def test_get_all_category_names(self, profile_service):
        """测试获取所有 6 个分类名称"""
        dynamic_names = ["学习笔记", "生活记录"]

        all_names = profile_service.get_all_category_names(dynamic_names)

        assert len(all_names) == 6
        assert "核心自我" in all_names
        assert "学习笔记" in all_names
