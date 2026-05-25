"""检查Cat5空答案的评估情况"""
import json
from pathlib import Path

result_file = sorted(Path("test_results/converted_data/legacy").glob("mymem_test_results_20260417_07481*.json"))[-1]
d = json.load(open(result_file, "r", encoding="utf-8"))
sample = d["samples"][0]
results = sample["qa_results"]

cat5 = [q for q in results if q.get("category") == 5]
cat5_correct = [q for q in cat5 if q.get("is_correct")]
cat5_wrong = [q for q in cat5 if not q.get("is_correct")]

print(f"Cat5 total: {len(cat5)}")
print(f"Cat5 correct: {len(cat5_correct)}")
print(f"Cat5 wrong: {len(cat5_wrong)}")

print(f"\n=== Cat5 correct cases ({len(cat5_correct)}) ===")
for i, q in enumerate(cat5_correct[:5], 1):
    print(f"\n  [{i}] Q: {q['question'][:60]}")
    print(f"      标准答案: \"{q['standard_answer']}\"")
    print(f"      LLM回答: {q['generated_answer'][:100]}")
    print(f"      评估说明: {q.get('correctness_explanation', '')[:100]}")

print(f"\n=== Cat5 wrong case ({len(cat5_wrong)}) ===")
if cat5_wrong:
    q = cat5_wrong[0]
    print(f"  Q: {q['question'][:60]}")
    print(f"  标准答案: \"{q['standard_answer']}\"")
    print(f"  LLM回答: {q['generated_answer'][:100]}")
    print(f"  评估说明: {q.get('correctness_explanation', '')[:100]}")
