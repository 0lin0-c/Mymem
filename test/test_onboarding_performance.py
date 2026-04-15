"""
测试用户初始化性能

运行方式：
cd D:\Research\Agent Memory\Project\Mymem
python test/test_onboarding_performance.py
"""
import asyncio
import sys
import time
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import AsyncSessionLocal
from services.profile_service import ProfileService
from services.llm.factory import LLMFactory
from schemas.onboarding_schema import OnboardingRequest, AICustomization


async def test_llm_initialization():
    """测试 LLM 客户端初始化耗时"""
    print("=== LLM 客户端初始化测试 ===")

    # 重置以确保从头开始
    LLMFactory.reset()

    start = time.perf_counter()
    llm = LLMFactory.get_provider()
    elapsed = time.perf_counter() - start
    print(f"LLM 客户端初始化: {elapsed:.3f} 秒")

    # 测试首次 LLM 调用
    start = time.perf_counter()
    try:
        response = await llm.generate_chat_response(
            system_prompt="你是一个助手",
            context="",
            user_query="说一个字",
        )
        elapsed = time.perf_counter() - start
        print(f"首次 LLM 调用: {elapsed:.3f} 秒")
    except Exception as e:
        print(f"LLM 调用失败: {e}")


async def test_onboarding_performance():
    """测试初始化性能"""

    print("\n=== 用户初始化性能测试 ===")

    # 先预热 LLM（模拟服务启动后的状态）
    print("预热 LLM 客户端...")
    llm = LLMFactory.get_provider()

    # 构造测试请求
    request = OnboardingRequest(
        username="test_user_perf",
        password="test123",
        identity_type="student",
        use_cases=["学习辅助", "工作助手"],
        interests=["编程", "AI", "音乐"],
        ai_customization=AICustomization(
            ai_name="小智",
            ai_role="assistant",
            personality=["严谨专业", "幽默风趣"],
            communication_style="daily",
        ),
    )

    # 测试 3 次取平均值
    times = []

    for i in range(3):
        # 每次用不同的用户名
        test_request = request.model_copy(update={
            "username": f"test_user_perf_{i}_{int(time.time())}"
        })

        async with AsyncSessionLocal() as session:
            service = ProfileService(session, llm)

            start = time.perf_counter()
            result = await service.onboarding(test_request)
            elapsed = time.perf_counter() - start

            times.append(elapsed)
            print(f"第 {i+1} 次: {elapsed:.3f} 秒 - {'成功' if result.success else '失败'}")

            # 等待后台任务完成
            await asyncio.sleep(0.5)

    avg = sum(times) / len(times)
    print(f"\n平均耗时: {avg:.3f} 秒")
    print(f"最快: {min(times):.3f} 秒")
    print(f"最慢: {max(times):.3f} 秒")


async def test_http_request():
    """模拟真实 HTTP 请求测试"""
    import httpx

    print("\n=== HTTP 请求测试（需要服务运行）===")
    print("请确保服务已启动: python main.py")

    request_data = {
        "username": f"http_test_{int(time.time())}",
        "password": "test123",
        "identity_type": "student",
        "use_cases": ["学习辅助"],
        "interests": ["编程"],
        "ai_customization": {
            "ai_name": "小智",
            "ai_role": "assistant",
            "personality": ["严谨专业"],
            "communication_style": "daily",
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            start = time.perf_counter()
            response = await client.post(
                "http://localhost:8002/v1/user/onboarding",
                json=request_data,
            )
            elapsed = time.perf_counter() - start

            print(f"HTTP 请求耗时: {elapsed:.3f} 秒")
            print(f"状态码: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                print(f"成功: {result.get('success')}")
                print(f"user_id: {result.get('user_id')}")
            else:
                print(f"错误: {response.text}")

    except httpx.ConnectError:
        print("无法连接服务，请确保服务已启动在端口 8002")
    except Exception as e:
        print(f"请求失败: {e}")


async def test_cold_start():
    """测试冷启动（模拟服务首次启动）"""
    print("\n=== 冷启动测试（模拟服务首次请求）===")

    # 重置所有状态
    LLMFactory.reset()

    # 构造测试请求
    request = OnboardingRequest(
        username=f"cold_start_{int(time.time())}",
        password="test123",
        identity_type="student",
        use_cases=["学习辅助"],
        interests=["编程"],
        ai_customization=AICustomization(
            ai_name="小智",
            ai_role="assistant",
            personality=["严谨专业"],
            communication_style="daily",
        ),
    )

    async with AsyncSessionLocal() as session:
        # 这里 LLM 是在 onboarding 中首次初始化的
        service = ProfileService(session, None)  # type: ignore

        start = time.perf_counter()
        llm = LLMFactory.get_provider()
        service.llm = llm
        init_time = time.perf_counter() - start
        print(f"LLM 初始化: {init_time:.3f} 秒")

        start = time.perf_counter()
        result = await service.onboarding(request)
        elapsed = time.perf_counter() - start

        print(f"onboarding 总耗时: {elapsed:.3f} 秒 - {'成功' if result.success else '失败'}")

        # 等待后台任务
        await asyncio.sleep(1)


if __name__ == "__main__":
    print("=" * 50)
    print("用户初始化性能诊断测试")
    print("=" * 50)

    # asyncio.run(test_llm_initialization())
    # asyncio.run(test_onboarding_performance())
    # asyncio.run(test_cold_start())
    asyncio.run(test_http_request())
