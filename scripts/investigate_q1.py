"""问题1：检索未命中 = 数据库没有 还是 检索不到？"""
import asyncio
import asyncpg
import json
from pathlib import Path

result_file = sorted(Path("test_results/converted_data/legacy").glob("mymem_test_results_20260417_07481*.json"))[-1]
d = json.load(open(result_file, "r", encoding="utf-8"))
sample = d["samples"][0]
results = sample["qa_results"]
user_id = sample["user_id"]

# 取Cat1-3中"信息不足"的错误案例（这些最可能是检索未命中）
no_info_questions = [q for q in results if 
    not q.get("is_correct") and 
    q.get("category", 0) <= 3 and
    ("don't have enough" in q.get("generated_answer", "").lower() or 
     "没有足够" in q.get("generated_answer", "") or
     "I cannot" in q.get("generated_answer", ""))]

print(f"Cat1-3中'信息不足'的问题: {len(no_info_questions)}个")
print(f"user_id: {user_id}")

async def check():
    conn = await asyncpg.connect(
        host="192.168.31.95", port=46195,
        user="postgres", password="Xzc000813!",
        database="postgres"
    )
    
    # 获取所有resource记忆内容
    rows = await conn.fetch(
        "SELECT description, raw_content FROM resources WHERE user_id = $1",
        user_id
    )
    all_memories = [r["description"] or r["raw_content"] or "" for r in rows]
    print(f"\n数据库中总记忆数: {len(all_memories)}")
    
    # 对每个问题，检查数据库中是否有包含标准答案关键词的记忆
    print(f"\n{'='*70}")
    print(f"  逐题检查：数据库中是否存在包含答案的记忆")
    print(f"{'='*70}")
    
    for i, q in enumerate(no_info_questions[:15], 1):
        std = q["standard_answer"]
        question = q["question"]
        cat = q.get("category", "?")
        
        # 从标准答案提取关键词
        keywords = [w for w in std.replace(",", " ").replace(".", " ").split() if len(w) > 3]
        
        # 在数据库中搜索
        found_memories = []
        for mem in all_memories:
            mem_lower = mem.lower()
            # 检查是否有多个关键词匹配
            match_count = sum(1 for kw in keywords if kw.lower() in mem_lower)
            if match_count >= max(1, len(keywords) // 2):  # 至少匹配一半关键词
                found_memories.append(mem)
        
        # 同时检查问题中的关键词
        q_keywords = [w for w in question.replace("?", " ").replace("'", " ").split() if len(w) > 4]
        q_found = []
        for mem in all_memories:
            mem_lower = mem.lower()
            if any(kw.lower() in mem_lower for kw in q_keywords):
                q_found.append(mem)
        
        status = "DB中有" if found_memories else "DB中无"
        print(f"\n  [{i}] Cat{cat} | Q: {question[:60]}")
        print(f"      标准答案: {std}")
        print(f"      数据库状态: {status} (关键词匹配: {len(found_memories)}条, 问题相关: {len(q_found)}条)")
        
        if found_memories:
            for j, m in enumerate(found_memories[:2], 1):
                print(f"      匹配记忆[{j}]: {m[:100]}")
        
        if not found_memories and q_found:
            print(f"      问题相关记忆(但不含答案):")
            for j, m in enumerate(q_found[:2], 1):
                print(f"        [{j}]: {m[:100]}")
    
    await conn.close()

asyncio.run(check())
