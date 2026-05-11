from pathlib import Path
text = Path('progress.json').read_text(encoding='utf-8')
for needle in [
    'decision-global-retrieval-tuning-before-exact-fact-research',
    'task-extend-eval-timeout-to-6-hours',
]:
    idx = text.find(needle)
    print('needle', needle, 'idx', idx)
    if idx >= 0:
        start = max(0, idx-200)
        end = min(len(text), idx+1200)
        print(text[start:end])
        print('---')
