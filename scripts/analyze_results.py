import json
from pathlib import Path

result_file = sorted(Path("test_results").glob("mymem_test_results_20260417_07481*.json"))[-1]
d = json.load(open(result_file, "r", encoding="utf-8"))

# Explore structure
print("=== Top-level keys ===")
print(list(d.keys()))

if "statistics" in d:
    s = d["statistics"]
    print("\n=== Statistics ===")
    for k, v in s.items():
        if isinstance(v, dict):
            print(f"  {k}:")
            for kk, vv in v.items():
                print(f"    {kk}: {vv}")
        else:
            print(f"  {k}: {v}")

if "samples" in d:
    for sample in d["samples"]:
        print(f"\n=== Sample: {sample.get('character', '?')} ===")
        results = sample.get("qa_results", [])
        correct = [q for q in results if q.get("is_correct")]
        wrong = [q for q in results if not q.get("is_correct")]
        print(f"  正确: {len(correct)}/{len(results)} ({len(correct)/len(results)*100:.1f}%)")

        # Layer distribution
        layers = {}
        for q in results:
            rl = q.get("retrieval_layer", {})
            if isinstance(rl, dict):
                layer = rl.get("resolved_layer", "none")
            else:
                layer = str(rl)
            if layer not in layers:
                layers[layer] = {"total": 0, "correct": 0}
            layers[layer]["total"] += 1
            if q.get("is_correct"):
                layers[layer]["correct"] += 1
        print(f"  层级分布:")
        for layer, stats in sorted(layers.items(), key=lambda x: -x[1]["total"]):
            rate = f"{stats['correct']}/{stats['total']}"
            pct = stats['correct']/stats['total']*100 if stats['total'] else 0
            print(f"    {layer}: {rate} ({pct:.1f}%)")

        # Category accuracy
        cats = {}
        for q in results:
            cat = q.get("category", "?")
            if cat not in cats:
                cats[cat] = {"total": 0, "correct": 0}
            cats[cat]["total"] += 1
            if q.get("is_correct"):
                cats[cat]["correct"] += 1
        print(f"  按类型:")
        for cat, stats in sorted(cats.items()):
            pct = stats['correct']/stats['total']*100 if stats['total'] else 0
            print(f"    Cat {cat}: {stats['correct']}/{stats['total']} ({pct:.1f}%)")

        print(f"\n  === 正确案例(前5) ===")
        for i, q in enumerate(correct[:5], 1):
            print(f'  [{i}] Q: {q["question"]}')
            print(f'      A: {q["standard_answer"]}')
            print(f'      LLM: {q["generated_answer"][:80]}')
            rl = q.get("retrieval_layer", {})
            layer = rl.get("resolved_layer", "?") if isinstance(rl, dict) else rl
            print(f'      Layer: {layer}')

        print(f"\n  === 错误案例(前10) ===")
        for i, q in enumerate(wrong[:10], 1):
            print(f'  [{i}] Q: {q["question"]}')
            print(f'      A: {q["standard_answer"]}')
            print(f'      LLM: {q["generated_answer"][:80]}')
            rl = q.get("retrieval_layer", {})
            layer = rl.get("resolved_layer", "?") if isinstance(rl, dict) else rl
            print(f'      Layer: {layer}')
