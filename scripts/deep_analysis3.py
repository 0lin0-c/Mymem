"""Cat4/Cat5详细 + category_only的15个问题是什么"""
import json
from pathlib import Path
from collections import defaultdict

result_file = sorted(Path("test_results/converted_data/legacy").glob("mymem_test_results_20260417_07481*.json"))[-1]
d = json.load(open(result_file, "r", encoding="utf-8"))
sample = d["samples"][0]
results = sample["qa_results"]
cat_names = {4: "Cat4-中等", 5: "Cat5-描述"}

for cat_id in [4, 5]:
    items = [q for q in results if q.get("category") == cat_id]
    correct = [q for q in items if q.get("is_correct")]
    wrong = [q for q in items if not q.get("is_correct")]
    
    print(f"\n{'='*70}")
    print(f"  {cat_names[cat_id]}: {len(correct)}/{len(items)} ({len(correct)/len(items)*100:.1f}%)")
    print(f"{'='*70}")
    
    # 错误原因
    if wrong:
        reason_counts = defaultdict(int)
        for q in wrong:
            llm_ans = q.get("generated_answer", "")
            layer = q.get("retrieval_layer", {})
            res_count = layer.get("resource_results_count", 0) if isinstance(layer, dict) else 0
            resolved = layer.get("resolved_layer", "none") if isinstance(layer, dict) else "none"
            contexts = q.get("retrieved_contexts", [])
            has_2026 = any("2026" in c for c in contexts)
            
            if "don't have enough" in llm_ans or "没有足够" in llm_ans or "I cannot" in llm_ans:
                if res_count == 0 and resolved == "category_only":
                    reason = "A-category误判充足，未下钻"
                elif res_count > 0:
                    reason = "B-resource也检索了但关键记忆未命中"
                else:
                    reason = "C-其他信息不足"
            elif has_2026:
                reason = "D-2026时间戳干扰"
            else:
                reason = "E-LLM生成错误"
            reason_counts[reason] += 1
        
        print(f"  错误原因:")
        for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
            print(f"    {reason}: {count}个")
    
    # 正确案例
    if correct:
        print(f"\n  --- 全部正确案例 ---")
        for i, q in enumerate(correct, 1):
            layer = q.get("retrieval_layer", {})
            resolved = layer.get("resolved_layer", "?") if isinstance(layer, dict) else "?"
            is_suff = layer.get("is_sufficient_at_category", "?") if isinstance(layer, dict) else "?"
            cat_cnt = layer.get("category_results_count", 0) if isinstance(layer, dict) else 0
            res_cnt = layer.get("resource_results_count", 0) if isinstance(layer, dict) else 0
            contexts = q.get("retrieved_contexts", [])
            scores = q.get("retrieved_scores", [])
            
            # 看答案在category层还是resource层
            std_kw = [w for w in q["standard_answer"].split() if len(w) > 3]
            cat_ctx = contexts[:cat_cnt] if cat_cnt > 0 else []
            res_ctx = contexts[cat_cnt:cat_cnt+res_cnt] if res_cnt > 0 else []
            
            cat_has = any(any(kw.lower() in c.lower() for kw in std_kw) for c in cat_ctx) if std_kw else False
            res_has = any(any(kw.lower() in c.lower() for kw in std_kw) for c in res_ctx) if std_kw else False
            
            source = "both" if cat_has and res_has else ("category" if cat_has else ("resource" if res_has else "unclear"))
            
            print(f"  [{i}] {q['question'][:55]}")
            print(f"      A: {q['standard_answer'][:60]}")
            print(f"      layer={resolved} | cat={cat_cnt} res={res_cnt} | 答案来自: {source}")

# ============================================================
# category_only的15个问题全部列出
# ============================================================
print(f"\n\n{'='*70}")
print(f"  category_only 层级的15个问题（全部错误）")
print(f"{'='*70}")

cat_only = [q for q in results if 
    (q.get("retrieval_layer", {}).get("resolved_layer") if isinstance(q.get("retrieval_layer"), dict) else None) == "category_only"]

for i, q in enumerate(cat_only, 1):
    layer = q.get("retrieval_layer", {})
    is_suff = layer.get("is_sufficient_at_category", "?")
    cat_cnt = layer.get("category_results_count", 0)
    contexts = q.get("retrieved_contexts", [])
    has_2026 = any("2026" in c for c in contexts)
    cat = q.get("category", "?")
    
    print(f"  [{i}] Cat{cat} | Q: {q['question'][:60]}")
    print(f"      A: {q['standard_answer'][:50]} | suff={is_suff} | 2026={has_2026}")
