"""英文 → 区切り音声 → 実験版に置く（課題2）。

使い方：
  python3 tools/make_audio.py texts/<id>.txt --model <kokoro-v1.0.int8.onnx> --voices <voices-v1.0.bin>
入力：texts/<id>.txt（1行目が「# 題名」、2行目以降が英文。空行で段落を分けてよい）
出力（リポジトリの直下）：
  <id>-001.mp3 …   区切りごとの音声（全体ファイルが使えない時の予備）
  <id>-all.mp3      英文全体を1本にした音声（画面オフで止まらず通すための本命）
  <id>.json         題名・区切りの英文・開始時刻 o・長さ s
  list.json         一覧に <id> を追加（同じ id があれば置き換え）
声と方式は既存の実験版と同じ：Kokoro int8（kokoro-v1.0.int8.onnx）・af_heart・24kHz モノラル 48kbps。
"""
import argparse, glob, hashlib, json, os, re, subprocess, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reading import normalize_for_reading

SR = 24000
GAP = 0.45          # 区切りの後の無音（秒）
MIN_CHARS = 80      # 短い文はこの長さになるまで次の文とまとめる
MAX_CHARS = 220     # まとめる時の上限


def split_sentences(text):
    text = re.sub(r'\s+', ' ', text).strip()
    # 文末（. ! ? と閉じ引用符）で区切る。Dr. Mr. や 3.5 は区切らない
    parts = re.split(r'(?:(?<=[.!?])|(?<=[.!?]["”’)]))\s+(?=["“(]?[A-Z0-9])', text)
    out = []
    for p in parts:
        if out and re.search(r'\b(?:Dr|Mr|Mrs|Ms|St)\.$', out[-1]):
            out[-1] += ' ' + p
        else:
            out.append(p)
    return [p.strip() for p in out if p.strip()]


def group(sents):
    segs, cur = [], ''
    for s in sents:
        if not cur:
            cur = s
        elif len(cur) < MIN_CHARS and len(cur) + 1 + len(s) <= MAX_CHARS:
            cur += ' ' + s
        else:
            segs.append(cur); cur = s
    if cur:
        if segs and len(cur) < MIN_CHARS // 2 and len(segs[-1]) + 1 + len(cur) <= MAX_CHARS:
            segs[-1] += ' ' + cur
        else:
            segs.append(cur)
    return segs


def trim(a, th=0.01):
    idx = np.where(np.abs(a) > th)[0]
    if not len(idx):
        return a
    return a[max(0, idx[0] - int(0.03 * SR)):min(len(a), idx[-1] + int(0.05 * SR))]


def fade(a, ms=10):
    m = int(SR * ms / 1000); a = a.copy()
    if len(a) > 2 * m:
        a[:m] *= np.linspace(0, 1, m); a[-m:] *= np.linspace(1, 0, m)
    return a


def to_mp3(a, path):
    pcm = (np.clip(a, -1, 1) * 32767).astype('<i2').tobytes()
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 's16le', '-ar', str(SR), '-ac', '1', '-i', 'pipe:0',
                    '-ar', str(SR), '-ac', '1', '-b:a', '48k', path], input=pcm, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('text'); ap.add_argument('--model', required=True); ap.add_argument('--voices', required=True)
    ap.add_argument('--out', default='.'); ap.add_argument('--voice', default='af_heart')
    ap.add_argument('--skip-unchanged', action='store_true', help='英文が前回と同じなら作り直さない')
    o = ap.parse_args()
    raw = open(o.text, 'rb').read(); src = hashlib.sha256(raw).hexdigest()[:16]
    from kokoro_onnx import Kokoro
    tid = os.path.splitext(os.path.basename(o.text))[0]
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,40}', tid):
        sys.exit('ファイル名（id）は小文字英数字とハイフンだけにしてください：' + tid)
    jp = os.path.join(o.out, f'{tid}.json')
    if o.skip_unchanged and os.path.exists(jp):
        try:
            if json.load(open(jp, encoding='utf-8')).get('src') == src: print(f'変更なし：{tid}'); return
        except Exception: pass
    lines = raw.decode('utf-8').splitlines()
    title = lines[0].lstrip('#').strip() if lines and lines[0].startswith('#') else tid
    body = '\n'.join(lines[1:] if lines and lines[0].startswith('#') else lines)
    # 区切り：英文の1行＝1区切り（書き手が決めた意味のまとまりを優先）。長すぎる行と、改行のない段落は文ごとにまとめ直す
    segs = []
    for line in [x.strip() for x in body.splitlines() if x.strip()]:
        segs += [line] if len(line) <= MAX_CHARS else group(split_sentences(line))
    K = Kokoro(o.model, o.voices)
    audio = []
    for i, s in enumerate(segs):
        a, sr = K.create(normalize_for_reading(s), voice=o.voice, speed=1.0, lang='en-us')
        assert sr == SR
        audio.append(fade(trim(np.asarray(a, dtype=np.float32))))
        print(f'{i + 1}/{len(segs)} {len(audio[-1]) / SR:.1f}s', flush=True)
    allw = np.concatenate([np.concatenate([x, np.zeros(int(SR * GAP), np.float32)]) for x in audio])
    rms = float(np.sqrt(np.mean(allw ** 2)) + 1e-9)
    gain = min(0.112 / rms, 0.89 / (np.abs(allw).max() + 1e-9))   # サーバー版と同じ音量合わせ（約-19dBFS、ピーク-1dB）
    for f in glob.glob(os.path.join(o.out, f'{tid}-[0-9][0-9][0-9].mp3')): os.remove(f)  # 区切りが減った時の古いファイルを残さない
    tracks, off = [], 0.0
    for i, (s, x) in enumerate(zip(segs, audio)):
        seg = np.concatenate([x, np.zeros(int(SR * GAP), np.float32)]) * gain
        f = f'{tid}-{i + 1:03d}.mp3'
        to_mp3(seg, os.path.join(o.out, f))
        tracks.append({'f': f, 't': s, 's': round(len(seg) / SR, 1), 'o': round(off, 3)})
        off += len(seg) / SR
    to_mp3(allw * gain, os.path.join(o.out, f'{tid}-all.mp3'))
    data = {'title': title, 'all': f'{tid}-all.mp3', 'src': src, 'tracks': tracks}
    json.dump(data, open(jp, 'w', encoding='utf-8'), ensure_ascii=False)
    lp = os.path.join(o.out, 'list.json')
    L = json.load(open(lp, encoding='utf-8')) if os.path.exists(lp) else []
    L = [{'title': title, 'json': f'{tid}.json', 'id': tid}] + [x for x in L if x.get('id') != tid]  # 新しい英文を一覧の先頭に
    json.dump(L, open(lp, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'完了：{tid}（{len(segs)}区切り・{off:.1f}秒）')


if __name__ == '__main__':
    main()
