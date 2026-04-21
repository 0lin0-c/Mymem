import json

a = json.load(open('data/converted_data_recent_2026q1/sample_0_caroline_converted.json', 'r', encoding='utf-8'))
b = json.load(open('data/converted_data_recent_2026q1_name_trimmed/sample_0_caroline_converted.json', 'r', encoding='utf-8'))

# Compare all sessions
total_diffs = 0
for si in range(len(a['sessions'])):
    sa = a['sessions'][si]['content']
    sb = b['sessions'][si]['content']
    lines_a = sa.split('\n')
    lines_b = sb.split('\n')
    
    diffs = []
    for i, (la, lb) in enumerate(zip(lines_a, lines_b)):
        if la != lb:
            diffs.append((i+1, la, lb))
    
    if diffs:
        total_diffs += len(diffs)
        print(f"\n=== Session {si+1}: {len(diffs)} differing lines ===")
        for i, la, lb in diffs[:8]:  # show first 8 diffs per session
            print(f"  Line {i}:")
            print(f"    ORIG: {la[:130]}")
            print(f"    TRIM: {lb[:130]}")
        if len(diffs) > 8:
            print(f"  ... and {len(diffs)-8} more diffs")

print(f"\n\nTotal differing lines across all sessions: {total_diffs}")

# Also check if there are structural differences (keys, metadata)
print("\n=== Structural comparison ===")
for key in a:
    if key == 'sessions':
        continue
    if a[key] != b[key]:
        print(f"  {key}: '{a[key]}' vs '{b[key]}'")
    else:
        print(f"  {key}: same")
