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


# 테스트용 샘플 10종 — 샷·포즈·소품·인원·대사/나레이션/효과음을 골고루 (제목, 본문)
SAMPLES = [
    ("카페 앞 거리 (일상)", SAMPLE_TEXT),
    ("강변 고백 (로맨스)",
     '1. [풀샷] 노을 지는 강변에 남자와 여자가 나란히 선다.\n'
     '2. [클로즈업] 남자가 긴장한 표정으로 여자를 본다. / 남자: "할 말이 있어."\n'
     '3. [미들샷] 남자가 꽃을 내밀며 고백한다. / 남자: "좋아해, 우리 사귀자."\n'
     '4. [클로즈업] 여자가 환하게 웃는다. / 여자: "나도 좋아해!"\n'
     '5. [풀샷] 둘이 마주보고 껴안는다.'),
    ("집밥 식사 (소품)",
     '1. [미들샷] 식탁 앞에 앉은 매리가 밥을 먹는다.\n'
     '2. [클로즈업] 매리가 맛있게 먹으며 미소짓는다. / 매리: "역시 집밥이 최고야!"\n'
     '3. [미들샷] 무결이 커피를 마신다. / 무결: "잘 먹었어?"\n'
     '4. [미들샷] 매리가 엄지를 든다. / 매리: "완전!"'),
    ("밤거리 추격 (액션)",
     '1. [롱샷] 밤거리에서 라이더가 달린다. / 효과음: "타다닥"\n'
     '2. [풀샷] 라이더가 뒤를 돌아본다. / 라이더: "이쪽이야, 빨리!"\n'
     '3. [클로즈업] 라이더가 깜짝 놀란다. / 효과음: "두근"\n'
     '4. [풀샷] 라이더가 넘어진다. / 효과음: "쿵"\n'
     '5. [미들샷] 라이더가 머리를 부여잡는다. / 라이더: "아, 놓쳤다!"'),
    ("비 오는 이별 (감정)",
     '1. [미들샷] 비 오는 날, 여자가 우산을 들고 서있다.\n'
     '2. [클로즈업] 여자가 눈물을 닦는다. / 여자: "잘 가..."\n'
     '3. [클로즈업] 남자가 고개를 숙인다. / 나레이션: 둘은 그렇게 헤어졌다.\n'
     '4. [롱샷] 거리에 홀로 남은 여자.'),
    ("밴드 회의 (다인물)",
     '1. [롱샷] 회의실에 사람들이 모여있다.\n'
     '2. [미들샷] 정인이 손을 번쩍 든다. / 정인: "제안이 있습니다!"\n'
     '3. [미들샷] 무결이 팔짱을 낀다. / 무결: "들어보죠."\n'
     '4. [클로즈업] 정인이 진지하게 말한다. / 정인: "우리 밴드를 만들어요."'),
    ("공원 데이트 (소품)",
     '1. [풀샷] 공원에서 매리가 꽃을 든다.\n'
     '2. [미들샷] 무결이 가방을 메고 걸어온다. / 무결: "오래 기다렸어?"\n'
     '3. [미들샷] 매리가 손을 흔든다. / 매리: "방금 왔어!"\n'
     '4. [풀샷] 둘이 나란히 걷는다.'),
    ("심야 공포 (효과음)",
     '1. [미들샷] 어두운 방에서 엘리가 핸드폰을 본다.\n'
     '2. [클로즈업] 엘리가 깜짝 놀란다. / 효과음: "쿵" / 엘리: "뭐, 뭐야?!"\n'
     '3. [클로즈업] 엘리가 입을 가린다. / 엘리: (속마음) "설마 누가 있어?"\n'
     '4. [풀샷] 엘리가 뒤로 물러선다. / 효과음: "덜덜"'),
    ("합격 발표 (기쁨)",
     '1. [미들샷] 매리가 노트북으로 결과를 확인한다.\n'
     '2. [클로즈업] 매리가 환호한다. / 매리: "합격이야!!"\n'
     '3. [풀샷] 매리가 두 손을 들고 점프한다. / 효과음: "야호"\n'
     '4. [미들샷] 무결이 박수친다. / 무결: "축하해!"'),
    ("아침 루틴 (일상)",
     '1. [미들샷] 매리가 기지개를 켠다. / 매리: "잘 잤다~"\n'
     '2. [미들샷] 매리가 통화한다. / 매리: "응, 곧 나갈게."\n'
     '3. [클로즈업] 매리가 거울을 보며 미소짓는다.\n'
     '4. [풀샷] 매리가 가방을 메고 집을 나선다.'),
]


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
:root{--bg:#f4f6fb;--card:#ffffff;--card2:#eef1f7;--line:#e3e7ef;--tx:#1c2230;
  --mut:#5a6478;--dim:#8b94a6;--grad:linear-gradient(135deg,#6366f1,#a855f7 55%,#ec4899)}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);font-family:'Pretendard',system-ui,sans-serif;-webkit-font-smoothing:antialiased}
body::before{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;
  background:radial-gradient(700px 360px at 85% -8%,rgba(99,102,241,.09),transparent 60%),
    radial-gradient(600px 340px at 5% 4%,rgba(168,85,247,.07),transparent 60%)}
a{color:inherit;text-decoration:none}
/* nav header */
header{position:sticky;top:0;z-index:50;backdrop-filter:blur(12px);
  background:rgba(255,255,255,.85);border-bottom:1px solid var(--line);padding:0 26px}
.nav{display:flex;align-items:center;justify-content:space-between;height:60px}
.logo{font-size:19px;font-weight:800;display:flex;align-items:center;gap:9px;letter-spacing:-.01em}
.logo .dot{width:9px;height:9px;border-radius:50%;background:var(--grad)}
.logo b{background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
.nav-r{display:flex;align-items:center;gap:18px;font-size:14px;color:var(--mut)}
.nav-r a:hover{color:var(--tx)}
.navbtn{background:var(--grad);color:#fff!important;font-weight:700;padding:9px 18px;border-radius:11px;
  cursor:pointer;box-shadow:0 6px 18px rgba(124,58,237,.4);transition:.15s}
.navbtn:hover{transform:translateY(-1px)}
.tabs{display:flex;gap:8px;padding:11px 0 13px;flex-wrap:wrap}
.tab{padding:8px 16px;background:var(--card2);border-radius:11px;cursor:pointer;font-size:14.5px;
  font-weight:600;border:1px solid var(--line);color:var(--mut);transition:.15s}
.tab:hover{color:var(--tx);border-color:#c7cdda}
.tab.on{background:var(--grad);border-color:transparent;color:#fff;box-shadow:0 6px 18px rgba(124,58,237,.4)}
.tab.gen{color:#6d4bd8;border-color:rgba(124,58,237,.4)}
.tab.gen.on{color:#fff}
.view{display:none;padding:30px 26px}
.view.on{display:block;animation:fade .25s ease}
@keyframes fade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.gallery{display:flex;flex-wrap:wrap;gap:28px;justify-content:center}
.paper{background:#fff;border-radius:12px;box-shadow:0 8px 26px rgba(20,30,60,.13);border:1px solid var(--line);overflow:hidden}
.paper svg{display:block;width:360px;height:auto}
.cap{text-align:center;color:var(--mut);font-size:14px;margin-top:10px;font-weight:600}
.split{display:flex;gap:24px;align-items:flex-start;justify-content:center}
.txtcol{width:380px;max-height:84vh;overflow:auto}
.pcard{display:flex;gap:11px;background:var(--card);border-radius:12px;padding:12px 14px;
  margin-bottom:9px;border:1px solid var(--line)}
.pnum{flex:0 0 28px;height:28px;border-radius:9px;background:var(--grad);
  color:#fff;text-align:center;line-height:28px;font-size:14px;font-weight:700}
.ptags{color:#7c4dd8;font-size:12.5px;letter-spacing:.3px;font-weight:700}
.pdesc{font-size:15px;margin-top:3px}
.pdlg{color:#fff;background:var(--grad);display:inline-block;padding:2px 9px;border-radius:9px;margin-top:5px;font-size:14px}
.pinner{color:var(--mut);font-style:italic;font-size:13.5px;margin-top:3px}
.psfx{color:#2f8fc4;font-size:13.5px;margin-top:3px;font-weight:600}
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
.genleft textarea{width:100%;height:calc(100vh - 320px);min-height:300px;resize:none;background:#fff;color:var(--tx);
  border:1px solid var(--line);border-radius:14px;padding:16px 18px;
  font-family:ui-monospace,'Pretendard',monospace;font-size:14.5px;line-height:1.8;outline:none;transition:.15s;box-shadow:0 2px 10px rgba(20,30,60,.05)}
.genleft textarea:focus{border-color:#7c5cff;box-shadow:0 0 0 4px rgba(124,58,237,.15)}
.genhint{font-size:13px;color:var(--dim);margin:10px 0 0;line-height:1.6}
.genhint code{background:var(--card2);padding:2px 7px;border-radius:6px;color:#6d4bd8}
/* 하단 생성 바 (탭 진입 시에만 표시) */
.genbottom{display:none;position:fixed;left:0;right:0;bottom:0;z-index:60;
  padding:13px 26px;gap:12px;align-items:center;justify-content:center;flex-wrap:wrap;
  background:rgba(255,255,255,.92);backdrop-filter:blur(14px);border-top:1px solid var(--line);box-shadow:0 -6px 24px rgba(20,30,60,.07)}
.genbottom button{font-family:inherit;font-size:15px;font-weight:700;padding:12px 20px;border-radius:12px;
  cursor:pointer;border:1px solid var(--line);background:var(--card2);color:var(--tx);transition:.15s}
.genbottom button:hover{border-color:#c7cdda}
.genbottom button.primary{background:var(--grad);border-color:transparent;color:#fff;padding:12px 34px;font-size:16px;
  box-shadow:0 8px 22px rgba(124,58,237,.4)}
.genbottom button.primary:hover{transform:translateY(-1px)}
.genbottom button:disabled{opacity:.45;cursor:default;transform:none}
.gchk{display:flex;align-items:center;gap:7px;font-size:14px;color:var(--mut)}
.gstat{font-size:14px;color:var(--mut);min-width:120px;text-align:left}
.gresult{overflow:visible;min-height:calc(100vh - 320px)}
.gresult > svg{display:block;width:100%;height:auto}
.gph{display:flex;align-items:center;justify-content:center;text-align:center;min-height:calc(100vh - 320px);
  padding:40px 24px;font-size:16px;line-height:1.7;color:var(--mut);background:var(--card2);
  border:1px solid var(--line);border-radius:14px}
.gph code{background:#eef;padding:2px 7px;border-radius:6px;color:#5b3fd6}
.spin{width:42px;height:42px;margin:0 auto 16px;border:5px solid #e6e2ff;
  border-top-color:#7c5cff;border-radius:50%;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
/* 입력 보조: 샷 칩 + 실시간 파싱 프리뷰 */
.chips{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin:0 0 9px}
.chip-sp{flex:1 1 auto;min-width:6px}
.chips .gtool{font-family:inherit;font-size:12.5px;font-weight:600;padding:6px 11px;border-radius:9px;
  border:1px solid var(--line);background:var(--card2);color:var(--tx);cursor:pointer;outline:none}
.chips select.gtool{max-width:170px}
.chips #gfmt{background:rgba(124,58,237,.1);border-color:rgba(124,58,237,.4);color:#6d4bd8;font-weight:700}
.chips #gfmt:hover{background:rgba(124,58,237,.18);color:#5a2ec0}
.chips .chip{font-size:12.5px;font-weight:600;padding:6px 11px;border-radius:9px;cursor:pointer;
  border:1px solid var(--line);background:var(--card2);color:var(--tx);transition:.12s;user-select:none}
.chips .chip:hover{border-color:#7c5cff;color:#6d4bd8;background:rgba(124,58,237,.1)}
.chips .chip.alt{color:var(--mut)}
/* 입력 자동완성 팝업 */
.gac{display:none;position:absolute;z-index:30;flex-wrap:wrap;gap:5px;max-width:520px;
  background:#fff;border:1px solid var(--line);border-radius:11px;padding:8px;box-shadow:0 12px 30px rgba(20,30,60,.18)}
.gac .acitem{font-family:inherit;font-size:13px;font-weight:600;padding:6px 11px;border-radius:8px;cursor:pointer;
  border:1px solid var(--line);background:var(--card2);color:var(--tx);display:flex;align-items:center;gap:6px}
.gac .acitem:hover{border-color:#7c5cff;background:rgba(124,58,237,.1)}
.gac .acitem i{font-style:normal;font-size:11px;color:var(--dim)}
.gpreview{display:flex;gap:7px;flex-wrap:wrap;align-items:center;margin:11px 0 0;min-height:24px;font-size:12.5px}
.gpreview .pv{padding:4px 10px;border-radius:999px;background:rgba(124,58,237,.1);
  border:1px solid rgba(124,58,237,.28);color:#6d4bd8;font-weight:600}
.gpreview .pv.muted{background:var(--card2);border-color:var(--line);color:var(--mut);font-weight:500}
/* 웹툰형 단일 캔버스 — 흰 바탕 위에 컷이 이어서 올라감. 첫 컷 위·아래 여백을 컷 간격과 동일하게 */
.pstack{display:flex;flex-direction:column;gap:160px;background:#fff;border-radius:14px;
  padding:160px 16px;border:1px solid var(--line);box-shadow:0 8px 30px rgba(20,30,60,.12)}
.gcard{display:flex;flex-direction:column;background:#fff;position:relative;z-index:0}
.gcard:hover{z-index:6}                       /* hover 시 옵션 패널이 옆 컷 위로 */
.gcard.busy{opacity:.5}
.gcard svg{display:block;width:100%;height:auto}
/* 컨트롤: 평소 숨김 → 컷에 마우스 올리면 컷 '바깥 오른쪽'에 화이트 UI 패널로 떠오름(그림 안 가림) */
.gcard-bar{position:absolute;top:50%;left:100%;margin-left:14px;transform:translate(8px,-50%);
  display:flex;flex-direction:column;gap:8px;align-items:stretch;width:178px;
  padding:13px;background:#fff;border:1px solid #e4e7ef;border-radius:13px;
  box-shadow:0 12px 30px rgba(0,0,0,.22);opacity:0;transition:.16s;pointer-events:none;z-index:5}
/* 컷↔패널 사이 빈 틈을 메우는 투명 브릿지 — 마우스가 옮겨갈 때 hover가 끊기지 않게 */
.gcard-bar::before{content:"";position:absolute;top:-10px;bottom:-10px;left:-30px;width:40px}
.gcard:hover .gcard-bar{opacity:1;transform:translate(0,-50%);pointer-events:auto}
.gcard-bar .pn{font-size:12px;font-weight:800;color:#9aa0b2;letter-spacing:.04em}
.gcard-bar select{font-family:inherit;font-size:13px;padding:8px 9px;border-radius:9px;
  background:#f5f6fa;color:#222;border:1px solid #dde1ec;cursor:pointer;outline:none;width:100%}
.gcard-bar select:hover{border-color:#a99bff}
.gcard-bar .iconbtn{font-size:13px;font-weight:700;padding:9px 10px;border-radius:9px;cursor:pointer;
  border:1px solid #dde1ec;background:#f5f6fa;color:#333;transition:.12s;width:100%}
.gcard-bar .iconbtn:hover{border-color:#7c5cff;color:#7c5cff;background:#fff}
.gcard-bar .sp{display:none}
/* 컷 관리 버튼(편집·추가·복제·이동·삭제) */
.gcard-ops{display:flex;gap:5px;flex-wrap:wrap;margin-top:6px;padding-top:8px;border-top:1px solid #eef0f5}
.gcard-ops .opbtn{flex:1 1 auto;min-width:30px;font-family:inherit;font-size:12.5px;font-weight:700;
  padding:6px 6px;border-radius:8px;border:1px solid #dde1ec;background:#f5f6fa;color:#444;cursor:pointer;transition:.12s}
.gcard-ops .opbtn[data-edit]{flex:1 1 100%}
.gcard-ops .opbtn:hover{border-color:#7c5cff;color:#7c5cff;background:#fff}
.gcard-ops .opbtn.del:hover{border-color:#e3506a;color:#e3506a}
/* 컷 인라인 편집 오버레이 */
.gcard-edit{position:absolute;inset:0;z-index:9;background:rgba(255,255,255,.97);
  display:flex;flex-direction:column;gap:9px;padding:16px}
.gcard-edit textarea{flex:1;min-height:90px;width:100%;resize:none;border:1px solid #cdd3e0;border-radius:9px;
  padding:11px 12px;font-family:ui-monospace,'Pretendard',monospace;font-size:14.5px;line-height:1.7;color:#222;outline:none}
.gcard-edit textarea:focus{border-color:#7c5cff;box-shadow:0 0 0 3px rgba(124,58,237,.15)}
.gcard-edit .ged-btns{display:flex;gap:8px;justify-content:flex-end}
.gcard-edit button{font-family:inherit;font-size:13.5px;font-weight:700;padding:9px 20px;border-radius:9px;
  cursor:pointer;border:1px solid #dde1ec;background:#f5f6fa;color:#333}
.gcard-edit .ged-apply{background:var(--grad);border-color:transparent;color:#fff}
/* 컷 번호 배지(좌상단, 항상 표시) */
.gcard-mini{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
  background:rgba(255,255,255,.55)}
/* 첫 진입 예시 배너 */
.gsample-banner{display:flex;align-items:center;gap:10px;margin:0 0 14px;padding:12px 16px;border-radius:12px;
  background:rgba(124,58,237,.09);border:1px solid rgba(124,58,237,.28);color:#6d4bd8;
  font-size:13.5px;line-height:1.55;word-break:keep-all}
.gsample-banner .ic{flex:0 0 auto;font-size:17px}
.gsample-banner span{flex:1 1 auto}
.gsample-banner b{color:#4a2bb0}
.exp-sep{width:1px;height:24px;background:var(--line);margin:0 2px}
/* ── 모바일/태블릿 대응 ───────────────────────────── */
@media(max-width:860px){
  header{padding:0 14px}
  .nav{height:54px}
  .logo{font-size:17px}
  .nav-r{gap:11px;font-size:13px}
  .navbtn{padding:8px 13px}
  .tabs{gap:6px;padding:9px 0 11px}
  .tab{padding:7px 12px;font-size:13.5px}
  .view{padding:18px 12px}
  .note{font-size:14px;padding:13px 15px;margin-bottom:18px}
  /* 직접 생성: 좌우 1:1 → 세로 스택(입력 위, 결과 아래) */
  #v6.view{padding-bottom:74px}
  .genwrap{flex-direction:column;gap:14px;max-width:none}
  .genleft{position:static;flex:none;width:100%;min-width:0}
  .genright{flex:none;width:100%}
  .genleft textarea{height:34vh;min-height:170px}
  .gresult{min-height:0}
  .gph{min-height:200px;padding:30px 18px}
  .chips .chip{font-size:12px;padding:5px 9px}
  /* 결과 캔버스: 여백/간격 모바일에 맞게 축소 */
  .pstack{gap:42px;padding:24px 10px;border-radius:10px}
  /* 컷 컨트롤: 터치엔 hover가 없으므로 컷 아래 항상 보이는 막대로 전환 */
  .gcard-bar{position:static;left:auto;right:auto;margin:0;width:auto;transform:none;opacity:1;
    pointer-events:auto;flex-direction:row;flex-wrap:wrap;gap:6px;align-items:center;
    background:#f6f7fb;border:none;border-top:1px solid #e6e8f0;border-radius:0;box-shadow:none;padding:9px 10px;z-index:auto}
  .gcard:hover .gcard-bar{transform:none}
  .gcard-bar .pn{flex:0 0 100%;margin-bottom:1px}
  .gcard-bar select{width:auto;flex:1 1 44%;font-size:12.5px}
  .gcard-bar .iconbtn{flex:1 1 44%;font-size:12.5px}
  /* 하단 생성바: 한 줄 가로 스크롤 */
  .genbottom{justify-content:flex-start;flex-wrap:nowrap;overflow-x:auto;gap:7px;padding:9px 12px}
  .genbottom>*{flex:0 0 auto}
  .genbottom button{font-size:13px;padding:9px 13px}
  .genbottom button.primary{padding:9px 18px;font-size:14px}
  .gstat{min-width:0}
  .exp-sep{display:none}
  /* 비교·갤러리·시트: 세로 스택 + 폭 100% */
  .cmpwrap{flex-direction:column;align-items:center;gap:18px}
  .cmpcol .paper{width:100%;max-width:360px;height:auto;max-height:66vh}
  .cmpcol object,.cmpcol img{width:100%}
  .split{flex-direction:column;align-items:center}
  .txtcol{width:100%;max-width:460px;max-height:none}
  .gallery{gap:18px}
  .gallery .paper{max-width:100%}
  .paper svg{width:100%!important;height:auto}
}
@media(max-width:480px){
  .tab{font-size:12.5px;padding:6px 10px}
  .gcard-bar select,.gcard-bar .iconbtn{flex-basis:100%}
  .genleft textarea{height:30vh}
}
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
    html.append(
        '<div class="chips" id="gchips">'
        '<span class="chip" data-ins="[풀샷] ">풀샷</span>'
        '<span class="chip" data-ins="[미들샷] ">미들샷</span>'
        '<span class="chip" data-ins="[클로즈업] ">클로즈업</span>'
        '<span class="chip" data-ins="[롱샷] ">롱샷</span>'
        '<span class="chip alt" data-ins=" / 매리: &quot;&quot;">대사</span>'
        '<span class="chip alt" data-ins=" / 효과음: \'\'">효과음</span>'
        '<span class="chip alt" data-ins=" / 나레이션: ">나레이션</span>'
        '<span class="chip-sp"></span>'
        '<select class="gtool" id="gsamplesel" title="샘플 선택"><option value="">📑 샘플 선택…</option></select>'
        '<button class="gtool" id="gfmt" title="자연글을 글콘티 형식으로 정리">✎ 글콘티 형식으로</button>'
        '</div>'
        '<div class="genwrap">'
        '<div class="genleft">'
        '<textarea id="ginp" placeholder="여기에 글콘티 입력 (줄글을 그대로 붙여넣어도 됩니다)...&#10;예) 1. [미들샷] 매리가 웃는다. / 매리: &quot;안녕!&quot;"></textarea>'
        '<div class="gac" id="gac"></div>'
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
    sample_txt_js = json.dumps(SAMPLE_TEXT, ensure_ascii=False)
    samples_js = json.dumps([{"t": t, "x": x} for t, x in SAMPLES], ensure_ascii=False)
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
const G_SAMPLES = __SAMPLES__;         // 테스트 샘플 10종 [{t:제목, x:본문}]
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
let _pvT; gq('ginp').addEventListener('input', ()=>{ clearTimeout(_pvT); _pvT=setTimeout(parsePreview,120); showAC(); });

// ── 입력 자동완성 (인물·샷·소품·동작) ──
const AC_LIST = [].concat(
  ['매리','무결','엘리','라이더','정인','신성우','하은','주태경','루나','이한'].map(v=>({v,t:'인물',ins:v})),
  [['풀샷','[풀샷] '],['미들샷','[미들샷] '],['클로즈업','[클로즈업] '],['롱샷','[롱샷] ']].map(([v,ins])=>({v,t:'샷',ins})),
  ['우산','가방','커피','꽃','노트북','핸드폰','책','케이크','풍선','선물','기타','마이크','카메라','물병','캐리어','공'].map(v=>({v,t:'소품',ins:v})),
  ['걷는다','달린다','웃는다','운다','놀란다','앉는다','손을 흔든다','팔짱을 낀다','점프한다','넘어진다','기지개를 켠다','통화한다'].map(v=>({v,t:'동작',ins:v}))
);
function acWord(ta){ const s=ta.value.slice(0,ta.selectionStart); const m=s.match(/([가-힣A-Za-z]{1,12})$/); return m?m[1]:''; }
function showAC(){
  const ta=gq('ginp'), pop=gq('gac'), w=acWord(ta);
  if(w.length<1){ pop.style.display='none'; return; }
  const ms=AC_LIST.filter(o=>o.v.indexOf(w)===0 && o.v!==w).slice(0,8);
  if(!ms.length){ pop.style.display='none'; return; }
  pop.innerHTML=ms.map(o=>`<button class="acitem" data-ins="${o.ins.replace(/"/g,'&quot;')}" data-w="${w}">${o.v}<i>${o.t}</i></button>`).join('');
  pop.style.left='0px'; pop.style.top=(ta.offsetTop+ta.offsetHeight+4)+'px'; pop.style.display='flex';
}
gq('gac').addEventListener('mousedown', e=>{
  const b=e.target.closest('.acitem'); if(!b) return; e.preventDefault();
  const ta=gq('ginp'), w=b.dataset.w, ins=b.dataset.ins, cur=ta.selectionStart;
  ta.value=ta.value.slice(0,cur-w.length)+ins+ta.value.slice(cur);
  const np=cur-w.length+ins.length; ta.focus(); ta.setSelectionRange(np,np);
  gq('gac').style.display='none'; parsePreview();
});
gq('ginp').addEventListener('blur', ()=>setTimeout(()=>{ gq('gac').style.display='none'; },160));
gq('ginp').addEventListener('keydown', e=>{ if(e.key==='Escape') gq('gac').style.display='none'; });

// ── 카드 렌더 ──
function optSel(field, cur, idx){
  const o = OPT[field].map(([l,v])=>`<option value="${v}"${v===cur?' selected':''}>${LBL[field]}: ${l}</option>`).join('');
  return `<select data-idx="${idx}" data-field="${field}">${o}</select>`;
}
function cardHTML(p, i){
  return `<div class="gcard" data-idx="${i}" id="gcard${i}">`
    + (p.svg||'')
    + '<div class="gcard-bar">'
    + `<span class="pn">#${i+1}</span>`
    + optSel('shot',p.shot,i)+optSel('pose',p.pose,i)+optSel('emotion',p.emotion,i)+optSel('view',p.view,i)
    + `<button class="iconbtn" data-reroll="${i}">🎲 리롤</button>`
    + `<button class="iconbtn" data-png="${i}">⬇ PNG</button>`
    + '<div class="gcard-ops">'
    +   `<button class="opbtn" data-edit="${i}" title="대사·묘사 편집">✎ 편집</button>`
    +   `<button class="opbtn" data-add="${i}" title="아래에 컷 추가">➕</button>`
    +   `<button class="opbtn" data-dup="${i}" title="복제">⧉</button>`
    +   `<button class="opbtn" data-up="${i}" title="위로">↑</button>`
    +   `<button class="opbtn" data-down="${i}" title="아래로">↓</button>`
    +   `<button class="opbtn del" data-del="${i}" title="삭제">🗑</button>`
    + '</div>'
    + '</div></div>';
}
// ── 컷 인라인 편집 ──
function openEditor(i){
  const card=gq('gcard'+i); if(!card||card.querySelector('.gcard-edit')) return;
  const ed=document.createElement('div'); ed.className='gcard-edit';
  const ta=document.createElement('textarea'); ta.value=gPanels[i].src||'';
  ta.placeholder='[샷] 묘사 / 화자: "대사"';
  const btns=document.createElement('div'); btns.className='ged-btns';
  const ap=document.createElement('button'); ap.className='ged-apply'; ap.textContent='적용';
  const cc=document.createElement('button'); cc.textContent='취소';
  btns.append(cc,ap); ed.append(ta,btns); card.appendChild(ed); ta.focus();
  const close=()=>ed.remove();
  const apply=()=>{ const t=ta.value.trim(); close(); if(t) cutReq(i,t); };
  cc.onclick=close; ap.onclick=apply;
  ta.addEventListener('keydown',e=>{ if((e.ctrlKey||e.metaKey)&&e.key==='Enter') apply(); else if(e.key==='Escape') close(); });
}
async function cutReq(i, text){
  const card=gq('gcard'+i); card.classList.add('busy');
  card.insertAdjacentHTML('beforeend','<div class="gcard-mini"><div class="spin"></div></div>');
  try{
    const res=await fetch(G_API+'/api/cut',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({text, gray:gq('ggray').checked, seed:gPanels[i].seed||5})});
    const d=await res.json();
    if(d.error){ gq('gstat').innerHTML='<span style="color:#dc3055">⚠ '+d.error+'</span>';
      card.classList.remove('busy'); const m=card.querySelector('.gcard-mini'); if(m) m.remove(); return; }
    gPanels[i]={svg:d.svg,shot:d.shot,pose:d.pose,emotion:d.emotion,view:d.view,panel:d.panel,seed:d.seed,src:d.src};
    renderCards(); gq('gstat').textContent='#'+(i+1)+' 컷 수정됨';
  }catch(e){ gq('gstat').innerHTML='<span style="color:#dc3055">서버 연결 실패</span>'; }
}
function dupCut(i){ gPanels.splice(i+1,0,Object.assign({},gPanels[i])); renderCards(); gq('gstat').textContent='컷 복제됨'; }
function delCut(i){ if(gPanels.length<=1){ gq('gstat').textContent='마지막 컷은 삭제할 수 없습니다'; return; }
  gPanels.splice(i,1); renderCards(); gq('gstat').textContent='컷 삭제됨'; }
function moveCut(i,dir){ const j=i+dir; if(j<0||j>=gPanels.length) return;
  [gPanels[i],gPanels[j]]=[gPanels[j],gPanels[i]]; renderCards(); }
function addCut(i){ gPanels.splice(i+1,0,Object.assign({},gPanels[i])); renderCards(); openEditor(i+1); }
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
    if(d.error){ gq('gstat').innerHTML='<span style="color:#dc3055">⚠ '+d.error+'</span>'; }
    else{
      gPanels[i] = {svg:d.svg, shot:d.shot, pose:d.pose, emotion:d.emotion, view:d.view, panel:d.panel, seed:d.seed, src:d.src!==undefined?d.src:p.src};
      const nc = document.createElement('div'); nc.innerHTML = cardHTML(gPanels[i], i);
      card.replaceWith(nc.firstChild);
    }
  }catch(e){ gq('gstat').innerHTML='<span style="color:#dc3055">서버 연결 실패</span>'; }
}
// 이벤트 위임: 드롭다운 편집 / 리롤 / 패널 PNG
gq('gout').addEventListener('change', e=>{
  const s=e.target.closest('select'); if(!s) return;
  panelReq(+s.dataset.idx, {[s.dataset.field]: s.value});
});
gq('gout').addEventListener('click', e=>{
  const rr=e.target.closest('[data-reroll]'); if(rr){ const i=+rr.dataset.reroll;
    panelReq(i, {seed: ((gPanels[i].seed||5)%97)+7}); return; }   // 시드 회전 → 선 흔들림 다르게
  const pg=e.target.closest('[data-png]'); if(pg){ exportPNG(+pg.dataset.png); return; }
  const ed=e.target.closest('[data-edit]'); if(ed){ openEditor(+ed.dataset.edit); return; }
  const ad=e.target.closest('[data-add]'); if(ad){ addCut(+ad.dataset.add); return; }
  const dp=e.target.closest('[data-dup]'); if(dp){ dupCut(+dp.dataset.dup); return; }
  const up=e.target.closest('[data-up]'); if(up){ moveCut(+up.dataset.up,-1); return; }
  const dn=e.target.closest('[data-down]'); if(dn){ moveCut(+dn.dataset.down,1); return; }
  const dl=e.target.closest('[data-del]'); if(dl){ delCut(+dl.dataset.del); return; }
});

// ── 생성 ──
async function genConti(){
  const text = gq('ginp').value.trim();
  if(!text){ gq('gstat').innerHTML='<span style="color:#dc3055">글콘티를 입력하세요.</span>'; return; }
  gq('ggen').disabled=true; gq('gstat').textContent='생성 중...';
  gq('gout').innerHTML='<div class="gph"><div class="spin"></div>생성 중...</div>';
  try{
    const res = await fetch(G_API+'/api/generate', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({text, gray: gq('ggray').checked})});
    const d = await res.json();
    if(d.error){
      gq('gstat').innerHTML='<span style="color:#dc3055">오류</span>';
      gq('gout').innerHTML='<div class="gph">⚠ '+d.error+'</div>';
    } else {
      gPanels = d.panels.map(p=>({svg:p.svg,shot:p.shot,pose:p.pose,emotion:p.emotion,view:p.view,panel:p.panel,seed:5,src:p.src}));
      gStrip = d.strip || '';
      renderCards();
      ['gpng','gpdf','gcopy','gdl'].forEach(id=>gq(id).disabled=false);
      gq('gstat').textContent = d.count+'컷 · 샷 '+Object.entries(d.shots).map(([k,v])=>k+'×'+v).join(' ');
    }
  }catch(e){
    gq('gstat').innerHTML='<span style="color:#dc3055">서버 연결 실패</span>';
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
      gq('gstat').textContent='첫 컷 클립보드 복사됨'; }catch(e){ gq('gstat').innerHTML='<span style="color:#dc3055">복사 미지원 브라우저</span>'; } });
  }catch(e){ gq('gstat').innerHTML='<span style="color:#dc3055">복사 실패</span>'; }
}

// 샘플 10종 드롭다운 채우기 + 선택 시 로드
(function(){ const sel=gq('gsamplesel'); if(!sel) return;
  G_SAMPLES.forEach((s,i)=>{ const o=document.createElement('option'); o.value=String(i); o.textContent=(i+1)+'. '+s.t; sel.appendChild(o); });
  sel.onchange=()=>{ const i=sel.value; if(i==='') return; gq('ginp').value=G_SAMPLES[+i].x; parsePreview(); sel.selectedIndex=0;
    gq('ginp').scrollTop=0; gq('gstat').textContent='샘플 불러옴: '+G_SAMPLES[+i].t; };
})();
// 자연글 → 글콘티 형식 정리 (서버 우선, 실패 시 클라이언트 휴리스틱)
function localFormat(text){
  const sents = text.replace(/\r/g,'').split(/\n+|(?<=[.!?。])\s+/).map(s=>s.trim()).filter(Boolean);
  let out=[];
  sents.forEach((s,idx)=>{
    if(/^\s*\d+[.)\]]/.test(s)){ out.push(s); return; }   // 이미 번호형식이면 유지
    let dlg=''; const m=s.match(/["“]([^"”]+)["”]/); if(m) dlg=m[1];
    let shot='미들샷';
    if(/얼굴|표정|웃|놀란|눈물|울|찡그|분노|화난|클로즈/.test(s)) shot='클로즈업';
    else if(/걷|달리|뛰|전신|서 ?있|쓰러|넘어|점프|일어/.test(s)) shot='풀샷';
    else if(/거리|사람들|군중|풍경|멀리|전경|모여/.test(s)) shot='롱샷';
    let body=s.replace(/["“][^"”]+["”]/,'').replace(/\s+/g,' ').trim();
    let line='['+shot+'] '+body;
    if(dlg){ const nm=(s.match(/([가-힣]{2,4})(가|는|이|은|와|과|아|야|이가)/)||[])[1]||'화자'; line+=' / '+nm+': "'+dlg+'"'; }
    out.push((idx+1)+'. '+line);
  });
  return out.join('\n');
}
async function formatText(){
  const text=gq('ginp').value.trim();
  if(!text){ gq('gstat').innerHTML='<span style="color:#dc3055">먼저 글을 입력하세요.</span>'; return; }
  gq('gfmt').disabled=true; gq('gstat').textContent='형식 정리 중...';
  try{
    const res=await fetch(G_API+'/api/format',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})});
    const d=await res.json();
    if(d.error||!d.text) throw 0;
    gq('ginp').value=d.text; gq('gstat').textContent=d.count+'컷 형식으로 정리됨';
  }catch(e){
    gq('ginp').value=localFormat(text); gq('gstat').textContent='형식으로 정리됨(간이 변환)';
  }
  parsePreview(); gq('gfmt').disabled=false;
}
gq('gfmt').onclick = formatText;
gq('ggen').onclick = genConti;
gq('gpng').onclick = ()=>exportPNG();
gq('gpdf').onclick = exportPDF;
gq('gcopy').onclick = copyPNG;
gq('gdl').onclick = () => { if(!gStrip) return; dlBlob(new Blob([gStrip],{type:'image/svg+xml'}),'storyboard.svg'); };
gq('ginp').addEventListener('keydown', e => { if((e.ctrlKey||e.metaKey)&&e.key==='Enter') genConti(); });

window.addEventListener('load',()=>{ parsePreview(); if(location.hash==='#cmp') show(2); if(location.hash==='#char') show(3); if(location.hash==='#pose') show(4); if(location.hash==='#angle') show(5); if(location.hash==='#gen') show(6); if(location.hash==='#prop') show(7); });
</script></body></html>""".replace("__CMP__", data_js).replace("__SAMPLE_SVG__", sample_svg_js).replace("__SAMPLE_TXT__", sample_txt_js).replace("__SAMPLES__", samples_js))

    out = OUT_DIR / "viewer.html"
    out.write_text("".join(html), encoding="utf-8")
    print(f"✓ {out}")
    print(f"  브라우저로 열기: file:///{out.as_posix()}")


if __name__ == "__main__":
    main()
