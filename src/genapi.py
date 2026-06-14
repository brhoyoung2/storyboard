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


_SHOT_KO = {"closeup": "클로즈업", "extreme_closeup": "클로즈업", "medium": "미들샷",
            "full": "풀샷", "long": "롱샷", "insert": "인서트", "unspecified": "미들샷"}


def fmt(text):
    """자연글(줄글) → 글콘티 형식 텍스트로 정리. 분류기를 그대로 써서 샷·대사·나레이션을 표준 형식으로 재출력."""
    panels = C.panels_from_text(text or "")
    if not panels:
        raise ValueError("문장을 찾지 못했습니다. 줄글을 입력해 주세요.")
    lines = []
    for i, p in enumerate(panels, 1):
        shot = _SHOT_KO.get(p["axes"]["A_shot"], "미들샷")
        desc = (p.get("description") or "").strip()
        segs = [f"[{shot}] {desc}" if desc else f"[{shot}]"]
        for d in p.get("dialogue", []):
            sp = (d.get("speaker") or "화자").strip()
            segs.append(f'{sp}: "{d["text"].strip().strip(chr(34)+chr(8220)+chr(8221))}"')
        for d in p.get("inner", []):
            sp = (d.get("speaker") or "화자").strip()
            segs.append(f"{sp}: (속마음) '{d['text'].strip().strip(chr(39)+chr(8216)+chr(8217))}'")
        for n in p.get("narration", []):
            segs.append(f"나레이션: {n.strip()}")
        for fx in p.get("sfx", []):
            segs.append(f"효과음: '{fx.strip()}'")
        lines.append(f"{i}. " + " / ".join(segs))
    return {"text": "\n".join(lines), "count": len(panels)}


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
