"""読み上げ補正の自動テスト（確認済みの範囲が壊れていないか）"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
from reading import normalize_for_reading as n
cases = [
    ('It was $6.75.', 'It was 6 dollars and 75 cents.'),
    ('Meet at 7:30.', 'Meet at 7 thirty.'),
    ('Since 2026, we go.', 'Since twenty twenty-six, we go.'),
    ('Dr. Smith is here.', 'Doctor Smith is here.'),
    ('It opens at 9 a.m. Then we eat.', 'It opens at 9 AM. Then we eat.'),
    ('It costs ¥500.', 'It costs 500 yen.'),
]
bad = [(a, n(a), b) for a, b in cases if n(a) != b]
for a, got, want in bad: print(f'✗ {a!r} → {got!r}（期待：{want!r}）')
print(f'読み上げ補正：合格 {len(cases) - len(bad)} / {len(cases)}')
sys.exit(1 if bad else 0)
