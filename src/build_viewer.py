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
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
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
/* 직접 생성 탭 — 중앙정렬·좌우 여백·콤팩트 */
.genwrap{display:flex;gap:22px;align-items:stretch;height:66vh;max-width:1040px;margin:0 auto}
.genleft{flex:0 0 42%;display:flex;flex-direction:column}
.genright{flex:1;display:flex;flex-direction:column}
.genleft textarea{flex:1;width:100%;resize:none;background:#0e1118;color:var(--tx);
  border:1px solid var(--line);border-radius:14px;padding:16px 18px;
  font-family:ui-monospace,'Pretendard',monospace;font-size:14.5px;line-height:1.8;outline:none;transition:.15s}
.genleft textarea:focus{border-color:#7c5cff;box-shadow:0 0 0 4px rgba(124,58,237,.18)}
.genhint{font-size:13px;color:var(--dim);margin:10px 0;line-height:1.6}
.genhint code{background:var(--card2);padding:2px 7px;border-radius:6px;color:#bcd}
.genbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.genbar button{font-family:inherit;font-size:15px;font-weight:700;padding:11px 18px;border-radius:12px;
  cursor:pointer;border:1px solid var(--line);background:var(--card2);color:var(--tx);transition:.15s}
.genbar button:hover{border-color:#3a415a}
.genbar button.primary{background:var(--grad);border-color:transparent;color:#fff;padding:11px 26px;font-size:16px;
  box-shadow:0 8px 22px rgba(124,58,237,.4)}
.genbar button.primary:hover{transform:translateY(-1px)}
.genbar button:disabled{opacity:.45;cursor:default;transform:none}
.gchk{display:flex;align-items:center;gap:7px;font-size:14px;color:var(--mut)}
.gstat{font-size:14px;color:var(--mut);margin:10px 0;min-height:20px}
.genright .paper{flex:1;background:#fff;border-radius:14px;overflow:auto}
.genright .paper svg{display:block;width:100%;height:auto}
.gph{color:#667;text-align:center;padding:90px 24px;font-size:16px;line-height:1.7}
.gph code{background:#eef;padding:2px 7px;border-radius:6px;color:#5b3fd6}
.spin{width:42px;height:42px;margin:0 auto 16px;border:5px solid #e6e2ff;
  border-top-color:#7c5cff;border-radius:50%;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
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
        '<textarea id="ginp" placeholder="여기에 글콘티 입력...&#10;예) 1. [미들샷] 매리가 웃는다. / 매리: &quot;안녕!&quot;"></textarea>'
        '<div class="genhint">형식: <code>번호. [샷] 상황묘사 / 화자: "대사"</code> · '
        '샷: 풀샷·미들샷·클로즈업·롱샷 · 인물 이름(매리·무결·엘리·라이더·정인 등)으로 색/성별 반영 · '
        '"둘/서로"=2명, "사람들"=다인물 · Ctrl+Enter로 생성</div>'
        '<div class="genbar">'
        '<button class="primary" id="ggen">✎ 생성</button>'
        '<button id="gsample">샘플 불러오기</button>'
        '<button id="gdl" disabled>SVG 저장</button>'
        '<span class="gchk"><input type="checkbox" id="ggray" checked> 흑백</span>'
        '</div><div class="gstat" id="gstat"></div>'
        '</div>'
        '<div class="genright"><div class="paper" id="gout"><div class="gph">생성 결과가 여기에 표시됩니다</div></div></div>'
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

    data_js = json.dumps({m["stem"]: m for m in compare}, ensure_ascii=False)
    html.append("""<script>
const CMP = %s;
function show(i){
  document.querySelectorAll('.view').forEach((v,j)=>v.classList.toggle('on',i===j));
  document.querySelectorAll('.tab').forEach((t,j)=>t.classList.toggle('on',i===j));
  if(i===2 && !document.getElementById('genobj').data) loadEp();
  if(i===6) checkGen();
}
function checkGen(){     // 생성 탭 진입 시 서버 연결 미리 확인
  if(gLast) return;
  fetch(G_API+'/', {method:'GET'}).catch(()=>{
    gq('gout').innerHTML='<div class="gph">생성하려면 서버가 필요합니다.<br><br>'
      +'터미널에서 <code>python src/server.py</code> 를 실행하고,<br>'
      +'열리는 <code>http://127.0.0.1:8000</code> 에서 이 페이지를 여세요.</div>';
  });
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
const G_SAMPLE = `1. [풀샷] 카페 앞 거리. 매리가 걸어간다.
2. [미들샷] 매리가 환하게 웃는다. / 매리: "오늘 날씨 좋다!"
3. [클로즈업] 매리가 생각에 잠긴다. / 매리: (속마음) '뭐 먹지?'
4. [미들샷] 무결이 손을 흔들며 인사한다. / 무결: "매리야!"
5. [미들샷] 매리와 무결이 서로 마주본다. / 매리: "어, 무결아!"
6. [풀샷] 둘이 나란히 걷는다.
7. [클로즈업] 매리가 깜짝 놀란다. / 매리: "헉, 저게 뭐야?!" / 효과음: '두근'
8. [롱샷] 거리에 사람들이 모여있다.`;
let gLast='';
const gq = id => document.getElementById(id);
gq('gsample').onclick = () => { gq('ginp').value = G_SAMPLE; };
gq('gdl').onclick = () => { if(!gLast) return; const b=new Blob([gLast],{type:'image/svg+xml'});
  const a=document.createElement('a'); a.href=URL.createObjectURL(b); a.download='conti.svg'; a.click(); };
async function genConti(){
  const text = gq('ginp').value.trim();
  if(!text){ gq('gstat').innerHTML='<span style="color:#f99">글콘티를 입력하세요.</span>'; return; }
  gq('ggen').disabled=true; gq('gstat').textContent='생성 중...';
  gq('gout').innerHTML='<div class="gph"><div class="spin"></div>생성 중...</div>';   // 로딩 스피너
  try{
    const res = await fetch(G_API+'/api/generate', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({text, gray: gq('ggray').checked})});
    const d = await res.json();
    if(d.error){
      gq('gstat').innerHTML='<span style="color:#f99">오류</span>';
      gq('gout').innerHTML='<div class="gph">⚠ '+d.error+'</div>';
    } else {
      gLast=d.svg; gq('gout').innerHTML=d.svg; gq('gdl').disabled=false;
      gq('gstat').textContent = d.panels+'컷 생성 · 샷 '+JSON.stringify(d.shots);
    }
  }catch(e){
    gq('gstat').innerHTML='<span style="color:#f99">서버 연결 실패</span>';
    gq('gout').innerHTML='<div class="gph">⚠ 생성 서버에 연결할 수 없습니다.<br><br>'
      +'터미널에서 <code>python src/server.py</code> 를 실행한 뒤,<br>'
      +'자동으로 열리는 <code>http://127.0.0.1:8000</code> 에서 다시 시도하세요.</div>';
  }
  gq('ggen').disabled=false;
}
gq('ggen').onclick = genConti;
gq('ginp').addEventListener('keydown', e => { if((e.ctrlKey||e.metaKey)&&e.key==='Enter') genConti(); });

window.addEventListener('load',()=>{ if(location.hash==='#cmp') show(2); if(location.hash==='#char') show(3); if(location.hash==='#pose') show(4); if(location.hash==='#angle') show(5); if(location.hash==='#gen') show(6); if(location.hash==='#prop') show(7); });
</script></body></html>""" % data_js)

    out = OUT_DIR / "viewer.html"
    out.write_text("".join(html), encoding="utf-8")
    print(f"✓ {out}")
    print(f"  브라우저로 열기: file:///{out.as_posix()}")


if __name__ == "__main__":
    main()
