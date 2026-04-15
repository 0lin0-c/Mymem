# 🖥️ 命令行测试脚本（直接调用 Service 层，无需启动服务）
# 运行方式: python -m test.test_chat_cli
import asyncio
import sys
import uuid

sys.stdout.reconfigure(encoding='utf-8')

from core.database import AsyncSessionLocal
from services.llm import LLMFactory
from services.session import session_manager, UserIdentifier
from services.memory import MemoryWriter
from services.profile_service import ProfileService
from schemas.onboarding_schema import OnboardingRequest, IdentityDetail, AICustomization
from tables import User

# chat 模态累积多少轮后存储
CHAT_BATCH_SIZE = 5


# ========== Onboarding 测试 ==========

async def test_onboarding():
    """测试用户初始化流程"""
    print("\n" + "=" * 50)
    print("📋 用户初始化测试")
    print("=" * 50)

    # 收集用户输入
    print("\n请填写以下信息：\n")

    username = input("用户名: ").strip()
    if not username:
        print("用户名不能为空")
        return

    print("\n身份类型:")
    print("  1. 学生 (student)")
    print("  2. 上班族 (worker)")
    print("  3. 教师 (teacher)")
    print("  4. 自由职业者 (freelancer)")
    print("  5. 其他 (other)")

    identity_choice = input("请选择 (1-5): ").strip()
    identity_map = {"1": "student", "2": "worker", "3": "teacher", "4": "freelancer", "5": "other"}
    identity_type = identity_map.get(identity_choice, "other")

    # 收集身份详情
    identity_detail = IdentityDetail()
    if identity_type == "student":
        print("\n学段:")
        print("  1. 小学  2. 初中  3. 高中  4. 大学  5. 研究生")
        stage_choice = input("请选择 (1-5): ").strip()
        stage_map = {"1": "elementary", "2": "middle", "3": "high", "4": "college", "5": "graduate"}
        identity_detail.education_stage = stage_map.get(stage_choice)
        identity_detail.major = input("专业方向 (可选，回车跳过): ").strip() or None

    elif identity_type == "worker":
        identity_detail.industry = input("行业: ").strip() or None
        identity_detail.job_title = input("职位 (可选): ").strip() or None

    elif identity_type == "teacher":
        identity_detail.subject = input("任教学科: ").strip() or None
        identity_detail.teaching_stage = input("教学学段: ").strip() or None

    elif identity_type == "freelancer":
        identity_detail.field = input("从事领域: ").strip() or None

    else:
        identity_detail.description = input("身份描述: ").strip() or None

    # 使用场景
    print("\n使用场景 (多选，用逗号分隔):")
    print("  学习辅助、工作助手、生活顾问、情感陪伴、创意灵感")
    use_cases_input = input("请输入: ").strip()
    use_cases = [u.strip() for u in use_cases_input.split("，") if u.strip()]
    if not use_cases:
        use_cases = [u.strip() for u in use_cases_input.split(",") if u.strip()]

    # 兴趣标签
    print("\n兴趣标签 (用逗号分隔):")
    print("  如: 文学, 电影, 心理学, 编程, 游戏")
    interests_input = input("请输入: ").strip()
    interests = [i.strip() for i in interests_input.split("，") if i.strip()]
    if not interests:
        interests = [i.strip() for i in interests_input.split(",") if i.strip()]

    # AI 助手定制
    print("\n" + "-" * 30)
    print("AI 助手定制")
    print("-" * 30)

    ai_name = input("给 AI 起个名字: ").strip() or "小助手"

    print("\nAI 身份角色:")
    print("  1. 助手 (assistant) - 高效可靠的执行者")
    print("  2. 导师 (mentor) - 循循善诱的引导者")
    print("  3. 朋友 (friend) - 平等亲近的伙伴")
    print("  4. 顾问 (advisor) - 专业理性的分析师")
    print("  5. 伙伴 (partner) - 共同成长的合作者")
    role_choice = input("请选择 (1-5): ").strip()
    role_map = {"1": "assistant", "2": "mentor", "3": "friend", "4": "advisor", "5": "partner"}
    ai_role = role_map.get(role_choice, "assistant")

    print("\n性格特点 (多选，用逗号分隔):")
    print("  严谨专业、幽默风趣、温柔耐心、简洁高效、热情活泼")
    personality_input = input("请输入: ").strip()
    personality = [p.strip() for p in personality_input.split("，") if p.strip()]
    if not personality:
        personality = [p.strip() for p in personality_input.split(",") if p.strip()]

    print("\n沟通风格:")
    print("  1. 正式  2. 随意  3. 学术  4. 日常")
    style_choice = input("请选择 (1-4): ").strip()
    style_map = {"1": "formal", "2": "casual", "3": "academic", "4": "daily"}
    communication_style = style_map.get(style_choice, "daily")

    # 构建请求
    request = OnboardingRequest(
        username=username,
        identity_type=identity_type,
        identity_detail=identity_detail,
        use_cases=use_cases,
        interests=interests,
        ai_customization=AICustomization(
            ai_name=ai_name,
            ai_role=ai_role,
            personality=personality,
            communication_style=communication_style,
        ),
    )

    # 调用 Service
    print("\n" + "=" * 50)
    print("正在初始化...")
    print("=" * 50)

    llm = LLMFactory.get_provider()
    async with AsyncSessionLocal() as session:
        service = ProfileService(session, llm)
        result = await service.onboarding(request)

        # 输出结果
        print("\n" + "-" * 30)
        print("初始化结果")
        print("-" * 30)
        print(f"状态: {'成功' if result.success else '失败'}")
        print(f"用户 ID: {result.user_id}")
        print(f"\nuser_prompt_template:")
        print(f"  {result.user_prompt_template}")
        print(f"\nagent_persona_template:")
        print(f"  {result.agent_persona_template}")

        if result.initial_categories:
            print(f"\n固定分类:")
            for cat in result.initial_categories.get("fixed", []):
                print(f"  - {cat.name}: {cat.description}")
            print(f"\n个性化分类:")
            for cat in result.initial_categories.get("personalized", []):
                print(f"  - {cat.name}: {cat.description}")

        print(f"\n消息: {result.message}")


