"""
测试 asyncio.create_task 的执行时机
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.llm.factory import LLMFactory


async def test_task_timing():
    """测试后台任务的执行时机"""
    print("=== 测试 asyncio.create_task 执行时机 ===\n")

    LLMFactory.reset()
    llm = LLMFactory.get_provider()

    async def slow_background_task(name: str):
        print(f"  [{time.perf_counter():.2f}] 后台任务 {name} 开始")
        await asyncio.sleep(0.1)  # 模拟一些工作
        response = await llm.generate_chat_response(
            system_prompt="你是一个助手",
            context="",
            user_query="说一个字",
        )
        print(f"  [{time.perf_counter():.2f}] 后台任务 {name} 完成: {response[:20]}...")
        return response

    print(f"[{time.perf_counter():.2f}] 开始主流程")

    # 创建后台任务
    task = asyncio.create_task(slow_background_task("分类生成"))

    print(f"[{time.perf_counter():.2f}] 后台任务已创建，继续主流程")

    # 模拟其他工作
    await asyncio.sleep(0.05)
    print(f"[{time.perf_counter():.2f}] 主流程其他工作完成")

    # 返回响应
    print(f"[{time.perf_counter():.2f}] 准备返回响应")

    # 等待后台任务完成（可选）
    # await task

    print(f"[{time.perf_counter():.2f}] 主流程结束")

    # 如果不等后台任务，脚本会直接退出
    # 这里等待是为了观察
    await task


if __name__ == "__main__":
    asyncio.run(test_task_timing())
