"""补充分析：Cat2-5详细 + 层级贡献度"""
import json
from pathlib import Path
from collections import defaultdict

result_file = sorted(Path("test_results/converted_data/legacy").glob("mymem_test_results_20260417_07481*.json"))[-1]
d = json.load(open(result_file, "r", encoding="utf-8"))
sample = d["samples"][0]
results = sample["qa_results"]
cat_names = {1: "Cat1-时间", 2: "Cat2-事实", 3: "Cat3-数值", 4: "Cat4-中等", 5: "Cat5-描述"}

# ============================================================
# Cat2-5 错误详情
# ============================================================
for cat_id in [2, 3, 4, 5]:
    items = [q for q in results if q.get("category") == cat_id]
    correct = [q for q in items if q.get("is_correct")]
    wrong = [q for q in items if not q.get("is_correct")]
    
    print(f"\n{'='*70}")
    print(f"  {cat_names[cat_id]}: {len(correct)}/{len(items)} 正确 ({len(correct)/len(items)*100:.1f}%)")
    print(f"{'='*70}")
    
    if wrong:
        print(f"\n  --- 错误原因 ---")
        reason_counts = defaultdict(int)
        for q in wrong:
            llm_ans = q.get("generated_answer", "")
            layer = q.get("retrieval_layer", {})
            resolved = layer.get("resolved_layer", "none") if isinstance(layer, dict) else "none"
            is_sufficient = layer.get("is_sufficient_at_category", None) if isinstance(layer, dict) else None
            cat_count = layer.get("category_results_count", 0) if isinstance(layer, dict) else 0
            res_count = layer.get("resource_results_count", 0) if isinstance(layer, dict) else 0
            contexts = q.get("retrieved_contexts", [])
            has_2026 = any("2026" in c for c in contexts)
            
            if "don't have enough" in llm_ans or "没有足够" in llm_ans or "I cannot" in llm_ans:
                if res_count == 0 and resolved == "category_only":
                    reason = "A-category层误判充足，未下钻resource"
                elif res_count > 0:
                    reason = "B-resource层也检索了，但关键记忆未命中"
                else:
                    reason = "C-其他信息不足"
            elif has_2026:
                reason = "D-2026时间戳干扰"
            else:
                reason = "E-检索到信息但LLM生成错误"
            reason_counts[reason] += 1
        
        for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
            print(f"    {reason}: {count}个")
        
        print(f"\n  --- 错误案例(前5) ---")
        for i, q in enumerate(wrong[:5], 1):
            layer = q.get("retrieval_layer", {})
            resolved = layer.get("resolved_layer", "?") if isinstance(layer, dict) else "?"
            is_suff = layer.get("is_sufficient_at_category", "?") if isinstance(layer, dict) else "?"
            cat_cnt = layer.get("category_results_count", 0) if isinstance(layer, dict) else 0
            res_cnt = layer.get("resource_results_count", 0) if isinstance(layer, dict) else 0
            contexts = q.get("retrieved_contexts", [])
            scores = q.get("retrieved_scores", [])
            has_2026 = any("2026" in c for c in contexts)
            
            print(f"  [{i}] Q: {q['question']}")
            print(f"      A: {q['standard_answer']}")
            print(f"      LLM: {q['generated_answer'][:100]}")
            print(f"      layer={resolved} | suff={is_suff} | cat={cat_cnt} | res={res_cnt} | 2026={has_2026}")
            for j, (ctx, sc) in enumerate(zip(contexts[:3], scores[:3] if scores else [0]*3)):
                print(f"        [{j+1}] score={sc:.4f} | {ctx[:90]}")

    if correct:
        print(f"\n  --- 正确案例(前3) ---")
        for i, q in enumerate(correct[:3], 1):
            layer = q.get("retrieval_layer", {})
            resolved = layer.get("resolved_layer", "?") if isinstance(layer, dict) else "?"
            is_suff = layer.get("is_sufficient_at_category", "?") if isinstance(layer, dict) else "?"
            cat_cnt = layer.get("category_results_count", 0) if isinstance(layer, dict) else 0
            res_cnt = layer.get("resource_results_count", 0) if isinstance(layer, dict) else 0
            print(f"  [{i}] Q: {q['question']}")
            print(f"      A: {q['standard_answer']}")
            print(f"      layer={resolved} | suff={is_suff} | cat={cat_cnt} | res={res_cnt}")

# ============================================================
# 层级贡献度：对于所有正确案例，分析哪层真正提供了答案
# ============================================================
print(f"\n\n{'='*70}")
print(f"  层级贡献度分析（所有30个正确案例）")
print(f"{'='*70}")