# ========== Chat 测试 ==========

async def batch_save(session, llm, session_state) -> dict:
    """批量存储累积的对话"""
    pending_chats = session_manager.clear_pending_chats(session_state.session_id)

    if not pending_chats:
        return {}

    # 合并对话
    combined_input = "\n\n".join([
        f"用户: {chat.user_input}\n助手: {chat.assistant_response}"
        for chat in pending_chats
    ])

    combined_summary = f"包含 {len(pending_chats)} 轮对话"

    # 存储到数据库
    writer = MemoryWriter(session, llm)
    result = await writer.save_chat(
        user_id=session_state.user_id,
        user_input=combined_input,
        assistant_response=combined_summary,
        modality="text",
    )

    return result


async def chat_loop():
    """主聊天循环"""
    # 初始化 LLM
    llm = LLMFactory.get_provider()

    # 生成会话 ID
    session_id = f"cli-test-{uuid.uuid4().hex[:8]}"

    print("=" * 50)
    print("🖥️  Mymem 命令行聊天")
    print("=" * 50)
    print(f"会话 ID: {session_id}")
    print("输入 'quit' 退出，输入 'status' 查看状态")
    print("=" * 50)
    print()

    chat_count = 0

    while True:
        try:
            user_input = input("你: ").strip()

            if not user_input:
                continue

            if user_input.lower() == "quit":
                print("\n再见！")
                break

            if user_input.lower() == "status":
                session_state = session_manager.get_session(session_id)
                print(f"\n📊 当前状态:")
                print(f"   会话 ID: {session_id}")
                print(f"   已对话轮数: {chat_count}")
                print(f"   用户: {session_state.user_name if session_state else '未识别'}")
                print()
                continue

            # 核心逻辑：直接调用 Service 层
            async with AsyncSessionLocal() as session:
                # Step 1: 获取或创建会话状态
                session_state = session_manager.get_or_create(session_id)

                # Step 2: 用户识别
                if not session_state.is_identified:
                    identifier = UserIdentifier(llm, session)
                    id_result = await identifier.identify_or_ask(session_state, user_input)

                    if id_result["identified"]:
                        session_manager.set_user(
                            session_id,
                            id_result["user_id"],
                            id_result["user_name"],
                        )

                    if id_result["response"]:
                        print("AI:", id_result["response"])
                        if id_result["identified"]:
                            print(f"   [用户: {id_result['user_name']}]")
                        print()
                        continue

                # Step 3: LLM 生成回复
                user = await session.get(User, session_state.user_id)

                system_prompt = "你是一个友好的智能助手。"
                if user and user.agent_persona_template:
                    system_prompt = user.agent_persona_template.decode('utf-8', errors='ignore')
                elif user and user.user_prompt_template:
                    system_prompt = user.user_prompt_template.decode('utf-8', errors='ignore')

                # 构建短期记忆上下文
                history_context = ""
                if session_state.pending_chats:
                    history_context = "\n".join([
                        f"用户: {chat.user_input}\n助手: {chat.assistant_response}"
                        for chat in session_state.pending_chats[-5:]
                    ])

                try:
                    answer = await llm.generate_chat_response(
                        system_prompt=system_prompt,
                        context=history_context,
                        user_query=user_input,
                    )
                except Exception as e:
                    answer = f"抱歉，我遇到了一些问题：{str(e)}"

                chat_count += 1

                # Step 4: 处理存储逻辑
                session_manager.add_pending_chat(session_id, user_input, answer)

                # 输出回复
                print("AI:", answer)

                if session_state.is_identified:
                    print(f"   [用户: {session_state.user_name}]")

                # 检查是否达到批量存储阈值
                if session_state.chat_count >= CHAT_BATCH_SIZE:
                    result = await batch_save(session, llm, session_state)
                    print(f"   [已存储到数据库, resource_id: {result.get('resource_id', '')[:8]}...]")
                    print(f"   [分类: {result.get('category_name')}, 重要性: {result.get('importance_score')}]")
                else:
                    remaining = CHAT_BATCH_SIZE - (chat_count % CHAT_BATCH_SIZE)
                    if remaining == CHAT_BATCH_SIZE:
                        remaining = 0
                    if remaining > 0:
                        print(f"   [缓存中，还需 {remaining} 轮存储]")

                print()

        except KeyboardInterrupt:
            print("\n\n已中断，再见！")
            break
        except Exception as e:
            print(f"错误: {e}")
            import traceback
            traceback.print_exc()


# ========== 主入口 ==========

async def main():
    """主菜单"""
    while True:
        print("\n" + "=" * 50)
        print("🖥️  Mymem 测试工具")
        print("=" * 50)
        print("  1. 用户初始化测试 (onboarding)")
        print("  2. 对话测试 (chat)")
        print("  3. 退出")
        print("=" * 50)

        choice = input("请选择 (1-3): ").strip()

        if choice == "1":
            await test_onboarding()
        elif choice == "2":
            await chat_loop()
        elif choice == "3":
            print("\n再见！")
            break
        else:
            print("无效选择，请重新输入")


if __name__ == "__main__":
    asyncio.run(main())
