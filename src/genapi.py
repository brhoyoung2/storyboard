# -*- coding: utf-8 -*-
"""
생성기 공용 로직 — Vercel 서버리스(api/*.py)와 로컬 server.py가 함께 사용.

- gen(text, gray)  : 글콘티 → 패널별 SVG 배열(+ 전체 strip). 패널 카드·웹툰 스크롤용.
- panel(req)       : 단일 패널 dict(+오버라이드: shot/pose/emotion/view, seed) → 재렌더.
                     '패널별 리롤(seed 변경)·편집(드롭다운)'에 사용.
"""
from collections import Counter

import classify_panels as C
import svg_render as R


def _fields(p):
    ax = p["axes"]
    return {
        "shot": ax["A_shot"],
        "pose": ax.get("F_pose", "stand"),
        "emotion": (ax.get("C_emotion") or ["neutral"])[0],
        "view": ax.get("G_view", "front"),
        "desc": p.get("description", "") or "",
        "num": p.get("num"),
    }


def gen(text, gray=True):
    R.GRAY = bool(gray)
    panels = C.panels_from_text(text or "")
    if not panels:
        raise ValueError("패널을 못 찾음. 형식: `번호. [샷] 묘사 / 화자: \"대사\"` 또는 줄글을 그대로 붙여넣어도 됩니다.")
    out = []
    for p in panels:
        svg, h = R.build_panel_svg(p)
        out.append({**_fields(p), "svg": svg, "h": h, "panel": p})
    strip, _ = R.build_strip_svg(panels)
    shots = dict(Counter(p["axes"]["A_shot"] for p in panels).most_common())
    return {"panels": out, "count": len(panels), "shots": shots, "strip": strip}


def panel(req):
    p = req.get("panel")
    if not isinstance(p, dict) or "axes" not in p:
        raise ValueError("panel 데이터가 없습니다.")
    R.GRAY = bool(req.get("gray", True))
    ax = p["axes"]
    if req.get("shot"):
        ax["A_shot"] = req["shot"]
    if req.get("pose"):
        ax["F_pose"] = req["pose"]
    if req.get("emotion"):
        ax["C_emotion"] = [req["emotion"]]
    if req.get("view"):
        ax["G_view"] = req["view"]
    try:
        seed = int(req.get("seed", 5))
    except (TypeError, ValueError):
        seed = 5
    svg, h = R.build_panel_svg(p, seed=seed)
    return {**_fields(p), "svg": svg, "h": h, "panel": p, "seed": seed}