correct_items = [q for q in results if q.get("is_correct")]

# 分类：category_only正确 vs category+resource正确
cat_only_correct = []
cat_res_correct = []
res_only_correct = []

for q in correct_items:
    layer = q.get("retrieval_layer", {})
    resolved = layer.get("resolved_layer", "none") if isinstance(layer, dict) else "none"
    if resolved == "category_only":
        cat_only_correct.append(q)
    elif resolved == "category+resource":
        cat_res_correct.append(q)
    elif resolved == "resource_only":
        res_only_correct.append(q)

print(f"\n  category_only 正确: {len(cat_only_correct)}")
print(f"  category+resource 正确: {len(cat_res_correct)}")
print(f"  resource_only 正确: {len(res_only_correct)}")

# 对于category+resource的正确案例，看category层得分 vs resource层得分
print(f"\n  === category+resource 正确案例({len(cat_res_correct)}个) 的层级得分对比 ===")

cat_better = 0  # category层最高分 > resource层最高分
res_better = 0  # resource层最高分 > category层最高分
equal = 0

for q in cat_res_correct:
    layer = q.get("retrieval_layer", {})
    cat_cnt = layer.get("category_results_count", 0)
    res_cnt = layer.get("resource_results_count", 0)
    is_suff = layer.get("is_sufficient_at_category", None)
    scores = q.get("retrieved_scores", [])
    
    cat_scores_list = scores[:cat_cnt] if cat_cnt > 0 else []
    res_scores_list = scores[cat_cnt:cat_cnt+res_cnt] if res_cnt > 0 else []
    
    cat_max = max(cat_scores_list) if cat_scores_list else 0
    res_max = max(res_scores_list) if res_scores_list else 0
    
    if is_suff is True:
        # category层判断为充足但仍检索了resource
        suff_status = "category充足但仍下钻"
    else:
        suff_status = "category不足，下钻resource"
    
    print(f"  Q: {q['question'][:50]} | cat_max={cat_max:.3f} | res_max={res_max:.3f} | {suff_status}")
    
    if cat_max > res_max:
        cat_better += 1
    elif res_max > cat_max:
        res_better += 1
    else:
        equal += 1

print(f"\n  category层得分更高: {cat_better}")
print(f"  resource层得分更高: {res_better}")
print(f"  得分相同: {equal}")

# 关键统计：sufficient判断
suff_true = [q for q in cat_res_correct if q.get("retrieval_layer", {}).get("is_sufficient_at_category") == True]
suff_false = [q for q in cat_res_correct if q.get("retrieval_layer", {}).get("is_sufficient_at_category") == False]
print(f"\n  category充足判断=True但还检索了resource: {len(suff_true)}")
print(f"  category充足判断=False，下钻resource: {len(suff_false)}")

# ============================================================
# 综合结论：哪层对正确率贡献最大
# ============================================================
print(f"\n\n{'='*70}")
print(f"  综合结论")
print(f"{'='*70}")

total = len(results)
correct_total = len(correct_items)

# 如果只有category层（假设resource层不存在），会怎样？
cat_only_all = [q for q in results if q.get("retrieval_layer", {}).get("resolved_layer") in ["category_only", "category+resource"]]
cat_sufficient = [q for q in results if q.get("retrieval_layer", {}).get("is_sufficient_at_category") == True]
cat_suff_correct = [q for q in cat_sufficient if q.get("is_correct")]

print(f"\n  总问题数: {total}")
print(f"  正确数: {correct_total} ({correct_total/total*100:.1f}%)")
print(f"  category层判断为充足的问题: {len(cat_sufficient)}")
print(f"    其中正确: {len(cat_suff_correct)} ({len(cat_suff_correct)/len(cat_sufficient)*100:.1f}%)" if cat_sufficient else "")
print(f"  category层判断不足（需要resource）: {total - len(cat_sufficient)}")

# category_only正确数 = 0，所有30个正确都来自两层检索
print(f"\n  category_only 正确数: {len(cat_only_correct)}")
print(f"  category+resource 正确数: {len(cat_res_correct)}")
print(f"  resource_only 正确数: {len(res_only_correct)}")
print(f"\n  结论: 所有{correct_total}个正确回答都来自resource层的检索")
print(f"  category层的价值: 分类导航+充足性判断，但不直接提供正确答案")
print(f"  resource层的价值: 提供具体记忆细节，是正确回答的核心来源")
