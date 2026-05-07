"""深度分析测试结果：各类型成败原因 + 层级贡献度"""
import json
from pathlib import Path
from collections import defaultdict

result_file = sorted(Path("test_results/converted_data/legacy").glob("mymem_test_results_20260417_07481*.json"))[-1]
d = json.load(open(result_file, "r", encoding="utf-8"))

sample = d["samples"][0]
results = sample["qa_results"]

# ============================================================
# 1. 逐类型深度分析
# ============================================================
cat_names = {1: "Cat1-时间", 2: "Cat2-事实", 3: "Cat3-数值", 4: "Cat4-中等", 5: "Cat5-描述"}

for cat_id in range(1, 6):
    items = [q for q in results if q.get("category") == cat_id]
    correct = [q for q in items if q.get("is_correct")]
    wrong = [q for q in items if not q.get("is_correct")]
    
    print(f"\n{'='*70}")
    print(f"  {cat_names[cat_id]}: {len(correct)}/{len(items)} 正确 ({len(correct)/len(items)*100:.1f}%)")
    print(f"{'='*70}")
    
    # 分析错误原因
    if wrong:
        print(f"\n  --- 错误原因分析 ---")
        reason_counts = defaultdict(int)
        for q in wrong:
            llm_ans = q.get("generated_answer", "")
            layer = q.get("retrieval_layer", {})
            resolved = layer.get("resolved_layer", "none") if isinstance(layer, dict) else "none"
            is_sufficient = layer.get("is_sufficient_at_category", None) if isinstance(layer, dict) else None
            cat_count = layer.get("category_results_count", 0) if isinstance(layer, dict) else 0
            res_count = layer.get("resource_results_count", 0) if isinstance(layer, dict) else 0
            
            # 判断失败原因
            contexts = q.get("retrieved_contexts", [])
            has_2026 = any("2026" in c for c in contexts)
            has_correct_info = any(q.get("standard_answer", "").lower()[:10] in c.lower() for c in contexts)
            
            if "don't have enough" in llm_ans or "没有足够" in llm_ans or "I cannot" in llm_ans:
                if res_count == 0 and resolved == "category_only":
                    reason = "A-仅在category层检索，未下钻resource，信息不足"
                elif res_count > 0:
                    reason = "B-resource层也检索了，但LLM仍认为信息不足（检索未命中关键记忆）"
                else:
                    reason = "C-其他信息不足情况"
            elif has_2026 and not has_correct_info:
                reason = "D-检索到2026时间戳记忆，原始2023时间信息缺失"
            elif has_correct_info:
                reason = "E-检索到了正确信息但LLM回答错误（生成问题）"
            else:
                reason = "F-检索未命中相关记忆（召回问题）"
            
            reason_counts[reason] += 1
        
        for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
            print(f"    {reason}: {count}个")
    
    # 具体案例
    print(f"\n  --- 错误案例详情(前5) ---")
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
        print(f"      标准答案: {q['standard_answer']}")
        print(f"      LLM回答: {q['generated_answer'][:100]}")
        print(f"      层级: {resolved} | category充足: {is_suff} | cat条数: {cat_cnt} | res条数: {res_cnt} | 有2026: {has_2026}")
        if contexts:
            print(f"      Top3检索:")
            for j, (ctx, sc) in enumerate(zip(contexts[:3], scores[:3] if scores else [0]*3)):
                print(f"        [{j+1}] score={sc:.4f} | {ctx[:80]}")

# ============================================================
# 2. 正确案例的层级贡献度分析
# ============================================================
print(f"\n\n{'='*70}")
print(f"  正确案例层级贡献度分析")
print(f"{'='*70}")

correct_items = [q for q in results if q.get("is_correct")]
print(f"\n  正确总数: {len(correct_items)}")

# 按resolved_layer分组
layer_groups = defaultdict(list)
for q in correct_items:
    layer = q.get("retrieval_layer", {})
    resolved = layer.get("resolved_layer", "none") if isinstance(layer, dict) else "none"
    layer_groups[resolved].append(q)

for layer_name, items in sorted(layer_groups.items()):
    print(f"\n  === {layer_name} ({len(items)}个正确) ===")
    
    # 分析每个正确案例：category层和resource层分别检索了多少条
    cat_contrib = 0  # category层信息已足够回答的
    res_contrib = 0  # 需要resource层才回答对的
    both_contrib = 0  # 两层都有贡献
    
    for q in items:
        layer = q.get("retrieval_layer", {})
        is_suff = layer.get("is_sufficient_at_category", None) if isinstance(layer, dict) else None
        cat_cnt = layer.get("category_results_count", 0) if isinstance(layer, dict) else 0
        res_cnt = layer.get("resource_results_count", 0) if isinstance(layer, dict) else 0
        cat_scores = q.get("category_scores", [])
        res_scores = q.get("resource_scores", [])
        
        if is_suff is True and res_cnt == 0:
            cat_contrib += 1  # 仅category层就足够
        elif is_suff is False and res_cnt > 0:
            res_contrib += 1  # category不足，resource层补上了
        elif is_suff is True and res_cnt > 0:
            both_contrib += 1  # category说足够但还检索了resource
        else:
            both_contrib += 1
    
    print(f"    仅category层足够: {cat_contrib} ({cat_contrib/len(items)*100:.1f}%)")
    print(f"    category不足需resource: {res_contrib} ({res_contrib/len(items)*100:.1f}%)")
    print(f"    两层都有贡献: {both_contrib} ({both_contrib/len(items)*100:.1f}%)")

