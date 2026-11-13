"""読み上げ用の最小補正（画面に出す英文は変えない）。
Listening App のサーバー版（tts_server.py と同じ reading.py）から移したもの。
対象は確認済みの範囲だけ：$ / ¥、年号、Dr. / Mr.、時刻、a.m. / p.m.、小数
（実験版での追加：文末の a.m. / p.m. の後に次の文が続く時も、文の区切りの点を残す）
"""
import re

_ONES = ['', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve',
         'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen']
_TENS = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety']


def _two(n):
    if n < 20:
        return _ONES[n]
    t, o = divmod(n, 10)
    return _TENS[t] + ('-' + _ONES[o] if o else '')


def year_words(y):
    """2026→twenty twenty-six, 2005→two thousand five, 1905→nineteen oh five, 1900→nineteen hundred"""
    if 2000 <= y <= 2009:
        return 'two thousand' + (' ' + _ONES[y - 2000] if y > 2000 else '')
    hi, lo = divmod(y, 100)
    if lo == 0:
        return _two(hi) + ' hundred'
    if lo < 10:
        return _two(hi) + ' oh ' + _ONES[lo]
    return _two(hi) + ' ' + _two(lo)


_MONTHS = r'(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan\.?|Feb\.?|Mar\.?|Apr\.?|Jun\.?|Jul\.?|Aug\.?|Sep\.?|Sept\.?|Oct\.?|Nov\.?|Dec\.?)'


def _money(m):
    sym, num = m.group(1), m.group(2).replace(',', '')
    if sym == '¥':
        return f'{num} yen'
    if '.' in num:
        d, c = num.split('.', 1)
        c = (c + '0')[:2]
        d_i, c_i = int(d or 0), int(c)
        parts = []
        if d_i or not c_i:
            parts.append(f'{d_i} dollar' + ('' if d_i == 1 else 's'))
        if c_i:
            parts.append(f'{c_i} cent' + ('' if c_i == 1 else 's'))
        return ' and '.join(parts)
    return f'{num} dollar' + ('' if num == '1' else 's')


def _time(m):
    h, mm = int(m.group(1)), int(m.group(2))
    if mm == 0:
        return f"{h} o'clock"
    if mm < 10:
        return f'{h} oh {mm}'
    return f'{h} {_two(mm)}'


def normalize_for_reading(t):
    t = re.sub(r'([$¥])\s?(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)', _money, t)
    t = re.sub(r'\b([01]?\d|2[0-3]):([0-5]\d)\b', _time, t)
    t = re.sub(r'\b([ap])\.\s?m\.(?=\s|$|[,;:!?])', lambda m: m.group(1).upper() + 'M' + ('.' if m.end() == len(m.string) or re.match(r'\s+[A-Z"“]', m.string[m.end():]) else ''), t, flags=re.I)
    t = re.sub(r'(' + _MONTHS + r'(?:\s+\d{1,2}(?:st|nd|rd|th)?)?,?\s+)((?:1[1-9]|20)\d\d)\b',
               lambda m: m.group(1) + year_words(int(m.group(2))), t)
    t = re.sub(r'\b(in|since|by|until|from|of)\s+((?:1[1-9]|20)\d\d)\b(?![\d,.]\d)',
               lambda m: m.group(1) + ' ' + year_words(int(m.group(2))), t, flags=re.I)
    t = re.sub(r'(?<![\d.,])(\d{1,3}(?:,\d{3})+|\d+)\.(\d+)(?![\d.]\d|\d)', lambda m: m.group(1) + ' point ' + ' '.join(m.group(2)), t)
    t = re.sub(r'\bDr\.(?=\s+[A-Z])', 'Doctor', t)
    t = re.sub(r'\bMr\.(?=\s+[A-Z])', 'Mister', t)
    return t
