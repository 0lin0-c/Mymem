from pathlib import Path
p = Path('progress.json')
data = p.read_bytes()
print(data[:120])
print('utf8_ok=', end='')
try:
    text = data.decode('utf-8')
    print(True)
    print(text[-1200:])
except Exception as e:
    print(False, e)
