# -*- coding: utf-8 -*-
"""
브라우저 뷰어 생성 (output/viewer.html)

생성된 SVG 콘티를 인라인 임베드 → 손그림 rough 필터(feTurbulence)와
손글씨 웹폰트(Nanum Pen Script)가 실제로 적용된 모습을 확인.
PNG 프리뷰로는 둘 다 안 보였던 부분.

추가: 에피소드 스트립 옆에 원본 글콘티(분류 결과) 텍스트를 나란히 → 입출력 검증.
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# 첫 진입 예시(입력칸 프리필 + 베이크된 결과 미리보기)
SAMPLE_TEXT = """1. [풀샷] 카페 앞 거리. 매리가 걸어간다.
2. [미들샷] 매리가 환하게 웃는다. / 매리: "오늘 날씨 좋다!"
3. [클로즈업] 매리가 생각에 잠긴다. / 매리: (속마음) '뭐 먹지?'
4. [미들샷] 무결이 손을 흔들며 인사한다. / 무결: "매리야!"
5. [미들샷] 매리와 무결이 서로 마주본다. / 매리: "어, 무결아!"
6. [풀샷] 둘이 나란히 걷는다.
7. [클로즈업] 매리가 깜짝 놀란다. / 매리: "헉, 저게 뭐야?!" / 효과음: '두근'
8. [롱샷] 거리에 사람들이 모여있다."""


def _bake_sample():
    """SAMPLE_TEXT를 렌더해 첫 진입용 패널 카드 묶음(HTML)을 만든다. 실패해도 빈 문자열."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import genapi as _G
        r = _G.gen(SAMPLE_TEXT, gray=True)
        return "".join(f'<div class="gcard">{p["svg"]}</div>' for p in r["panels"])
    except Exception as e:
        print(f"  (샘플 베이크 생략: {e})")
        return ""

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "output"
CLS_DIR = ROOT / "data" / "classified"


def inline_svg(path: Path, uid: str) -> str:
    """파일 충돌 방지를 위해 filter id를 파일별로 네임스페이스."""
    svg = path.read_text(encoding="utf-8")
    svg = svg.replace('id="rough"', f'id="rough_{uid}"')
    svg = svg.replace("url(#rough)", f"url(#rough_{uid})")
    return svg


def source_panels_html(stem: str, limit: int):
    """stem(예: 풀하우스_EP01)의 분류 결과 → 패널 텍스트 카드."""
    f = CLS_DIR / f"{stem}.json"
    if not f.exists():
        return ""
    data = json.load(open(f, encoding="utf-8"))
    rows = []
    for p in data["panels"][:limit]:
        ax = p["axes"]
        tags = " · ".join([ax["A_shot"], ax.get("F_pose", "stand"),
                           ax["C_emotion"][0]])
        dlg = " ".join(d["text"] for d in p.get("dialogue", []))
        inner = " ".join(f"({d['text']})" for d in p.get("inner", []))
        sfx = " ".join(p.get("sfx", []))
        rows.append(
            f'<div class="pcard"><div class="pnum">{p["num"]}</div>'
            f'<div class="pbody"><div class="ptags">{tags}</div>'
            f'<div class="pdesc">{esc(p.get("description",""))}</div>'
            f'{f"<div class=pdlg>{esc(dlg)}</div>" if dlg else ""}'
            f'{f"<div class=pinner>{esc(inner)}</div>" if inner else ""}'
            f'{f"<div class=psfx>{esc(sfx)}</div>" if sfx else ""}'
            f'</div></div>')
    return "".join(rows)


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


