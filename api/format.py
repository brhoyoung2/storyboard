# -*- coding: utf-8 -*-
"""
Vercel Python 서버리스 함수: POST /api/format
{text} → 자연글을 글콘티 형식으로 정리 → {text, count}
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler

_HERE = os.path.dirname(os.path.abspath(__file__))
for _cand in (os.path.join(_HERE, "..", "src"), os.path.join(_HERE, "src"), _HERE):
    if os.path.exists(os.path.join(_cand, "svg_render.py")):
        sys.path.insert(0, _cand)
        break

import genapi as G


class handler(BaseHTTPRequestHandler):
    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        try:
            n = int(self.headers.get("content-length", 0) or 0)
            req = json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
            self._json(G.fmt(req.get("text", "")))
        except Exception as e:
            self._json({"error": str(e)})

    def do_GET(self):
        self._json({"ok": True, "hint": "POST {text} 로 호출하세요."})

    def log_message(self, *a):
        pass
