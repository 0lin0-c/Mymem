from pathlib import Path
text = Path('tests/conftest.py').read_text(encoding='utf-8')
for pat in ['async def db_engine', 'DELETE FROM resource_categories', 'async def db_session']:
    idx = text.find(pat)
    print('\nPATTERN:', pat, 'IDX', idx)
    print(text[max(0, idx-250): idx+500])
