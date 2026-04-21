"""测试当前 API + 模型是否支持 Function Calling (tool_calls)"""
import asyncio
import json
import os
import sys

sys.path.insert(0, str(os.path.dirname(__file__)))

from core.config import settings


async def test_openai():
    """测试 OpenAI 兼容接口"""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )

    tools = [{
        "type": "function",
        "function": {
            "name": "extract_memory",
            "description": "从对话中提取记忆信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "对话摘要"},
                    "importance_score": {"type": "integer", "description": "重要程度1-10"},
                },
                "required": ["summary", "importance_score"],
            },
        },
    }]

    success = 0
    total = 5

    for i in range(total):
        try:
            response = await client.chat.completions.create(
                model=settings.chat_model,
                messages=[
                    {"role": "system", "content": "你是一个记忆提取助手。"},
                    {"role": "user", "content": "我今天去了动物园，看到了大熊猫，特别开心！"},
                ],
                tools=tools,
                tool_choice={"type": "function", "function": {"name": "extract_memory"}},
            )
            msg = response.choices[0].message
            if msg.tool_calls:
                args = json.loads(msg.tool_calls[0].function.arguments)
                print(f"[{i+1}/{total}] OK: {json.dumps(args, ensure_ascii=False)}")
                success += 1
            else:
                print(f"[{i+1}/{total}] FAIL - plain text")
        except Exception as e:
            print(f"[{i+1}/{total}] FAIL - {type(e).__name__}: {e}")

    return success, total


async def test_anthropic():
    """测试 Anthropic 兼容接口"""
    import anthropic

    client_kwargs = {"api_key": settings.anthropic_api_key}
    if settings.anthropic_base_url:
        client_kwargs["base_url"] = settings.anthropic_base_url

    client = anthropic.AsyncAnthropic(**client_kwargs)

    tools = [{
        "name": "extract_memory",
        "description": "从对话中提取记忆信息",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "对话摘要"},
                "importance_score": {"type": "integer", "description": "重要程度1-10"},
            },
            "required": ["summary", "importance_score"],
        },
    }]

    success = 0
    total = 5

    for i in range(total):
        try:
            message = await client.messages.create(
                model=settings.chat_model,
                max_tokens=2000,
                system="你是一个记忆提取助手。",
                messages=[{"role": "user", "content": "我今天去了动物园，看到了大熊猫，特别开心！"}],
                tools=tools,
                tool_choice={"type": "tool", "name": "extract_memory"},
            )
            for block in message.content:
                if block.type == "tool_use":
                    print(f"[{i+1}/{total}] OK: {json.dumps(block.input, ensure_ascii=False)}")
                    success += 1
                    break
            else:
                print(f"[{i+1}/{total}] FAIL - no tool_use block")
        except Exception as e:
            print(f"[{i+1}/{total}] FAIL - {type(e).__name__}: {e}")

    return success, total


async def main():
    provider = settings.llm_provider.lower()
    print(f"LLM_PROVIDER: {provider}")
    print(f"CHAT_MODEL: {settings.chat_model}")
    print("-" * 50)

    if provider == "anthropic":
        print(f"Base URL: {settings.anthropic_base_url}")
        print(f"API Key: {(settings.anthropic_api_key or '')[:10]}...")
        print("-" * 50)
        success, total = await test_anthropic()
    else:
        print(f"Base URL: {settings.openai_base_url}")
        print(f"API Key: {(settings.openai_api_key or '')[:10]}...")
        print("-" * 50)
        success, total = await test_openai()

    print("-" * 50)
    print(f"Result: {success}/{total} ({success/total*100:.0f}%)")


if __name__ == "__main__":
    asyncio.run(main())
