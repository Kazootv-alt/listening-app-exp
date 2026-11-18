"""試験用の簡易サーバー：GitHub Pages と同じく部分取得（Range）に応える（音声の位置移動の試験に必要）
使い方：python3 tests/serve_range.py <配信するフォルダ> <ポート>"""
import http.server, io, os, re, sys


class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass

    def end_headers(self):
        self.send_header('Accept-Ranges', 'bytes'); super().end_headers()

    def send_head(self):
        rng = self.headers.get('Range'); path = self.translate_path(self.path)
        if not rng or not os.path.isfile(path): return super().send_head()
        size = os.path.getsize(path); m = re.match(r'bytes=(\d*)-(\d*)', rng)
        a = int(m.group(1) or 0); b = min(int(m.group(2)) if m.group(2) else size - 1, size - 1)
        with open(path, 'rb') as f: f.seek(a); data = f.read(b - a + 1)
        self.send_response(206); self.send_header('Content-Type', self.guess_type(path))
        self.send_header('Content-Range', f'bytes {a}-{b}/{size}'); self.send_header('Content-Length', str(len(data))); self.end_headers()
        return io.BytesIO(data)


os.chdir(sys.argv[1]); http.server.ThreadingHTTPServer(('127.0.0.1', int(sys.argv[2])), H).serve_forever()
