"""Gemini による自動レビュー（無料枠の Flash モデル）。
直した中身（差分）と自動テストの結果を Gemini に読ませ、不具合・改善案・ボトルネックを日本語で出させて、
リポジトリの Issue「AIレビュー（Gemini）」にコメントとして残す。鍵（GEMINI_API_KEY）が無ければ何もしない。
Gemini の意見は参考情報。反映するかどうかは Claude（アプリ担当）が判断し、本人の承認ルールは変えない。"""
import json, os, re, subprocess, sys, urllib.request

key = os.environ.get('GEMINI_API_KEY', '')
if not key:
    print('GEMINI_API_KEY が未設定のため、レビューは行いません'); sys.exit(0)


def pick_model():
    """モデル名は時期で変わるので、指定が無ければ使える Flash の最新を自動で選ぶ（無料枠は Flash 系のみ）"""
    if os.environ.get('GEMINI_MODEL'): return [os.environ['GEMINI_MODEL']]
    try:
        r = urllib.request.Request('https://generativelanguage.googleapis.com/v1beta/models?pageSize=200', headers={'x-goog-api-key': key})
        names = [m['name'].split('/')[-1] for m in json.load(urllib.request.urlopen(r, timeout=30)).get('models', [])
                 if 'generateContent' in m.get('supportedGenerationMethods', [])]
        ok = [n for n in names if re.fullmatch(r'gemini-(\d+(?:\.\d+)?)-flash(?:-lite)?', n)]
        # 新しい順。同じ版なら通常版を先に、軽量版（lite）を後に
        ok.sort(key=lambda n: (float(re.search(r'\d+(?:\.\d+)?', n).group()), 'lite' not in n), reverse=True)
        if ok: return ok[:3]
    except Exception as e:
        print('モデル一覧を取れませんでした：', e)
    return ['gemini-2.5-flash']


models = pick_model()
mode = os.environ.get('REVIEW_MODE', 'change')  # change＝直した中身のレビュー／audit＝定期のボトルネック監査


def sh(*a):
    return subprocess.run(a, capture_output=True, text=True).stdout


def clip(t, n): return t if len(t) <= n else t[:n] + '\n…（長いので以下省略）'


tests = open(sys.argv[1], encoding='utf-8').read() if len(sys.argv) > 1 and os.path.exists(sys.argv[1]) else '（テスト結果なし）'
if mode == 'audit':
    issues = sh('gh', 'issue', 'list', '--state', 'all', '--limit', '30', '--json', 'title,state,body,comments')
    log = sh('git', 'log', '--since=14 days ago', '--format=%h %ad %s', '--date=short')
    task = ('あなたは英語学習アプリ（iPhoneで使うリスニング用のWebアプリ）の独立した監査役です。'
            '直近2週間の変更履歴・Issue・自動テストの結果から、開発の進み方そのもののボトルネックを見つけてください。'
            '観点：同じ種類の修正の繰り返し、利用者（本人）の手間、テストで見つけられていない不具合の兆候、遅い工程、自動化できる作業。')
    body = f'## 変更履歴（2週間）\n{clip(log, 8000)}\n\n## Issue\n{clip(issues, 20000)}\n\n## 自動テスト\n{clip(tests, 8000)}'
else:
    diff = sh('git', 'diff', '--stat', 'HEAD~1', 'HEAD') + '\n' + sh('git', 'diff', '-U2', 'HEAD~1', 'HEAD', '--', '.', ':(exclude)*.mp3', ':(exclude)*.wasm', ':(exclude)model/*', ':(exclude)SHA256SUMS.txt')
    msg = sh('git', 'log', '-1', '--format=%s%n%n%b')
    task = ('あなたは英語学習アプリ（iPhoneで使うリスニング用のWebアプリ）の独立したレビュー役です。'
            '次の変更について、(1)不具合やiPhone Safariで壊れそうな点、(2)利用者がもっと楽になる改善案、(3)この変更で確認できていない点、'
            'を具体的に（ファイル名と該当箇所付きで）挙げてください。問題が無い観点は「なし」と書く。推測は推測と明記。')
    body = f'## 変更の説明\n{msg}\n\n## 差分\n{clip(diff, 60000)}\n\n## 自動テストの結果\n{clip(tests, 8000)}'
req = {'contents': [{'role': 'user', 'parts': [{'text': task + '\n\n回答は日本語で、見出しと箇条書きで簡潔に。\n\n' + body}]}]}
import time
text, errs, model = None, [], models[0]
for model in models:  # 混雑（503・429）や時間切れなら、少し待ってやり直し、だめなら次のモデルへ
    for k in range(2):
        try:
            url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
            r = urllib.request.Request(url, data=json.dumps(req).encode(), headers={'Content-Type': 'application/json', 'x-goog-api-key': key})
            res = json.load(urllib.request.urlopen(r, timeout=150))
            text = ''.join(p.get('text', '') for p in res['candidates'][0]['content']['parts']); break
        except Exception as e:
            errs.append(f'{model}: {type(e).__name__} {str(e)[:120]}'); time.sleep(20)
    if text: break
if not text:
    text = 'Gemini を呼べませんでした（' + ' / '.join(errs) + '）'
title = 'AIレビュー（Gemini）' if mode != 'audit' else 'AIボトルネック監査（Gemini・定期）'
head = sh('git', 'log', '-1', '--format=%h %s').strip()
num = sh('gh', 'issue', 'list', '--state', 'open', '--search', f'"{title}" in:title', '--json', 'number', '--jq', '.[0].number').strip()
if not num:
    num = sh('gh', 'issue', 'create', '--title', title, '--body', 'Gemini による自動レビューの記録。アプリ担当（Claude）が読んで、反映するかを判断する。').strip().rsplit('/', 1)[-1]
comment = f'### {head}（モデル：{model}）\n\n{text}'
subprocess.run(['gh', 'issue', 'comment', num, '--body', clip(comment, 60000)], check=False)
print(comment[:3000])
