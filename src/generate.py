# -*- coding: utf-8 -*-
"""
단일 진입점: 글콘티 1편 → 그림콘티 1장(세로 스트립 SVG)

사용법:
    python src/generate.py <콘티.txt | 콘티.pdf> [-o 출력.svg] [--title 이름] [--json]

입력:
    - .txt  : 글콘티 원문 (형식: `번호. [샷] 상황묘사 / 화자: "대사"`)
    - .pdf  : 글콘티 PDF (텍스트 추출 후 동일 처리)
출력:
    - output/<이름>.svg  (그 편 전체 컷이 세로로 쌓인 1개 SVG)
    - (--json) output/<이름>.panels.json  (분류 결과)

생성 후 엄격 XML 파서로 자가검증한다(브라우저 <object> 호환 보장).
"""
import argparse
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import classify_panels as C
import svg_render as R

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "output"


def read_conti(path: Path) -> str:
    """입력 파일 → 글콘티 원문 텍스트. PDF면 추출."""
    if path.suffix.lower() == ".pdf":
        import fitz
        doc = fitz.open(path)
        txt = "\n".join(page.get_text() for page in doc)
        doc.close()
        if not txt.strip():
            raise SystemExit(f"[오류] PDF에서 텍스트를 못 찾음(이미지 PDF?): {path.name}")
        return txt
    return path.read_text(encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="글콘티 → 그림콘티 SVG (단일 진입점)")
    ap.add_argument("input", help="글콘티 .txt 또는 .pdf 경로")
    ap.add_argument("-o", "--out", help="출력 SVG 경로 (기본 output/<이름>.svg)")
    ap.add_argument("--title", help="제목(미지정 시 파일명)")
    ap.add_argument("--json", action="store_true", help="분류 결과 JSON도 저장")
    args = ap.parse_args()

    src = Path(args.input)
    if not src.exists():
        raise SystemExit(f"[오류] 입력 파일 없음: {src}")
    title = args.title or src.stem
    out = Path(args.out) if args.out else OUT_DIR / f"{title}.svg"
    out.parent.mkdir(parents=True, exist_ok=True)

    # 1) 글콘티 → 패널 분류 (6축 + 장소상속)
    raw = read_conti(src)
    panels = C.panels_from_text(raw)
    if not panels:
        raise SystemExit("[오류] 패널을 못 찾음. 글콘티 형식 확인: `번호. [샷] 묘사 / 화자: \"대사\"`")

    # 2) 렌더 → 세로 스트립 SVG 1장
    height = R.render_strip(panels, out)

    # 3) 자가검증 (브라우저 <object> 호환: 엄격 XML)
    try:
        ET.parse(out)
        xml_ok = "OK"
    except ET.ParseError as e:
        xml_ok = f"XML 오류! {e}"

    # 4) JSON(선택)
    if args.json:
        import json
        jp = out.with_suffix(".panels.json")
        jp.write_text(json.dumps({"title": title, "panel_count": len(panels),
                                  "panels": panels}, ensure_ascii=False, indent=2),
                      encoding="utf-8")

    # 요약
    shots = Counter(p["axes"]["A_shot"] for p in panels)
    poses = Counter(p["axes"]["F_pose"] for p in panels)
    print(f"✅ {src.name} → {out}")
    print(f"   패널 {len(panels)}컷 · 높이 {height}px · XML {xml_ok}")
    print(f"   샷: {dict(shots.most_common())}")
    top_pose = {k: v for k, v in poses.most_common() if k != 'stand'}
    print(f"   주요 포즈: {dict(list(top_pose.items())[:6]) or '(대부분 stand)'}")
    print(f"   브라우저로 열기: file:///{out.resolve().as_posix()}")


if __name__ == "__main__":
    main()
