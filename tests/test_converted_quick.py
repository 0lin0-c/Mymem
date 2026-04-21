# Quick validation script: test converted_data parsing
"""
Quick validation of dataset parsing without calling real LLM.
Used for debugging and verifying data format.

Usage:
    python -m tests.test_converted_quick
"""
import asyncio
from pathlib import Path

# Dataset path
DATA_DIR = Path(__file__).parent.parent.parent / "memU" / "tier_test_results" / "converted_data_zh"


def test_parse_converted():
    """Test parsing converted file"""
    from tests.evals.converted_data.loader import parse_converted_file, parse_conversation_turns

    # Find first file
    files = sorted(DATA_DIR.glob("sample_0_*_converted.json"))
    if not files:
        print("[FAIL] No data file found")
        return False

    converted = parse_converted_file(files[0])
    print(f"[OK] Parsed: {files[0].name}")
    print(f"  - User: {converted.user_id}")
    print(f"  - Character: {converted.user_character}")
    print(f"  - Sessions: {converted.total_sessions}")

    # Parse first session's conversation turns
    if converted.sessions:
        turns = parse_conversation_turns(converted.sessions[0].content)
        print(f"  - First session turns: {len(turns)}")
        if turns:
            print(f"    Example: user: {turns[0][1][:50]}...")

    return True


def test_parse_qa():
    """Test parsing QA file"""
    from tests.evals.converted_data.loader import parse_qa_file

    qa_file = DATA_DIR / "sample_0_qa.json"
    if not qa_file.exists():
        print("[FAIL] No QA file found")
        return False

    qa = parse_qa_file(qa_file)
    print(f"[OK] Parsed: {qa_file.name}")
    print(f"  - Characters: {qa.characters}")
    print(f"  - Questions: {qa.total_questions}")

    if qa.questions:
        q = qa.questions[0]
        print(f"  - Example question: {q.question}")
        print(f"    Expected answer: {q.answer}")
        print(f"    Target character: {q.target_character}")

    return True


def test_file_structure():
    """Test file structure"""
    print("\n[FILES] Dataset Structure:")
    print(f"   Path: {DATA_DIR}")

    if not DATA_DIR.exists():
        print("   [FAIL] Directory not found")
        return False

    # Count files
    converted_files = list(DATA_DIR.glob("*_converted.json"))
    qa_files = list(DATA_DIR.glob("*_qa.json"))

    print(f"   - Converted files: {len(converted_files)}")
    print(f"   - QA files: {len(qa_files)}")

    # Group by sample
    samples = {}
    for f in converted_files:
        import re
        match = re.match(r"sample_(\d+)_", f.name)
        if match:
            idx = int(match.group(1))
            if idx not in samples:
                samples[idx] = {"converted": [], "qa": None}
            samples[idx]["converted"].append(f.name)

    for f in qa_files:
        import re
        match = re.match(r"sample_(\d+)_", f.name)
        if match:
            idx = int(match.group(1))
            if idx in samples:
                samples[idx]["qa"] = f.name

    print(f"\n   Sample details:")
    for idx in sorted(samples.keys()):
        s = samples[idx]
        print(f"   - Sample {idx}: {len(s['converted'])} chars, QA: {s['qa']}")

    return True


def main():
    print("=" * 50)
    print("[TEST] Converted Data Quick Validation")
    print("=" * 50)

    # Test file structure
    test_file_structure()

    print("\n" + "-" * 50)
    print("[PARSE] Parsing Test")
    print("-" * 50)

    # Test parsing
    test_parse_converted()
    print()
    test_parse_qa()

    print("\n" + "=" * 50)
    print("[OK] Validation Complete")
    print("=" * 50)


if __name__ == "__main__":
    main()
