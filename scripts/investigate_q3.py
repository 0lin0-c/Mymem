"""问题3：不同Cat类型的区别 + 充足性判断的问题"""
import json
from pathlib import Path
from collections import defaultdict

result_file = sorted(Path("test_results/converted_data/legacy").glob("mymem_test_results_20260417_07481*.json"))[-1]
d = json.load(open(result_file, "r", encoding="utf-8"))
sample = d["samples"][0]
results = sample["qa_results"]

# ============================================================
# 问题3：不同Cat类型的区别
# ============================================================
cat_names = {1: "Cat1", 2: "Cat2", 3: "Cat3", 4: "Cat4", 5: "Cat5"}

print("=" * 70)
print("  不同Cat类型的问题特征分析")
print("=" * 70)

for cat_id in range(1, 6):
    items = [q for q in results if q.get("category") == cat_id]
    correct = sum(1 for q in items if q.get("is_correct"))
    
    # 收集答案特征
    has_time = 0  # 答案含时间
    has_number = 0  # 答案含数字
    has_name = 0  # 答案含人名/地名
    short_answer = 0  # 答案<5词
    long_answer = 0  # 答案>=5词
    
    for q in items:
        ans = q.get("standard_answer", "")
        words = ans.split()
        
        # 时间检测
        import re
        if re.search(r'\d{4}|January|February|March|April|May|June|July|August|September|October|November|December|\d+\s+(days?|weeks?|months?|years?|ago)', ans, re.I):
            has_time += 1
        if re.search(r'\d+', ans):
            has_number += 1
        if len(words) < 5:
            short_answer += 1
        else:
            long_answer += 1
    
    print(f"\n  {cat_names[cat_id]}: {len(items)}个问题, 正确{correct}个 ({correct/len(items)*100:.1f}%)")
    print(f"    答案含时间: {has_time} ({has_time/len(items)*100:.0f}%)")
    print(f"    答案含数字: {has_number} ({has_number/len(items)*100:.0f}%)")
    print(f"    短答案(<5词): {short_answer} ({short_answer/len(items)*100:.0f}%)")
    print(f"    长答案(>=5词): {long_answer} ({long_answer/len(items)*100:.0f}%)")
    
    # 展示典型问题
    print(f"    典型问题:")
    for q in items[:3]:
        print(f"      Q: {q['question'][:60]}")
        print(f"      A: {q['standard_answer'][:60]}")

# ============================================================
# 问题2：充足性判断的矛盾分析
# ============================================================
print(f"\n\n{'=' * 70}")
print("  问题2：充足性判断为什么'判断足够但实际不够'")
print("=" * 70)

# category_only的15个问题详细分析
cat_only = [q for q in results if
    (q.get("retrieval_layer", {}).get("resolved_layer") if isinstance(q.get("retrieval_layer"), dict) else None) == "category_only"]

print(f"\n  category_only层级的问题: {len(cat_only)}个（全部回答错误）")
print(f"  这些问题被LLM判断'category层信息足够回答'")
print(f"  但最终LLM回答全部错误")
print()

for i, q in enumerate(cat_only, 1):
    layer = q.get("retrieval_layer", {})
    is_suff = layer.get("is_sufficient_at_category", "?")
    cat_cnt = layer.get("category_results_count", 0)
    contexts = q.get("retrieved_contexts", [])
    llm_ans = q.get("generated_answer", "")
    
    # 看LLM回答是什么
    if "don't have enough" in llm_ans.lower() or "没有足够" in llm_ans:
        outcome = "LLM自己也说信息不足"
    elif "I cannot" in llm_ans:
        outcome = "LLM自己也说无法回答"
    else:
        outcome = "LLM给了错误答案"
    
    print(f"  [{i}] Q: {q['question'][:55]}")
    print(f"      标准答案: {q['standard_answer'][:50]}")
    print(f"      充足性判断: {is_suff} | 结果: {outcome}")
    print(f"      LLM回答: {llm_ans[:80]}")
    print()

# 关键洞察
print(f"\n  === 关键洞察 ===")
suff_but_no_info = [q for q in cat_only if 
    "don't have enough" in q.get("generated_answer", "").lower() or 
    "没有足够" in q.get("generated_answer", "") or
    "I cannot" in q.get("generated_answer", "")]
suff_but_wrong = [q for q in cat_only if q not in suff_but_no_info]

print(f"  充足性判断='足够'，但回答时LLM自己说信息不足: {len(suff_but_no_info)}个")
print(f"  充足性判断='足够'，但LLM给了错误答案: {len(suff_but_wrong)}个")
print()
print(f"  这说明存在两个不同的LLM调用：")
print(f"    1. 充足性判断LLM：基于category摘要判断'足够'")
print(f"    2. 回答生成LLM：基于同样的category摘要，发现无法回答")
print(f"  两次调用对信息充分性的判断不一致！")
print(f"  原因：充足性判断prompt说'优先判断为足够'，偏向乐观；")
print(f"        回答生成时面对具体问题，发现缺少细节，无法回答。")

# ============================================================
# 补充：看category层检索的内容到底是什么
# ============================================================
print(f"\n\n{'=' * 70}")
print("  category层检索内容到底是什么？")
print("=" * 70)

# 取几个category_only问题，看检索到的内容
for q in cat_only[:5]:
    contexts = q.get("retrieved_contexts", [])
    print(f"\n  Q: {q['question'][:55]}")
    print(f"  A: {q['standard_answer']}")
    print(f"  检索到的category内容:")
    for j, ctx in enumerate(contexts[:3], 1):
        print(f"    [{j}] {ctx[:100]}")
