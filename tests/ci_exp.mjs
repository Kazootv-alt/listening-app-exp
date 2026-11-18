// 実験版の自動テスト（GitHub Actions で毎回動く）。失敗があれば終了コード1。
// 使い方：node tests/ci_exp.mjs http://127.0.0.1:8900/   （tests/serve_range.py で配信しておく）
import fs from 'node:fs';
const { chromium } = await import(process.env.PW || 'playwright');
const BASE = process.argv[2] || 'http://127.0.0.1:8900/';
const ok = [], ng = [];
const check = (name, cond, info) => { (cond ? ok : ng).push(name + (cond ? '' : '  → ' + JSON.stringify(info))); };
// 1 中身（ファイル）の点検：一覧の英文ごとに json・全体mp3・区切りmp3 が揃い、開始時刻が増えていく
const list = JSON.parse(fs.readFileSync('list.json', 'utf8'));
check('一覧が空でない', list.length > 0, list);
for (const x of list) {
  const j = JSON.parse(fs.readFileSync(x.json, 'utf8'));
  check(`${x.id}: 全体mp3あり`, j.all && fs.existsSync(j.all), j.all);
  check(`${x.id}: 区切りmp3が全部ある`, j.tracks.every(t => fs.existsSync(t.f)), j.tracks.filter(t => !fs.existsSync(t.f)).map(t => t.f));
  check(`${x.id}: 開始時刻が増えていく`, j.tracks.every((t, i) => i === 0 ? t.o === 0 : t.o > j.tracks[i - 1].o), j.tracks.map(t => t.o));
  check(`${x.id}: 英文が空でない`, j.tracks.every(t => t.t && t.t.trim()), null);
}
for (const f of fs.readdirSync('texts').filter(f => f.endsWith('.txt'))) {
  const id = f.replace(/\.txt$/, '');
  check(`texts/${f}: 音声が作られている`, list.some(x => x.id === id) && fs.existsSync(id + '.json'), id);
}
// 2 画面の動き（iPhone相当の画面幅）
const b = await chromium.launch(process.env.CHROMIUM ? { executablePath: process.env.CHROMIUM } : {});
const p = await (await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, serviceWorkers: 'block' })).newPage();
p.setDefaultTimeout(20000);
const errs = []; p.on('pageerror', e => errs.push(e.message));
const step = n => console.log('… ' + n);
setTimeout(async () => { console.log('時間切れ（3分）。最後の画面を test-shot.png に保存'); try { await p.screenshot({ path: 'test-shot.png' }); } catch (e) { } process.exit(2); }, 180000).unref();
await p.goto(BASE); await p.waitForFunction(() => document.getElementById('txt').textContent.length > 0, null, { timeout: 15000 });
const st = () => p.evaluate(() => { const a = document.getElementById('au'); return { sel: document.getElementById('sel').value, no: document.getElementById('no').textContent, t: +a.currentTime.toFixed(2), paused: a.paused, src: a.src.split('/').pop() }; });
const first = list[0];
check('最初は一覧の先頭の英文', (await st()).sel === first.json, await st());
check('選択肢の数＝一覧の数', (await p.$$eval('#sel option', o => o.length)) === list.length, null);
await p.tap('#bg'); await p.waitForTimeout(1200); let s = await st();
check('再生で全体mp3が鳴る', !s.paused && s.src === first.id + '-all.mp3' && s.t > 0, s);
await p.tap('#bn'); await p.waitForTimeout(800); s = await st();
const j0 = JSON.parse(fs.readFileSync(first.json, 'utf8'));
const n = x => +(x.no.match(/区切り (\d+)/) || [])[1];
check('次へで2番目の区切りへ', n(s) === 2 && s.t >= j0.tracks[1].o - 0.1, s);
await p.evaluate(() => { document.getElementById('au').playbackRate = 4; }); await p.waitForTimeout(4000); s = await st();
const cur = j0.tracks.filter(t => t.o <= s.t).length;
check('再生が進むと表示の区切り番号も進む', cur > 2 && Math.abs(n(s) - cur) <= 1, { s, cur });
await p.evaluate(() => { document.getElementById('au').playbackRate = 1; });
const before = await st(); await p.reload(); await p.waitForFunction(() => document.getElementById('txt').textContent.length > 0); await p.waitForTimeout(800);
const after = await st();
check('開き直しても続きの位置', after.sel === before.sel && after.no === before.no, { before, after });
if (list.length > 1) { await p.selectOption('#sel', list[1].json); await p.waitForTimeout(800); s = await st(); check('英文の切り替え', s.sel === list[1].json, s); }
check('画面のエラーなし', errs.length === 0, errs);
await b.close();
console.log('合格 ' + ok.length + '件\n' + ok.map(x => '  ✓ ' + x).join('\n'));
if (ng.length) { console.log('不合格 ' + ng.length + '件\n' + ng.map(x => '  ✗ ' + x).join('\n')); process.exit(1); }