# ============================================================
# 3. 更细粒度：对于category+resource的正确案例，看category层检索质量
# ============================================================
print(f"\n\n{'='*70}")
print(f"  category+resource 正确案例：category层检索质量分析")
print(f"{'='*70}")

cr_items = [q for q in correct_items if 
    (q.get("retrieval_layer", {}).get("resolved_layer") if isinstance(q.get("retrieval_layer"), dict) else None) == "category+resource"]

print(f"\n  总数: {len(cr_items)}")

# 看category层是否已经检索到了正确信息
cat_already_has_answer = 0
cat_missing_answer = 0

for q in cr_items:
    layer = q.get("retrieval_layer", {})
    is_suff = layer.get("is_sufficient_at_category", None)
    contexts = q.get("retrieved_contexts", [])
    std_ans = q.get("standard_answer", "").lower()
    
    # 检查category层检索的前几条（resource在后面）
    cat_cnt = layer.get("category_results_count", 0)
    cat_contexts = contexts[:cat_cnt] if cat_cnt > 0 else []
    
    # 简单判断category层是否包含标准答案关键词
    cat_has_info = any(
        any(kw in c.lower() for kw in std_ans.split() if len(kw) > 3)
        for c in cat_contexts
    ) if cat_contexts and std_ans else False
    
    if cat_has_info:
        cat_already_has_answer += 1
    else:
        cat_missing_answer += 1

print(f"  category层已含答案关键词: {cat_already_has_answer} ({cat_already_has_answer/len(cr_items)*100:.1f}%)" if cr_items else "")
print(f"  category层缺失答案关键词: {cat_missing_answer} ({cat_missing_answer/len(cr_items)*100:.1f}%)" if cr_items else "")

# 展示几个典型案例
print(f"\n  --- 典型正确案例(前5) ---")
for i, q in enumerate(cr_items[:5], 1):
    layer = q.get("retrieval_layer", {})
    is_suff = layer.get("is_sufficient_at_category", "?")
    cat_cnt = layer.get("category_results_count", 0)
    res_cnt = layer.get("resource_results_count", 0)
    contexts = q.get("retrieved_contexts", [])
    scores = q.get("retrieved_scores", [])
    
    print(f"  [{i}] Q: {q['question']}")
    print(f"      A: {q['standard_answer']}")
    print(f"      category充足: {is_suff} | cat: {cat_cnt}条 | res: {res_cnt}条")
    # 展示category层top2
    for j in range(min(2, cat_cnt)):
        if j < len(contexts) and j < len(scores):
            print(f"      [Cat-{j+1}] score={scores[j]:.4f} | {contexts[j][:80]}")
    # 展示resource层top2
    for j in range(min(2, res_cnt)):
        idx = cat_cnt + j
        if idx < len(contexts) and idx < len(scores):
            print(f"      [Res-{j+1}] score={scores[idx]:.4f} | {contexts[idx][:80]}")

# ============================================================
# 4. 2026时间戳问题统计
# ============================================================
print(f"\n\n{'='*70}")
print(f"  2026时间戳问题统计")
print(f"{'='*70}")

total_with_2026 = 0
correct_with_2026 = 0
wrong_with_2026 = 0

for q in results:
    contexts = q.get("retrieved_contexts", [])
    has_2026 = any("2026" in c for c in contexts)
    if has_2026:
        total_with_2026 += 1
        if q.get("is_correct"):
            correct_with_2026 += 1
        else:
            wrong_with_2026 += 1

print(f"  检索结果含2026记忆的问题: {total_with_2026}/90 ({total_with_2026/90*100:.1f}%)")
print(f"    其中正确: {correct_with_2026}")
print(f"    其中错误: {wrong_with_2026}")

# 没有2026的情况
no_2026 = [q for q in results if not any("2026" in c for c in q.get("retrieved_contexts", []))]
no_2026_correct = [q for q in no_2026 if q.get("is_correct")]
print(f"\n  检索结果不含2026的问题: {len(no_2026)}/90")
print(f"    其中正确: {len(no_2026_correct)} ({len(no_2026_correct)/len(no_2026)*100:.1f}%)" if no_2026 else "")

# ============================================================
# 5. "信息不足"类回答统计
# ============================================================
print(f"\n\n{'='*70}")
print(f"  '信息不足'类回答统计")
print(f"{'='*70}")

no_info = [q for q in results if "don't have enough" in q.get("generated_answer", "").lower() 
           or "没有足够" in q.get("generated_answer", "")
           or "I cannot" in q.get("generated_answer", "")]

print(f"  回答'信息不足'的问题: {len(no_info)}/90 ({len(no_info)/90*100:.1f}%)")

# 按层级分
for q in no_info[:10]:
    layer = q.get("retrieval_layer", {})
    resolved = layer.get("resolved_layer", "?") if isinstance(layer, dict) else "?"
    is_suff = layer.get("is_sufficient_at_category", "?") if isinstance(layer, dict) else "?"
    cat_cnt = layer.get("category_results_count", 0) if isinstance(layer, dict) else 0
    res_cnt = layer.get("resource_results_count", 0) if isinstance(layer, dict) else 0
    print(f"  Q: {q['question'][:50]} | layer={resolved} | suff={is_suff} | cat={cat_cnt} | res={res_cnt}")