HEAD = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Storyboard · 뷰어</title>
<link rel="icon" type="image/svg+xml" href="favicon.svg">
<link rel="apple-touch-icon" href="favicon.svg">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=Nanum+Pen+Script&display=swap');
:root{--bg:#0b0d13;--card:#151823;--card2:#1c2030;--line:#262b3b;--tx:#eaecf3;
  --mut:#9aa3b6;--dim:#6b7488;--grad:linear-gradient(135deg,#6366f1,#a855f7 55%,#ec4899)}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);font-family:'Pretendard',system-ui,sans-serif;-webkit-font-smoothing:antialiased}
body::before{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;
  background:radial-gradient(700px 360px at 85% -8%,rgba(99,102,241,.16),transparent 60%),
    radial-gradient(600px 340px at 5% 4%,rgba(168,85,247,.12),transparent 60%)}
a{color:inherit;text-decoration:none}
/* nav header */
header{position:sticky;top:0;z-index:50;backdrop-filter:blur(12px);
  background:rgba(11,13,19,.78);border-bottom:1px solid var(--line);padding:0 26px}
.nav{display:flex;align-items:center;justify-content:space-between;height:60px}
.logo{font-size:19px;font-weight:800;display:flex;align-items:center;gap:9px;letter-spacing:-.01em}
.logo .dot{width:9px;height:9px;border-radius:50%;background:var(--grad)}
.logo b{background:linear-gradient(90deg,#fff,#cbc4ff);-webkit-background-clip:text;background-clip:text;color:transparent}
.nav-r{display:flex;align-items:center;gap:18px;font-size:14px;color:var(--mut)}
.nav-r a:hover{color:var(--tx)}
.navbtn{background:var(--grad);color:#fff!important;font-weight:700;padding:9px 18px;border-radius:11px;
  cursor:pointer;box-shadow:0 6px 18px rgba(124,58,237,.4);transition:.15s}
.navbtn:hover{transform:translateY(-1px)}
.tabs{display:flex;gap:8px;padding:11px 0 13px;flex-wrap:wrap}
.tab{padding:8px 16px;background:var(--card2);border-radius:11px;cursor:pointer;font-size:14.5px;
  font-weight:600;border:1px solid var(--line);color:var(--mut);transition:.15s}
.tab:hover{color:var(--tx);border-color:#3a415a}
.tab.on{background:var(--grad);border-color:transparent;color:#fff;box-shadow:0 6px 18px rgba(124,58,237,.4)}
.tab.gen{color:#d9caff;border-color:rgba(124,58,237,.4)}
.tab.gen.on{color:#fff}
.view{display:none;padding:30px 26px}
.view.on{display:block;animation:fade .25s ease}
@keyframes fade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.gallery{display:flex;flex-wrap:wrap;gap:28px;justify-content:center}
.paper{background:#fff;border-radius:12px;box-shadow:0 14px 44px rgba(0,0,0,.5);overflow:hidden}
.paper svg{display:block;width:360px;height:auto}
.cap{text-align:center;color:var(--mut);font-size:14px;margin-top:10px;font-weight:600}
.split{display:flex;gap:24px;align-items:flex-start;justify-content:center}
.txtcol{width:380px;max-height:84vh;overflow:auto}
.pcard{display:flex;gap:11px;background:var(--card);border-radius:12px;padding:12px 14px;
  margin-bottom:9px;border:1px solid var(--line)}
.pnum{flex:0 0 28px;height:28px;border-radius:9px;background:var(--grad);
  color:#fff;text-align:center;line-height:28px;font-size:14px;font-weight:700}
.ptags{color:#b39dff;font-size:12.5px;letter-spacing:.3px;font-weight:600}
.pdesc{font-size:15px;margin-top:3px}
.pdlg{color:#fff;background:#33384a;display:inline-block;padding:2px 9px;border-radius:9px;margin-top:5px;font-size:14px}
.pinner{color:var(--mut);font-style:italic;font-size:13.5px;margin-top:3px}
.psfx{color:#86c5e6;font-size:13.5px;margin-top:3px}
.note{max-width:820px;margin:0 auto 24px;background:var(--card);padding:15px 20px;
  border-radius:14px;border:1px solid var(--line);border-left:4px solid #a855f7;font-size:15px;line-height:1.6;color:var(--mut)}
.note b{color:var(--tx)}
/* 비교 탭 */
.cmpbar{display:flex;gap:12px;align-items:center;justify-content:center;margin-bottom:20px;flex-wrap:wrap;font-size:15px;color:var(--mut)}
.cmpbar select{font-family:inherit;font-size:15px;padding:9px 14px;border-radius:11px;
  background:var(--card2);color:var(--tx);border:1px solid var(--line)}
.cmpwrap{display:flex;gap:28px;justify-content:center;align-items:flex-start}
.cmpcol{text-align:center}
.cmphead{font-size:15px;color:var(--tx);margin-bottom:10px;font-weight:700}
.cmpcol .paper{width:340px;height:80vh;overflow-y:auto}
.cmpcol object,.cmpcol img{display:block;width:340px;height:auto}
.cmpcol img{filter:grayscale(1)}
.cmpmeta{color:var(--dim);font-size:13px;margin-top:9px}
#v3 .paper svg{width:540px}
#v3 .gallery{gap:36px;align-items:flex-start}
#v4 .paper svg{width:600px}
#v5 .paper svg{width:600px}
#v7 .paper svg{width:660px}
/* 직접 생성 탭 — 좌:입력(고정) / 우:결과(웹툰 스크롤), 1:1 동일폭, 하단 생성바 */
#v6.view{padding-bottom:96px}            /* 하단 고정바에 가리지 않게 */
.genwrap{display:flex;gap:22px;align-items:flex-start;max-width:1180px;margin:0 auto}
.genleft{flex:1 1 0;min-width:0;position:sticky;top:118px;align-self:flex-start;display:flex;flex-direction:column}
.genright{flex:1 1 0;min-width:0}
.genleft textarea{width:100%;height:calc(100vh - 320px);min-height:300px;resize:none;background:#0e1118;color:var(--tx);
  border:1px solid var(--line);border-radius:14px;padding:16px 18px;
  font-family:ui-monospace,'Pretendard',monospace;font-size:14.5px;line-height:1.8;outline:none;transition:.15s}
.genleft textarea:focus{border-color:#7c5cff;box-shadow:0 0 0 4px rgba(124,58,237,.18)}
.genhint{font-size:13px;color:var(--dim);margin:10px 0 0;line-height:1.6}
.genhint code{background:var(--card2);padding:2px 7px;border-radius:6px;color:#bcd}
/* 하단 생성 바 (탭 진입 시에만 표시) */
.genbottom{display:none;position:fixed;left:0;right:0;bottom:0;z-index:60;
  padding:13px 26px;gap:12px;align-items:center;justify-content:center;flex-wrap:wrap;
  background:rgba(13,16,24,.82);backdrop-filter:blur(14px);border-top:1px solid var(--line)}
.genbottom button{font-family:inherit;font-size:15px;font-weight:700;padding:12px 20px;border-radius:12px;
  cursor:pointer;border:1px solid var(--line);background:var(--card2);color:var(--tx);transition:.15s}
.genbottom button:hover{border-color:#3a415a}
.genbottom button.primary{background:var(--grad);border-color:transparent;color:#fff;padding:12px 34px;font-size:16px;
  box-shadow:0 8px 22px rgba(124,58,237,.4)}
.genbottom button.primary:hover{transform:translateY(-1px)}
.genbottom button:disabled{opacity:.45;cursor:default;transform:none}
.gchk{display:flex;align-items:center;gap:7px;font-size:14px;color:var(--mut)}
.gstat{font-size:14px;color:var(--mut);min-width:120px;text-align:left}
.gresult{overflow:visible;min-height:calc(100vh - 320px)}
.gresult > svg{display:block;width:100%;height:auto}
.gph{color:#667;text-align:center;padding:90px 24px;font-size:16px;line-height:1.7;background:#fff;border-radius:14px}
.gph code{background:#eef;padding:2px 7px;border-radius:6px;color:#5b3fd6}
.spin{width:42px;height:42px;margin:0 auto 16px;border:5px solid #e6e2ff;
  border-top-color:#7c5cff;border-radius:50%;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
/* 입력 보조: 샷 칩 + 실시간 파싱 프리뷰 */
.chips{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 9px}
.chips .chip{font-size:12.5px;font-weight:600;padding:6px 11px;border-radius:9px;cursor:pointer;
  border:1px solid var(--line);background:var(--card2);color:#cdd;transition:.12s;user-select:none}
.chips .chip:hover{border-color:#7c5cff;color:#fff;background:rgba(124,58,237,.18)}
.chips .chip.alt{color:#9fb3c8}
.gpreview{display:flex;gap:7px;flex-wrap:wrap;align-items:center;margin:11px 0 0;min-height:24px;font-size:12.5px}
.gpreview .pv{padding:4px 10px;border-radius:999px;background:rgba(124,58,237,.14);
  border:1px solid rgba(124,58,237,.32);color:#d9caff;font-weight:600}
.gpreview .pv.muted{background:var(--card2);border-color:var(--line);color:var(--mut);font-weight:500}
/* 웹툰형 단일 캔버스 — 흰 바탕 위에 컷이 이어서 올라감(여백·그림자·카드테두리 없음) */
.pstack{display:flex;flex-direction:column;gap:160px;background:#fff;border-radius:14px;
  padding:16px;box-shadow:0 10px 36px rgba(0,0,0,.4)}
.gcard{display:flex;flex-direction:column;background:#fff;position:relative;border-radius:6px;overflow:hidden}
.gcard.busy{opacity:.5}
.gcard svg{display:block;width:100%;height:auto}
/* 컨트롤바: 평소엔 숨김 → 컷에 마우스 올리면 그림 위에 떠오름(캔버스 연속성 유지) */
.gcard-bar{position:absolute;left:0;right:0;bottom:0;display:flex;gap:7px;align-items:center;flex-wrap:wrap;
  padding:10px 12px;background:rgba(13,16,24,.86);backdrop-filter:blur(8px);
  opacity:0;transform:translateY(8px);transition:.16s;pointer-events:none}
.gcard:hover .gcard-bar{opacity:1;transform:none;pointer-events:auto}
.gcard-bar .pn{font-size:13px;font-weight:800;color:#aeb6cc;margin-right:2px}
.gcard-bar select{font-family:inherit;font-size:13px;padding:6px 9px;border-radius:8px;
  background:var(--card2);color:var(--tx);border:1px solid var(--line);cursor:pointer;outline:none}
.gcard-bar select:hover{border-color:#3a415a}
.gcard-bar .iconbtn{font-size:13px;font-weight:700;padding:7px 12px;border-radius:8px;cursor:pointer;
  border:1px solid var(--line);background:var(--card2);color:var(--tx);transition:.12s}
.gcard-bar .iconbtn:hover{border-color:#7c5cff;color:#fff}
.gcard-bar .sp{flex:1}
/* 컷 번호 배지(좌상단, 항상 표시) */
.gcard-mini{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
  background:rgba(255,255,255,.55)}
/* 첫 진입 예시 배너 */
.gsample-banner{display:flex;align-items:center;gap:10px;margin:0 0 14px;padding:12px 16px;border-radius:12px;
  background:rgba(124,58,237,.12);border:1px solid rgba(124,58,237,.3);color:#d9caff;
  font-size:13.5px;line-height:1.55;word-break:keep-all}
.gsample-banner .ic{flex:0 0 auto;font-size:17px}
.gsample-banner span{flex:1 1 auto}
.gsample-banner b{color:#fff}
.exp-sep{width:1px;height:24px;background:var(--line);margin:0 2px}
</style></head><body>"""


def main():
    samples = OUT_DIR / "_type_samples.svg"
    strip = OUT_DIR / "풀하우스_EP01_strip.svg"

    cmp_path = OUT_DIR / "_compare.json"
    compare = json.load(open(cmp_path, encoding="utf-8")) if cmp_path.exists() else []

    html = [HEAD]
    html.append('<header>'
                '<div class="nav">'
                '<a class="logo" href="index.html"><span class="dot"></span><b>AI Storyboard</b></a>'
                '<div class="nav-r">'
                '<a href="index.html">← 홈</a>'
                '<a href="https://github.com/brhoyoung2/storyboard" target="_blank">GitHub</a>'
                '<a class="navbtn" onclick="show(6)">✎ 직접 생성</a>'
                '</div></div>'
                '<div class="tabs">'
                '<div class="tab on" onclick="show(0)">유형/포즈 샘플</div>'
                '<div class="tab" onclick="show(1)">풀하우스 EP01</div>'
                '<div class="tab" onclick="show(2)">20화 ↔ 원본 비교</div>'
                '<div class="tab" onclick="show(3)">캐릭터 시트</div>'
                '<div class="tab" onclick="show(4)">바디/포즈</div>'
                '<div class="tab" onclick="show(5)">시점/각도</div>'
                '<div class="tab gen" onclick="show(6)">✎ 직접 생성</div>'
                '<div class="tab" onclick="show(7)">소품</div>'
                '</div></header>')

    # View 0: 샘플 시트
    html.append('<div class="view on" id="v0">')
    html.append('<div class="note">아래 그림은 분류기가 뽑은 <b>배치 값</b>(샷·포즈·표정·말풍선)을 '
                '결정론적 렌더러가 SVG로 그린 것입니다. 선이 미세하게 떨리는 건 '
                '<b>feTurbulence 연필 필터</b>, 글씨체는 <b>Nanum Pen Script</b>입니다.</div>')
    if samples.exists():
        html.append(f'<div class="gallery"><div><div class="paper">{inline_svg(samples,"s")}</div>'
                    f'<div class="cap">상위 유형 · 포즈 샘플 시트</div></div></div>')
    html.append('</div>')

    # View 1: 에피소드 입력↔출력
    html.append('<div class="view" id="v1">')
    html.append('<div class="note">왼쪽은 원본 글콘티(분류 결과), 오른쪽은 생성된 그림콘티 스트립. '
                '같은 1~12컷입니다.</div>')
    html.append('<div class="split">')
    html.append(f'<div class="txtcol">{source_panels_html("풀하우스_EP01", 12)}</div>')
    if strip.exists():
        html.append(f'<div class="paper">{inline_svg(strip,"e")}</div>')
    html.append('</div></div>')

    # View 2: 20화 ↔ 원본 비교 (object/img 참조 → HTML 가볍게)
    html.append('<div class="view" id="v2">')
    html.append('<div class="note">왼쪽은 <b>원본 작가 그림콘티</b>(PDF 상단), 오른쪽은 <b>우리가 생성</b>한 SVG 스트립. '
                '드롭다운으로 20화 전환. 둘 다 세로 웹툰 스크롤이라 길이는 다르지만 '
                '컷 구성·샷·배치를 비교하세요.</div>')
    opts = "".join(
        f'<option value="{m["stem"]}">{m["stem"]}  (우리 {m["panels"]}컷 / 원본 {m["ref_pages"] or "?"}p)</option>'
        for m in compare)
    first = compare[0] if compare else None
    init_ref = quote(first["ref"]) if first and first.get("ref") else ""
    init_svg = quote(first["svg"]) if first else ""
    init_rmeta = f'원본 PDF {first.get("ref_pages") or "?"}쪽 중 상단' if first else ""
    init_gmeta = f'생성 {first["panels"]}컷 · 높이 {first["svg_h"]}px' if first else ""
    html.append(f'<div class="cmpbar"><span>에피소드:</span><select id="epsel" onchange="loadEp()">{opts}</select></div>')
    html.append('<div class="cmpwrap">'
                '<div class="cmpcol"><div class="cmphead">원본 작가 그림콘티</div>'
                f'<div class="paper"><img id="refimg" src="{init_ref}"></div>'
                f'<div class="cmpmeta" id="refmeta">{init_rmeta}</div></div>'
                '<div class="cmpcol"><div class="cmphead">생성된 SVG 콘티</div>'
                f'<div class="paper"><object id="genobj" type="image/svg+xml" data="{init_svg}"></object></div>'
                f'<div class="cmpmeta" id="genmeta">{init_gmeta}</div></div>'
                '</div></div>')

    # View 3: 캐릭터 시트 (외형 검토)
    csheet = OUT_DIR / "_character_sheet.svg"
    html.append('<div class="view" id="v3">')
    html.append('<div class="note">v2 캐릭터: 턱선·웹툰 눈·눈썹·코 + 캐릭터별 헤어/의상/안경. '
                '행=인물, 열=표정. 손그림 필터·손글씨 폰트 적용.</div>')
    esheet = OUT_DIR / "_expr_sheet.svg"
    gal = []
    if esheet.exists():
        gal.append(f'<div><div class="cap">표정 22종 (매리)</div><div class="paper" style="width:560px">{inline_svg(esheet,"es")}</div></div>')
    if csheet.exists():
        gal.append(f'<div><div class="cap">캐릭터 9인 × 표정</div><div class="paper" style="width:560px">{inline_svg(csheet,"cs")}</div></div>')
    html.append(f'<div class="gallery">{"".join(gal)}</div>')
    html.append('</div>')

    # View 4: 바디/포즈 시트
    psheet = OUT_DIR / "_pose_sheet.svg"
    html.append('<div class="view" id="v4">')
    html.append('<div class="note">v3 관절 바디 리그: 목·어깨·팔·손·골반·허벅지·종아리·발을 '
                '각 세그먼트로. 포즈 = 관절 각도. (반측면/완측면 각도는 다음 단계)</div>')
    if psheet.exists():
        html.append(f'<div class="gallery"><div class="paper" style="width:620px">{inline_svg(psheet,"ps")}</div></div>')
    html.append('</div>')

    # View 5: 시점/각도 시트
    asheet = OUT_DIR / "_angle_sheet.svg"
    html.append('<div class="view" id="v5">')
    html.append('<div class="note">시점 각도: 정면 · 반측면(3/4) · 완측면(profile). '
                '투샷은 자동으로 서로 마주보는 3/4뷰, 묘사에 "옆모습/측면"이 있으면 완측면.</div>')
    if asheet.exists():
        html.append(f'<div class="gallery"><div class="paper" style="width:620px">{inline_svg(asheet,"as")}</div></div>')
    html.append('</div>')

    # View 6: 직접 생성 (서버 /generate 호출)
    html.append('<div class="view" id="v6">')
    html.append('<div class="note">글콘티를 직접 쓰거나 붙여넣고 <b>[✎ 생성]</b>을 누르면 '
                '오른쪽에 그림콘티가 즉시 만들어집니다. '
                '<span style="color:#7a8398">· 내 PC에서 직접 띄울 땐 <code>서버실행.bat</code></span></div>')
    html.append(
        '<div class="genwrap">'
        '<div class="genleft">'
        '<div class="chips" id="gchips">'
        '<span class="chip" data-ins="[풀샷] ">풀샷</span>'
        '<span class="chip" data-ins="[미들샷] ">미들샷</span>'
        '<span class="chip" data-ins="[클로즈업] ">클로즈업</span>'
        '<span class="chip" data-ins="[롱샷] ">롱샷</span>'
        '<span class="chip alt" data-ins=" / 매리: &quot;&quot;">대사</span>'
        '<span class="chip alt" data-ins=" / 효과음: \'\'">효과음</span>'
        '<span class="chip alt" data-ins=" / 나레이션: ">나레이션</span>'
        '</div>'
        '<textarea id="ginp" placeholder="여기에 글콘티 입력 (줄글을 그대로 붙여넣어도 됩니다)...&#10;예) 1. [미들샷] 매리가 웃는다. / 매리: &quot;안녕!&quot;"></textarea>'
        '<div class="gpreview" id="gpreview"></div>'
        '<div class="genhint">형식: <code>번호. [샷] 상황묘사 / 화자: "대사"</code> · '
        '인물 이름(매리·무결·엘리·라이더·정인 등)으로 색/성별 반영 · "둘/서로"=2명, "사람들"=다인물 · Ctrl+Enter로 생성</div>'
        '</div>'
        '<div class="genright"><div class="gresult" id="gout"><div class="gph">생성 결과가 여기에 표시됩니다</div></div></div>'
        '</div></div>')

    # View 7: 소품 에셋
    psheet = OUT_DIR / "_prop_sheet.svg"
    html.append('<div class="view" id="v7">')
    html.append('<div class="note">묘사에 소품이 나오면 자동 배치됩니다 — '
                '<b>"밥을 먹는다"</b> → 밥+숟가락+책상+의자(앉은 자세) · <b>"노트북/책"</b> → 책상 위에 · '
                '<b>"소파·침대"</b> 등. 아래는 기본 소품 에셋입니다.</div>')
    if psheet.exists():
        html.append(f'<div class="gallery"><div class="paper" style="width:680px">{inline_svg(psheet,"prop")}</div></div>')
    html.append('</div>')

    # 하단 고정 생성 바 (생성 탭에서만 표시)
    html.append(
        '<div class="genbottom" id="genbottom">'
        '<button class="primary" id="ggen">✎ 생성</button>'
        '<button id="gsample">샘플 불러오기</button>'
        '<span class="gchk"><input type="checkbox" id="ggray" checked> 흑백</span>'
        '<span class="exp-sep"></span>'
        '<button id="gpng" disabled>⬇ PNG</button>'
        '<button id="gpdf" disabled>⬇ PDF</button>'
        '<button id="gcopy" disabled>⧉ 복사</button>'
        '<button id="gdl" disabled>SVG</button>'
        '<span class="gstat" id="gstat"></span>'
        '</div>')

    data_js = json.dumps({m["stem"]: m for m in compare}, ensure_ascii=False)
    sample_svg_js = '""'                       # 생성 탭은 빈 상태로 시작(샘플 미삽입)
    sample_txt_js = json.dumps(SAMPLE_TEXT, ensure_ascii=False)   # '샘플 불러오기' 버튼용으로만 유지
    html.append(r"""<script>
const CMP = __CMP__;
function show(i){
  document.querySelectorAll('.view').forEach((v,j)=>v.classList.toggle('on',i===j));
  document.querySelectorAll('.tab').forEach((t,j)=>t.classList.toggle('on',i===j));
  document.getElementById('genbottom').style.display = (i===6)?'flex':'none';
  if(i===2 && !document.getElementById('genobj').data) loadEp();
  if(i===6) checkGen();
}
function checkGen(){     // 생성 탭 진입 시 서버 연결만 확인(샘플·프리필 없음 — 빈 상태로 시작)
  if(window.__gen_shown) return;
  window.__gen_shown = true;
  parsePreview();
  fetch(G_API+'/', {method:'GET'}).catch(()=>{});
}
function loadEp(){
  const stem = document.getElementById('epsel').value;
  const m = CMP[stem];
  document.getElementById('refimg').src = m.ref ? encodeURI(m.ref) : '';
  document.getElementById('genobj').data = encodeURI(m.svg);
  document.getElementById('refmeta').textContent = '원본 PDF '+(m.ref_pages||'?')+'쪽 중 상단';
  document.getElementById('genmeta').textContent = '생성 '+m.panels+'컷 · 높이 '+m.svg_h+'px';
}
// ── 직접 생성 탭 ──
const G_API = location.protocol==='file:' ? 'http://127.0.0.1:8000' : '';
const G_SAMPLE = __SAMPLE_TXT__;
const G_SAMPLE_SVG = __SAMPLE_SVG__;   // 첫 진입용 베이크된 예시 패널들
const gq = id => document.getElementById(id);
let gPanels = [];          // [{svg, shot,pose,emotion,view,panel}] — 현재 결과 상태
let gStrip = '';           // 전체 strip SVG(SVG 저장용)

// 편집 드롭다운 선택지 (label, value)
const OPT = {
  shot:    [['풀샷','full'],['미들샷','medium'],['클로즈업','closeup'],['익스트림CU','extreme_closeup'],['롱샷','long'],['인서트','insert']],
  pose:    [['서있음','stand'],['걷기','walk'],['달리기','run'],['통화','phone'],['손번쩍','raise_hand'],['인사','wave'],['팔짱','arms_cross'],['가리킴','point'],['머리긁','scratch_head'],['생각(턱)','think_chin'],['머리부여잡','hold_head'],['앉기','sit'],['포옹','hug'],['고개숙임','head_down'],['뒷모습','turn_away'],['거부','hand_no']],
  emotion: [['무표정','neutral'],['미소','smile'],['활짝','happy'],['크게웃음','laugh'],['놀람','surprise'],['진지','serious'],['황당','dumbfound'],['화남','angry'],['슬픔','sad'],['하트','love'],['윙크','wink'],['실쭉','smirk'],['지침','tired']],
  view:    [['정면','front'],['반측면','q3'],['완측면','profile']],
};
const LBL = {shot:'샷',pose:'포즈',emotion:'표정',view:'시점'};

// ── 입력 칩: 커서 위치에 삽입 ──
gq('gchips').addEventListener('click', e => {
  const c = e.target.closest('.chip'); if(!c) return;
  const t = gq('ginp'), ins = c.dataset.ins;
  const s = t.selectionStart, en = t.selectionEnd, v = t.value;
  t.value = v.slice(0,s) + ins + v.slice(en);
  const caret = s + ins.length - (ins.endsWith('""')||ins.endsWith("''") ? 1 : 0);
  t.focus(); t.setSelectionRange(caret, caret); parsePreview();
});

// ── 실시간 파싱 프리뷰 (클라이언트 추정, 서버 불필요) ──
const SHOT_WORDS = {풀샷:'풀샷',풀:'풀샷',미들:'미들',바스트:'미들',클로즈업:'클로즈업',클로즈:'클로즈업',클로즈샷:'클로즈업',롱샷:'롱샷',롱:'롱샷',인서트:'인서트'};
const KNOWN = ['매리','무결','엘리','라이더','정인','민수','지훈','수아','하늘','준영'];
function parsePreview(){
  const raw = gq('ginp').value;
  const pv = gq('gpreview'); if(!pv) return;
  if(!raw.trim()){ pv.innerHTML='<span class="pv muted">입력하면 감지 결과가 여기에 표시됩니다</span>'; return; }
  const lines = raw.split(/\n+/).map(s=>s.trim()).filter(Boolean);
  let units = lines.filter(l=>/^\s*\d+[.)\]]/.test(l));   // 번호 매겨진 줄
  if(units.length===0) units = lines;                      // 줄글: 줄 단위
  const shots = {};
  let names = new Set(), dlg = 0, sfx = 0, multi = false;
  for(const l of units){
    const sm = l.match(/\[([^\]]+)\]/);
    if(sm){ for(const k in SHOT_WORDS){ if(sm[1].includes(k)){ shots[SHOT_WORDS[k]]=(shots[SHOT_WORDS[k]]||0)+1; break; } } }
    if(/["“][^"”]+["”]/.test(l)) dlg++;
    if(/효과음/.test(l)) sfx++;
    if(/둘|서로|마주|함께|나란히/.test(l)) multi = true;
    if(/사람들|군중|모여/.test(l)) multi = true;
    for(const nm of KNOWN){ if(l.includes(nm)) names.add(nm); }
  }
  const chips = [`<span class="pv">패널 ${units.length}개</span>`];
  if(names.size) chips.push(`<span class="pv">인물 ${[...names].join('·')}</span>`);
  else if(multi) chips.push('<span class="pv">인물 여럿</span>');
  const sh = Object.entries(shots).map(([k,v])=>`${k}×${v}`).join(' · ');
  if(sh) chips.push(`<span class="pv muted">샷 ${sh}</span>`);
  if(dlg) chips.push(`<span class="pv muted">대사 ${dlg}</span>`);
  if(sfx) chips.push(`<span class="pv muted">효과음 ${sfx}</span>`);
  pv.innerHTML = chips.join('');
}
let _pvT; gq('ginp').addEventListener('input', ()=>{ clearTimeout(_pvT); _pvT=setTimeout(parsePreview,120); });

// ── 카드 렌더 ──
function optSel(field, cur, idx){
  const o = OPT[field].map(([l,v])=>`<option value="${v}"${v===cur?' selected':''}>${LBL[field]}: ${l}</option>`).join('');
  return `<select data-idx="${idx}" data-field="${field}">${o}</select>`;
}
function cardHTML(p, i){
  return `<div class="gcard" data-idx="${i}" id="gcard${i}">`
    + p.svg
    + '<div class="gcard-bar">'
    + `<span class="pn">#${i+1}</span>`
    + optSel('shot',p.shot,i)+optSel('pose',p.pose,i)+optSel('emotion',p.emotion,i)+optSel('view',p.view,i)
    + `<button class="iconbtn" data-reroll="${i}">🎲 리롤</button>`
    + '<span class="sp"></span>'
    + `<button class="iconbtn" data-png="${i}">⬇ PNG</button>`
    + '</div></div>';
}
function renderCards(){
  gq('gout').innerHTML = '<div class="pstack" id="pstack">'+gPanels.map(cardHTML).join('')+'</div>';
}

// ── 단일 패널 재요청(편집/리롤) ──
async function panelReq(i, extra){
  const p = gPanels[i];
  const card = gq('gcard'+i); card.classList.add('busy');
  card.insertAdjacentHTML('beforeend','<div class="gcard-mini"><div class="spin"></div></div>');
  try{
    const res = await fetch(G_API+'/api/panel', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(Object.assign({panel:p.panel, gray:gq('ggray').checked, seed:p.seed||5}, extra))});
    const d = await res.json();
    if(d.error){ gq('gstat').innerHTML='<span style="color:#f99">⚠ '+d.error+'</span>'; }
    else{
      gPanels[i] = {svg:d.svg, shot:d.shot, pose:d.pose, emotion:d.emotion, view:d.view, panel:d.panel, seed:d.seed};
      const nc = document.createElement('div'); nc.innerHTML = cardHTML(gPanels[i], i);
      card.replaceWith(nc.firstChild);
    }
  }catch(e){ gq('gstat').innerHTML='<span style="color:#f99">서버 연결 실패</span>'; }
}
// 이벤트 위임: 드롭다운 편집 / 리롤 / 패널 PNG
gq('gout').addEventListener('change', e=>{
  const s=e.target.closest('select'); if(!s) return;
  panelReq(+s.dataset.idx, {[s.dataset.field]: s.value});
});
gq('gout').addEventListener('click', e=>{
  const rr=e.target.closest('[data-reroll]'); if(rr){ const i=+rr.dataset.reroll;
    panelReq(i, {seed: ((gPanels[i].seed||5)%97)+7}); return; }   // 시드 회전 → 선 흔들림 다르게
  const pg=e.target.closest('[data-png]'); if(pg){ exportPNG(+pg.dataset.png); }
});

// ── 생성 ──
async function genConti(){
  const text = gq('ginp').value.trim();
  if(!text){ gq('gstat').innerHTML='<span style="color:#f99">글콘티를 입력하세요.</span>'; return; }
  gq('ggen').disabled=true; gq('gstat').textContent='생성 중...';
  gq('gout').innerHTML='<div class="gph"><div class="spin"></div>생성 중...</div>';
  try{
    const res = await fetch(G_API+'/api/generate', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({text, gray: gq('ggray').checked})});
    const d = await res.json();
    if(d.error){
      gq('gstat').innerHTML='<span style="color:#f99">오류</span>';
      gq('gout').innerHTML='<div class="gph">⚠ '+d.error+'</div>';
    } else {
      gPanels = d.panels.map(p=>({svg:p.svg,shot:p.shot,pose:p.pose,emotion:p.emotion,view:p.view,panel:p.panel,seed:5}));
      gStrip = d.strip || '';
      renderCards();
      ['gpng','gpdf','gcopy','gdl'].forEach(id=>gq(id).disabled=false);
      gq('gstat').textContent = d.count+'컷 · 샷 '+Object.entries(d.shots).map(([k,v])=>k+'×'+v).join(' ');
    }
  }catch(e){
    gq('gstat').innerHTML='<span style="color:#f99">서버 연결 실패</span>';
    gq('gout').innerHTML='<div class="gph">⚠ 생성 서버에 연결할 수 없습니다.<br><br>'
      +'터미널에서 <code>python src/server.py</code> 를 실행한 뒤,<br>'
      +'자동으로 열리는 <code>http://127.0.0.1:8000</code> 에서 다시 시도하세요.</div>';
  }
  gq('ggen').disabled=false;
}

// ── 내보내기: SVG→canvas 래스터화 ──
function svgToCanvas(svgEl, scale){
  scale = scale||2;
  return new Promise((res,rej)=>{
    const vb = svgEl.viewBox.baseVal;
    const w = (vb&&vb.width)||svgEl.width.baseVal.value||750;
    const h = (vb&&vb.height)||svgEl.height.baseVal.value||480;
    let xml = new XMLSerializer().serializeToString(svgEl);
    if(!/^<svg[^>]+xmlns=/.test(xml)) xml = xml.replace('<svg','<svg xmlns="http://www.w3.org/2000/svg"');
    const url = 'data:image/svg+xml;charset=utf-8,'+encodeURIComponent(xml);
    const img = new Image();
    img.onload=()=>{ const c=document.createElement('canvas'); c.width=Math.round(w*scale); c.height=Math.round(h*scale);
      const cx=c.getContext('2d'); cx.fillStyle='#fff'; cx.fillRect(0,0,c.width,c.height);
      cx.drawImage(img,0,0,c.width,c.height); res({canvas:c,w,h}); };
    img.onerror=rej; img.src=url;
  });
}
function dlBlob(blob, name){ const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download=name; a.click(); setTimeout(()=>URL.revokeObjectURL(a.href),3000); }

async function exportPNG(idx){   // idx 주면 그 패널만, 없으면 전체 세로 합성
  const svgs = [...gq('gout').querySelectorAll('.gcard svg')];
  if(!svgs.length) return;
  if(idx!=null){ const {canvas}=await svgToCanvas(svgs[idx],2); canvas.toBlob(b=>dlBlob(b,`conti_${idx+1}.png`)); return; }
  gq('gstat').textContent='PNG 합성 중...';
  const cs = await Promise.all(svgs.map(s=>svgToCanvas(s,2)));
  const W = Math.max(...cs.map(c=>c.canvas.width)), H = cs.reduce((a,c)=>a+c.canvas.height,0)+ (cs.length-1)*16;
  const big = document.createElement('canvas'); big.width=W; big.height=H;
  const cx = big.getContext('2d'); cx.fillStyle='#fff'; cx.fillRect(0,0,W,H);
  let y=0; for(const c of cs){ cx.drawImage(c.canvas,(W-c.canvas.width)/2,y); y+=c.canvas.height+16*2; }
  big.toBlob(b=>{ dlBlob(b,'storyboard.png'); gq('gstat').textContent='PNG 저장됨'; });
}
async function exportPDF(){
  const svgs=[...gq('gout').querySelectorAll('.gcard svg')]; if(!svgs.length) return;
  if(!(window.jspdf&&window.jspdf.jsPDF)){ alert('PDF 라이브러리를 불러오지 못했습니다(인터넷 필요).'); return; }
  gq('gstat').textContent='PDF 생성 중...';
  const cs=await Promise.all(svgs.map(s=>svgToCanvas(s,2)));
  const {jsPDF}=window.jspdf; let pdf=null;
  cs.forEach((c,i)=>{ const w=c.canvas.width, h=c.canvas.height;
    if(i===0) pdf=new jsPDF({orientation:w>h?'l':'p',unit:'px',format:[w,h]});
    else pdf.addPage([w,h], w>h?'l':'p');
    pdf.addImage(c.canvas.toDataURL('image/png'),'PNG',0,0,w,h); });
  pdf.save('storyboard.pdf'); gq('gstat').textContent='PDF 저장됨';
}
async function copyPNG(){
  const svgs=[...gq('gout').querySelectorAll('.gcard svg')]; if(!svgs.length) return;
  try{ const {canvas}=await svgToCanvas(svgs[0],2);
    canvas.toBlob(async b=>{ try{ await navigator.clipboard.write([new ClipboardItem({'image/png':b})]);
      gq('gstat').textContent='첫 컷 클립보드 복사됨'; }catch(e){ gq('gstat').innerHTML='<span style="color:#f99">복사 미지원 브라우저</span>'; } });
  }catch(e){ gq('gstat').innerHTML='<span style="color:#f99">복사 실패</span>'; }
}

gq('gsample').onclick = () => { gq('ginp').value = G_SAMPLE; parsePreview(); };
gq('ggen').onclick = genConti;
gq('gpng').onclick = ()=>exportPNG();
gq('gpdf').onclick = exportPDF;
gq('gcopy').onclick = copyPNG;
gq('gdl').onclick = () => { if(!gStrip) return; dlBlob(new Blob([gStrip],{type:'image/svg+xml'}),'storyboard.svg'); };
gq('ginp').addEventListener('keydown', e => { if((e.ctrlKey||e.metaKey)&&e.key==='Enter') genConti(); });

window.addEventListener('load',()=>{ parsePreview(); if(location.hash==='#cmp') show(2); if(location.hash==='#char') show(3); if(location.hash==='#pose') show(4); if(location.hash==='#angle') show(5); if(location.hash==='#gen') show(6); if(location.hash==='#prop') show(7); });
</script></body></html>""".replace("__CMP__", data_js).replace("__SAMPLE_SVG__", sample_svg_js).replace("__SAMPLE_TXT__", sample_txt_js))

    out = OUT_DIR / "viewer.html"
    out.write_text("".join(html), encoding="utf-8")
    print(f"✓ {out}")
    print(f"  브라우저로 열기: file:///{out.as_posix()}")


if __name__ == "__main__":
    main()
