import json
from collections import Counter

d = json.load(open('data/locomo10.json', 'r', encoding='utf-8'))
s0 = d[0]
qa = s0.get('qa', [])

cats = Counter(q.get('category') for q in qa)
print('Original category distribution:')
for k, v in sorted(cats.items()):
    empty = sum(1 for q in qa if q.get('category') == k and not str(q.get('answer', '')).strip())
    print(f'  Cat{k}: {v} questions, {empty} empty answers')

for cat_id in range(1, 6):
    items = [q for q in qa if q.get('category') == cat_id]
    print(f'\nCat{cat_id} examples:')
    for q in items[:3]:
        ans = q.get('answer', '')
        print(f'  Q: {q["question"][:60]} | A: "{ans}"')
