# -*- coding: utf-8 -*-
"""
로컬 웹앱 서버: 뷰어(모든 탭) + 실시간 생성기를 한 번에 제공.

실행:
    python src/server.py        # http://127.0.0.1:8000 자동 오픈

- GET  /             → output/viewer.html (뷰어; '✎ 직접 생성' 탭 포함)
- GET  /<경로>       → output/ 아래 정적 파일(refs/strips/sheets svg·png)
- POST /generate     → {text, gray} 받아 그림콘티 SVG 생성 → {svg, panels, shots}

의존성 없음(파이썬 표준 라이브러리). 분류기/렌더러 재사용.
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import genapi as G

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HOST, PORT = "127.0.0.1", 8000
OUT_DIR = (Path(__file__).resolve().parent.parent / "output").resolve()

MIME = {".html": "text/html; charset=utf-8", ".svg": "image/svg+xml",
        ".png": "image/png", ".json": "application/json; charset=utf-8",
        ".js": "text/javascript", ".css": "text/css"}


class Handler(BaseHTTPRequestHandler):
    def _headers(self, code, ctype, length):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Access-Control-Allow-Origin", "*")   # file://에서도 호출 가능
        self.end_headers()

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self._headers(code, ctype, len(data))
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = unquote(self.path.split("?")[0])
        rel = "index.html" if path == "/" else path.lstrip("/")
        fp = (OUT_DIR / rel).resolve()
        if OUT_DIR not in fp.parents and fp != OUT_DIR:      # 경로 탈출 방지
            self._send(403, "forbidden"); return
        if fp.is_file():
            self._send(200, fp.read_bytes(), MIME.get(fp.suffix.lower(), "application/octet-stream"))
        elif rel in ("index.html", "viewer.html"):
            self._send(200, f"<h2>{rel}이 없습니다. 먼저 <code>python src/build_viewer.py</code> 실행</h2>")
        else:
            self._send(404, "not found")

    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
            if path in ("/generate", "/api/generate"):       # Vercel과 동일 경로 호환
                out = G.gen(req.get("text", ""), req.get("gray", True))
            elif path in ("/panel", "/api/panel"):
                out = G.panel(req)
            elif path in ("/format", "/api/format"):
                out = G.fmt(req.get("text", ""))
            elif path in ("/cut", "/api/cut"):
                out = G.cut(req)
            else:
                self._send(404, "not found"); return
            self._send(200, json.dumps(out, ensure_ascii=False), "application/json; charset=utf-8")
        except Exception as e:
            self._send(200, json.dumps({"error": str(e)}, ensure_ascii=False),
                       "application/json; charset=utf-8")

    def log_message(self, *a):
        pass


def main():
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}"
    print(f"✅ 뷰어+생성기 실행 중 → {url}")
    print("   '✎ 직접 생성' 탭에서 글콘티를 입력하고 생성하세요. 종료: Ctrl+C")
    try:
        import webbrowser
        webbrowser.open(url)
    except Exception:
        pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n종료.")


if __name__ == "__main__":
    main()
