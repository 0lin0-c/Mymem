"""问题1深入：数据库有记忆但检索未命中的具体原因"""
import asyncio
import asyncpg
import json
from pathlib import Path

result_file = sorted(Path("test_results/converted_data/legacy").glob("mymem_test_results_20260417_07481*.json"))[-1]
d = json.load(open(result_file, "r", encoding="utf-8"))
sample = d["samples"][0]
results = sample["qa_results"]
user_id = sample["user_id"]

# 选几个典型问题进行深入分析
test_questions = [
    {"q": "When did Caroline go to the LGBTQ support group?", "a": "7 May 2023", "cat": 2},
    {"q": "What did Caroline research?", "a": "Adoption agencies", "cat": 1},
    {"q": "What is Caroline's identity?", "a": "Transgender woman", "cat": 1},
    {"q": "What is Caroline's relationship status?", "a": "Single", "cat": 1},
    {"q": "Where did Caroline move from 4 years ago?", "a": "Sweden", "cat": 1},
    {"q": "What career path has Caroline decided to persue?", "a": "counseling or mental health for Transgender people", "cat": 2},
]

async def check():
    conn = await asyncpg.connect(
        host="192.168.31.95", port=46195,
        user="postgres", password="Xzc000813!",
        database="postgres"
    )
    
    # 获取所有resource记忆
    rows = await conn.fetch(
        "SELECT r.id, r.description, c.category_name FROM resources r LEFT JOIN resource_categories rc ON r.id = rc.resource_id LEFT JOIN categories c ON rc.category_id = c.id WHERE r.user_id = $1",
        user_id
    )
    all_resources = {}
    for r in rows:
        rid = r["id"]
        if rid not in all_resources:
            all_resources[rid] = {"description": r["description"], "categories": []}
        if r["category_name"]:
            all_resources[rid]["categories"].append(r["category_name"])
    
    print(f"总记忆数: {len(all_resources)}")
    
    # 获取所有category
    cat_rows = await conn.fetch(
        "SELECT category_name, content FROM categories WHERE user_id = $1",
        user_id
    )
    print(f"\n所有分类:")
    for r in cat_rows:
        print(f"  {r['category_name']}: {r['content'][:80]}")
    
    # 对每个测试问题
    for tq in test_questions:
        question = tq["q"]
        answer = tq["a"]
        
        # 在数据库中搜索包含答案关键词的记忆
        keywords = [w for w in answer.replace(",", " ").replace(".", " ").split() if len(w) > 2]
        
        matched_resources = []
        for rid, data in all_resources.items():
            desc = data["description"] or ""
            match_count = sum(1 for kw in keywords if kw.lower() in desc.lower())
            if match_count >= max(1, len(keywords) // 3):
                matched_resources.append((rid, desc, data["categories"], match_count))
        
        # 排序
        matched_resources.sort(key=lambda x: -x[3])
        
        print(f"\n{'='*70}")
        print(f"  Q: {question}")
        print(f"  A: {answer}")
        print(f"  关键词: {keywords}")
        print(f"  匹配记忆数: {len(matched_resources)}")
        
        if matched_resources:
            for i, (rid, desc, cats, mc) in enumerate(matched_resources[:3], 1):
                print(f"\n  匹配[{i}] 关键词命中={mc} | 分类={cats}")
                print(f"    内容: {desc[:150]}")
        else:
            print(f"  WARNING: 数据库中未找到包含答案的记忆！")
    
    await conn.close()

asyncio.run(check())
