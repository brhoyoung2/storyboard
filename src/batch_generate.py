# -*- coding: utf-8 -*-
"""
전체 20화 일괄 생성 + 원본 그림콘티 참조 렌더 (정성 비교용)

A. data/classified/*_EP*.json  → output/strips/<stem>.svg  (전체 패널)
B. 원본 "<제목> N화 그림콘티.pdf" → output/refs/<stem>.png  (저해상 썸네일)
C. output/_compare.json (스트립/참조 경로 + 패널수 메타)
"""
import json
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF

sys.path.insert(0, str(Path(__file__).resolve().parent))
import svg_render as R

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
CLS_DIR = ROOT / "data" / "classified"
STRIP_DIR = ROOT / "output" / "strips"
REF_DIR = ROOT / "output" / "refs"


def stem_to_pdf(stem: str):
    """풀하우스_EP01 → '풀하우스 1화 그림콘티.pdf' 경로."""
    m = re.match(r"(.+)_EP(\d+)$", stem)
    if not m:
        return None
    title = m.group(1).replace("_", " ")
    ep = int(m.group(2))
    return ROOT / f"{title} {ep}화 그림콘티.pdf"


def render_ref(pdf_path: Path, out_png: Path, max_h=2400):
    """원본 그림콘티에서 대표 페이지 상단을 저해상 썸네일로."""
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        return None
    # 표지(0페이지)는 건너뛰고 내용 페이지 선택
    pidx = 1 if doc.page_count > 1 else 0
    page = doc[pidx]
    rect = page.rect
    # 상단 일부만(세로 웹툰이라 매우 길다)
    clip_h = min(rect.height, rect.width * 4)
    clip = fitz.Rect(0, 0, rect.width, clip_h)
    scale = min(1.0, max_h / clip_h)
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip)
    pix.save(out_png)
    doc.close()
    return dict(page=pidx, w=pix.width, h=pix.height,
                src_w=round(rect.width), src_h=round(rect.height),
                pages=doc.page_count if False else None)


def main():
    STRIP_DIR.mkdir(parents=True, exist_ok=True)
    REF_DIR.mkdir(parents=True, exist_ok=True)
    jsons = sorted(CLS_DIR.glob("*_EP*.json"))

    meta = []
    print(f"=== 20화 일괄 생성 ===")
    for jf in jsons:
        stem = jf.stem
        data = json.load(open(jf, encoding="utf-8"))
        panels = data["panels"]
        # A. SVG 스트립 (전체)
        svg_path = STRIP_DIR / f"{stem}.svg"
        height = R.render_strip(panels, svg_path)
        # B. 원본 참조 썸네일
        pdf = stem_to_pdf(stem)
        ref_png = REF_DIR / f"{stem}.png"
        ref_info = None
        if pdf and pdf.exists():
            doc = fitz.open(pdf)
            src_pages = doc.page_count
            doc.close()
            ref_info = render_ref(pdf, ref_png)
            if ref_info:
                ref_info["src_pages"] = src_pages
        meta.append(dict(
            stem=stem, title=data.get("file", stem),
            panels=len(panels), svg=f"strips/{stem}.svg",
            svg_h=height,
            ref=f"refs/{stem}.png" if ref_info else None,
            ref_pages=ref_info.get("src_pages") if ref_info else None,
        ))
        print(f"  {stem:22s} 패널 {len(panels):3d} | SVG {height:5d}px"
              f" | 원본 {meta[-1]['ref_pages'] or '-'}p")

    (ROOT / "output" / "_compare.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    tot = sum(m["panels"] for m in meta)
    print(f"\n총 {len(meta)}화 / {tot} 패널 생성. output/strips/, output/refs/")


if __name__ == "__main__":
    main()
