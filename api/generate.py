# -*- coding: utf-8 -*-
"""
Vercel Python 서버리스 함수: POST /api/generate
{text, gray} → 그림콘티 SVG 생성 → {svg, panels, shots}

분류기/렌더러(src/)는 순수 표준 라이브러리라 외부 의존성 없음.
"""
import json
import os
import sys
from collections import Counter
from http.server import BaseHTTPRequestHandler

# src/ 모듈 import 경로 확보 (Vercel includeFiles로 번들됨)
_HERE = os.path.dirname(os.path.abspath(__file__))
for _cand in (os.path.join(_HERE, "..", "src"), os.path.join(_HERE, "src"), _HERE):
    if os.path.exists(os.path.join(_cand, "svg_render.py")):
        sys.path.insert(0, _cand)
        break

import classify_panels as C
import svg_render as R


def _make_svg(text, gray):
    R.GRAY = bool(gray)
    panels = C.panels_from_text(text or "")
    if not panels:
        raise ValueError("패널을 못 찾음. 형식: `번호. [샷] 묘사 / 화자: \"대사\"`")
    svg, _ = R.build_strip_svg(panels)
    shots = dict(Counter(p["axes"]["A_shot"] for p in panels).most_common())
    return {"svg": svg, "panels": len(panels), "shots": shots}


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
            self._json(_make_svg(req.get("text", ""), req.get("gray", True)))
        except Exception as e:
            self._json({"error": str(e)})

    def do_GET(self):
        self._json({"ok": True, "hint": "POST {text, gray} 로 호출하세요."})

    def log_message(self, *a):
        pass
