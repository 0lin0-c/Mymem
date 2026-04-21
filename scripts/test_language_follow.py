# Test Language Following Feature
"""
Verify that during memory extraction, the LLM outputs in the same language as the user input.
No database connection required, only tests LLM calls.
"""
import asyncio
import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.llm.openai_sdk import OpenAIProvider
from services.llm.tools import build_memory_extraction_prompt
from services.constants import BASE_CATEGORIES


def is_chinese(text: str) -> bool:
    """Check if text is primarily Chinese"""
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    return chinese_chars > len(text) * 0.3


def is_english(text: str) -> bool:
    """Check if text is primarily English"""
    alpha_chars = sum(1 for c in text if c.isalpha() and ord(c) < 128)
    return alpha_chars > len(text) * 0.3


async def test_chinese_input(llm: OpenAIProvider):
    """Test Chinese input"""
    print("\n" + "="*60)
    print("Test 1: Chinese Input")
    print("="*60)

    user_input = "我叫张三，今年28岁，在北京做产品经理。我喜欢打篮球，周末经常和朋友一起去球场。"
    assistant_response = "你好张三！很高兴认识你。产品经理是个很有挑战的工作，打篮球是很好的放松方式。"

    result = await llm.extract_memory_intent(
        text=user_input,
        categories=[{"name": c["name"], "description": c["description"]} for c in BASE_CATEGORIES],
        assistant_response=assistant_response,
    )

    print(f"User Input: {user_input}")
    print(f"\nExtraction Result:")
    print(f"  summary: {result['summary']}")
    print(f"  importance_score: {result['importance_score']}")
    print(f"  atomic_items ({len(result['atomic_items'])} items):")
    for item in result['atomic_items']:
        print(f"    - [{item['category_name']}] {item['content']}")

    # Verify language
    summary_lang = "Chinese" if is_chinese(result['summary']) else ("English" if is_english(result['summary']) else "Mixed/Other")
    print(f"\nLanguage Detection: summary is {summary_lang}")

    # Check atomic_items language
    for i, item in enumerate(result['atomic_items']):
        item_lang = "Chinese" if is_chinese(item['content']) else ("English" if is_english(item['content']) else "Mixed/Other")
        print(f"  atomic_items[{i}]: {item_lang}")

    # Assertions
    assert is_chinese(result['summary']), f"Expected summary in Chinese, but got: {result['summary']}"
    for item in result['atomic_items']:
        assert is_chinese(item['content']), f"Expected atomic_item in Chinese, but got: {item['content']}"

    print("\n[PASS] Chinese input test passed!")
    return result


async def test_english_input(llm: OpenAIProvider):
    """Test English input"""
    print("\n" + "="*60)
    print("Test 2: English Input")
    print("="*60)

    user_input = "My name is John, I'm 28 years old, and I work as a product manager in Beijing. I enjoy playing basketball and often go to the court with friends on weekends."
    assistant_response = "Hello John! Nice to meet you. Product management is a challenging role. Basketball is a great way to relax!"

    result = await llm.extract_memory_intent(
        text=user_input,
        categories=[{"name": c["name"], "description": c["description"]} for c in BASE_CATEGORIES],
        assistant_response=assistant_response,
    )

    print(f"User Input: {user_input}")
    print(f"\nExtraction Result:")
    print(f"  summary: {result['summary']}")
    print(f"  importance_score: {result['importance_score']}")
    print(f"  atomic_items ({len(result['atomic_items'])} items):")
    for item in result['atomic_items']:
        print(f"    - [{item['category_name']}] {item['content']}")

    # Verify language
    summary_lang = "Chinese" if is_chinese(result['summary']) else ("English" if is_english(result['summary']) else "Mixed/Other")
    print(f"\nLanguage Detection: summary is {summary_lang}")

    # Check atomic_items language
    for i, item in enumerate(result['atomic_items']):
        item_lang = "Chinese" if is_chinese(item['content']) else ("English" if is_english(item['content']) else "Mixed/Other")
        print(f"  atomic_items[{i}]: {item_lang}")

    # Assertions
    assert is_english(result['summary']), f"Expected summary in English, but got: {result['summary']}"
    for item in result['atomic_items']:
        assert is_english(item['content']), f"Expected atomic_item in English, but got: {item['content']}"

    print("\n[PASS] English input test passed!")
    return result


async def test_mixed_input(llm: OpenAIProvider):
    """Test mixed language input"""
    print("\n" + "="*60)
    print("Test 3: Mixed Input (Chinese dominant)")
    print("="*60)

    user_input = "我在 AWS 做架构师，主要用 Python 和 Go 开发。周末喜欢打 League of Legends。"
    assistant_response = "AWS 架构师很厉害！Python 和 Go 都是很实用的语言。LOL 打什么位置？"

    result = await llm.extract_memory_intent(
        text=user_input,
        categories=[{"name": c["name"], "description": c["description"]} for c in BASE_CATEGORIES],
        assistant_response=assistant_response,
    )

    print(f"User Input: {user_input}")
    print(f"\nExtraction Result:")
    print(f"  summary: {result['summary']}")
    print(f"  atomic_items ({len(result['atomic_items'])} items):")
    for item in result['atomic_items']:
        print(f"    - [{item['category_name']}] {item['content']}")

    # Mixed input should use dominant language (Chinese in this case)
    summary_lang = "Chinese" if is_chinese(result['summary']) else ("English" if is_english(result['summary']) else "Mixed/Other")
    print(f"\nLanguage Detection: summary is {summary_lang}")

    print("\n[PASS] Mixed input test completed!")


async def main():
    print("Starting language following tests...")

    # Initialize LLM
    llm = OpenAIProvider()
    print(f"LLM Config: model={llm.chat_model}")

    try:
        # Test Chinese
        await test_chinese_input(llm)

        # Test English
        await test_english_input(llm)

        # Test Mixed
        await test_mixed_input(llm)

        print("\n" + "="*60)
        print("[SUCCESS] All tests passed! Language following feature works correctly.")
        print("="*60)

    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n[ERROR] Test error: {type(e).__name__}: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
