# -*- coding: utf-8 -*-
"""
서비스 랜딩 페이지 생성 (output/index.html)
실제 생성된 예시 SVG를 인라인해 '진짜 결과'를 보여준다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import classify_panels as C
import svg_render as R

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

EXAMPLE = """1. [미들샷] 매리가 환하게 웃으며 말한다 / 매리: "콘티 다 썼어!"
2. [클로즈업] 무결이 놀란다 / 무결: "벌써 다 했다고?"
3. [풀샷] 매리와 무결이 마주본다"""


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


PAGE = r"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Storyboard · 글콘티 → 그림콘티 생성기</title>
<link rel="icon" type="image/svg+xml" href="favicon.svg">
<link rel="apple-touch-icon" href="favicon.svg">
<meta name="description" content="텍스트 콘티(글콘티)를 입력하면 손그림 스타일 그림콘티를 SVG로 즉시 생성. 캐릭터·포즈·표정·말풍선까지 자동.">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
<style>
@import url('https://fonts.googleapis.com/css2?family=Nanum+Pen+Script&display=swap');
:root{
  --bg:#f4f6fb; --card:#ffffff; --card2:#eef1f7; --line:#e3e7ef;
  --tx:#1c2230; --mut:#5a6478; --dim:#8b94a6;
  --g1:#6366f1; --g2:#a855f7; --g3:#22d3ee;
  --grad:linear-gradient(135deg,#6366f1 0%,#a855f7 55%,#ec4899 100%);
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--tx);font-family:'Pretendard',system-ui,sans-serif;line-height:1.6;
  -webkit-font-smoothing:antialiased;overflow-x:hidden}
.pen{font-family:'Nanum Pen Script',cursive}
a{color:inherit;text-decoration:none}
.wrap{max-width:1160px;margin:0 auto;padding:0 24px}
.grad-tx{background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
/* 배경 글로우 */
body::before{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;
  background:
    radial-gradient(700px 400px at 80% -5%, rgba(99,102,241,.10), transparent 60%),
    radial-gradient(600px 380px at 5% 8%, rgba(168,85,247,.08), transparent 60%),
    radial-gradient(700px 500px at 50% 110%, rgba(34,211,238,.06), transparent 60%);}
/* nav */
nav{position:sticky;top:0;z-index:50;backdrop-filter:blur(12px);
  background:rgba(255,255,255,.8);border-bottom:1px solid var(--line)}
nav .wrap{display:flex;align-items:center;justify-content:space-between;height:64px}
.logo{font-size:22px;font-weight:800;display:flex;align-items:center;gap:9px;letter-spacing:-.01em}
.logo .brand{background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
.logo .dot{width:10px;height:10px;border-radius:50%;background:var(--grad)}
.nav-r{display:flex;align-items:center;gap:18px;font-size:15px;color:var(--mut)}
.btn{display:inline-flex;align-items:center;gap:8px;border-radius:12px;font-weight:700;
  padding:11px 22px;font-size:15px;cursor:pointer;border:1px solid transparent;transition:.18s;white-space:nowrap}
.btn.primary{background:var(--grad);color:#fff;box-shadow:0 8px 24px rgba(124,58,237,.35)}
.btn.primary:hover{transform:translateY(-2px);box-shadow:0 12px 30px rgba(124,58,237,.5)}
.btn.ghost{background:var(--card2);border-color:var(--line);color:var(--tx)}
.btn.ghost:hover{border-color:#c7cdda;background:#e7ebf3}
.btn.lg{padding:15px 30px;font-size:17px;border-radius:14px}
/* hero */
.hero{padding:72px 0 40px}
.hero-grid{display:grid;grid-template-columns:1fr;gap:48px;align-items:center;max-width:820px}
.badge{display:inline-flex;align-items:center;gap:7px;font-size:13px;font-weight:600;color:#6d4bd8;
  background:rgba(124,58,237,.1);border:1px solid rgba(124,58,237,.28);padding:6px 14px;border-radius:999px;margin-bottom:22px}
.badge .pip{width:7px;height:7px;border-radius:50%;background:#a855f7;box-shadow:0 0 0 4px rgba(168,85,247,.25)}
h1{font-size:54px;line-height:1.14;font-weight:800;letter-spacing:-.02em;margin-bottom:20px}
.lead{font-size:19px;color:var(--mut);margin-bottom:32px;max-width:520px}
.cta{display:flex;gap:14px;flex-wrap:wrap;align-items:center}
.cta .note{font-size:14px;color:var(--dim);margin-left:4px}
.stats{display:flex;gap:30px;margin-top:38px}
.stat .n{font-size:26px;font-weight:800}
.stat .l{font-size:13px;color:var(--dim)}
/* 데모 카드 (input→output) */
.demo-card{background:var(--card);border:1px solid var(--line);border-radius:22px;overflow:hidden;
  box-shadow:0 30px 70px rgba(0,0,0,.5);transform:rotate(.6deg)}
.demo-head{display:flex;align-items:center;gap:7px;padding:13px 16px;border-bottom:1px solid var(--line);background:var(--card2)}
.demo-head .d{width:11px;height:11px;border-radius:50%}
.demo-head .t{margin-left:8px;font-size:13px;color:var(--dim)}
.demo-in{padding:15px 18px;font-size:13.5px;color:#cdd3e0;font-family:ui-monospace,monospace;line-height:1.85;
  border-bottom:1px solid var(--line);background:#10131c;white-space:pre-wrap}
.demo-in b{color:#a855f7}
.demo-cta{display:flex;align-items:center;justify-content:space-between;gap:10px;
  padding:16px 20px;font-size:16px;font-weight:700;color:#fff;background:var(--grad);transition:.18s}
.demo-cta:hover{filter:brightness(1.08)}
.demo-cta b{font-size:18px}
/* sections */
section{padding:64px 0}
.eyebrow{font-size:14px;font-weight:700;color:#a855f7;letter-spacing:.04em;text-align:center;margin-bottom:10px}
h2{font-size:38px;font-weight:800;letter-spacing:-.02em;text-align:center;margin-bottom:14px}
.sub{font-size:17px;color:var(--mut);text-align:center;max-width:620px;margin:0 auto 46px}
.feat{display:grid;grid-template-columns:repeat(4,1fr);gap:20px}
.fcard{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:26px 22px;transition:.18s}
.fcard:hover{transform:translateY(-4px);border-color:rgba(124,58,237,.45);box-shadow:0 14px 34px rgba(20,30,60,.13)}
.fcard .ic{width:48px;height:48px;border-radius:13px;display:grid;place-items:center;font-size:24px;
  background:linear-gradient(135deg,rgba(99,102,241,.25),rgba(168,85,247,.22));margin-bottom:16px}
.fcard h3{font-size:19px;margin-bottom:8px}
.fcard p{font-size:14.5px;color:var(--mut)}
/* steps */
.steps{display:grid;grid-template-columns:repeat(3,1fr);gap:24px;counter-reset:s}
.step{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:30px 26px;position:relative}
.step::before{counter-increment:s;content:counter(s);position:absolute;top:-18px;left:26px;
  width:44px;height:44px;border-radius:13px;background:var(--grad);color:#fff;font-weight:800;font-size:20px;
  display:grid;place-items:center;box-shadow:0 8px 20px rgba(124,58,237,.4)}
.step h3{font-size:20px;margin:14px 0 8px}
.step p{color:var(--mut);font-size:15px}
.step code{background:var(--card2);border:1px solid var(--line);padding:2px 8px;border-radius:6px;font-size:13px;color:#6d4bd8}
/* format */
.fmt{background:var(--card);border:1px solid var(--line);border-radius:20px;padding:34px;max-width:820px;margin:0 auto}
.fmt .row{display:flex;gap:14px;padding:12px 0;border-bottom:1px solid var(--line);align-items:flex-start;font-size:15.5px}
.fmt .row:last-child{border:0}
.fmt .k{flex:0 0 110px;color:#a855f7;font-weight:700}
.fmt code{background:var(--card2);padding:2px 8px;border-radius:6px;font-size:14px;color:var(--mut)}
/* cta band */
.band{background:var(--card);border:1px solid var(--line);border-radius:26px;padding:56px 40px;text-align:center;
  background-image:radial-gradient(500px 240px at 50% -20%,rgba(124,58,237,.2),transparent)}
.band h2{margin-bottom:10px}
.band .sub{margin-bottom:28px}
/* footer */
footer{border-top:1px solid var(--line);padding:30px 0;color:var(--dim);font-size:14px}
footer .wrap{display:flex;justify-content:space-between;flex-wrap:wrap;gap:12px}
footer a{color:var(--mut)}
@media(max-width:900px){
  .hero-grid{grid-template-columns:1fr;gap:36px} h1{font-size:40px}
  .feat{grid-template-columns:repeat(2,1fr)} .steps{grid-template-columns:1fr}
  .demo-card{transform:none}
}
@media(max-width:560px){.feat{grid-template-columns:1fr} h1{font-size:33px} h2{font-size:29px}}
</style></head><body>

<nav><div class="wrap">
  <div class="logo"><span class="dot"></span><span class="brand">AI Storyboard</span></div>
  <div class="nav-r">
    <a href="https://github.com/brhoyoung2/storyboard" target="_blank">GitHub</a>
    <a href="viewer.html">뷰어</a>
    <a class="btn primary" href="viewer.html#gen">✎ 직접 생성</a>
  </div>
</div></nav>

<header class="hero"><div class="wrap"><div class="hero-grid">
  <div>
    <div class="badge"><span class="pip"></span> 설치 없음 · 브라우저에서 바로</div>
    <h1>글 콘티를 쓰면,<br><span class="grad-tx">그림 콘티가 완성</span>됩니다.</h1>
    <p class="lead">텍스트 콘티만 입력하면 손그림 스타일 그림콘티를 <b>SVG</b>로 즉시 생성합니다.
      캐릭터·포즈·표정·시점·말풍선·배경까지 자동으로.</p>
    <div class="cta">
      <a class="btn primary lg" href="viewer.html#gen">✎ 지금 생성하기</a>
      <a class="btn ghost lg" href="viewer.html">결과 둘러보기</a>
    </div>
  </div>
</div></div></header>

<section><div class="wrap">
  <div class="eyebrow">FEATURES</div>
  <h2>콘티에 필요한 걸, 전부 자동으로</h2>
  <p class="sub">글로 적은 연출을 그대로 그림으로. 손으로 그릴 필요 없이 배치·표정·동작이 채워집니다.</p>
  <div class="feat">
    <div class="fcard"><div class="ic">✏️</div><h3>손그림 콘티 스타일</h3><p>연필 떨림 필터와 손글씨 폰트로 진짜 러프 콘티 느낌.</p></div>
    <div class="fcard"><div class="ic">🧍</div><h3>캐릭터 자동</h3><p>이름·성별 인식, 관절 바디로 30종 포즈와 22종 표정.</p></div>
    <div class="fcard"><div class="ic">💬</div><h3>연출 요소</h3><p>대사 말풍선·속마음·나레이션·효과음·배경까지.</p></div>
    <div class="fcard"><div class="ic">⬇️</div><h3>SVG로 저장</h3><p>벡터라 깨지지 않음. 흑백/컬러 전환, 바로 다운로드.</p></div>
  </div>
</div></section>

<section><div class="wrap">
  <div class="eyebrow">HOW IT WORKS</div>
  <h2>3단계면 끝</h2>
  <p class="sub">평소 쓰던 글콘티 형식 그대로 붙여넣기만 하면 됩니다.</p>
  <div class="steps" style="margin-top:40px">
    <div class="step"><h3>글콘티 입력</h3><p><code>번호. [샷] 묘사 / 화자: "대사"</code> 형식으로 쓰거나 붙여넣기.</p></div>
    <div class="step"><h3>생성 클릭</h3><p>[✎ 생성]을 누르면 컷마다 인물·포즈·말풍선이 배치됩니다.</p></div>
    <div class="step"><h3>SVG 완성</h3><p>오른쪽에 세로 웹툰 스트립으로. <code>SVG 저장</code>으로 다운로드.</p></div>
  </div>
</div></section>

<section><div class="wrap">
  <div class="eyebrow">FORMAT</div>
  <h2>입력 형식</h2>
  <p class="sub">규칙은 한 줄이면 충분합니다.</p>
  <div class="fmt">
    <div class="row"><div class="k">기본</div><div><code>번호. [샷] 상황묘사 / 화자: "대사"</code></div></div>
    <div class="row"><div class="k">샷</div><div><code>풀샷</code> · <code>미들샷</code> · <code>클로즈업</code> · <code>롱샷</code></div></div>
    <div class="row"><div class="k">인물</div><div>이름(매리·라이더·엘리·무결…) → 색·성별 자동 · 일반어 <code>여자</code>/<code>남자</code>도 인식</div></div>
    <div class="row"><div class="k">인원</div><div><code>둘</code>/<code>서로</code> → 2명 · <code>사람들</code> → 다인물</div></div>
    <div class="row"><div class="k">말풍선</div><div><code>"대사"</code> → 말풍선 · <code>(속마음)</code> → 생각풍선 · <code>나레이션:</code> → 하단 박스 · <code>효과음:</code> → 손글씨</div></div>
  </div>
</div></section>

<section><div class="wrap"><div class="band">
  <div class="eyebrow">START NOW</div>
  <h2>지금 바로, 콘티를 그려보세요</h2>
  <p class="sub" style="margin-left:auto;margin-right:auto">로그인도 설치도 필요 없습니다. 글만 쓰면 됩니다.</p>
  <a class="btn primary lg" href="viewer.html#gen">✎ 무료로 생성하기</a>
</div></div></section>

<footer><div class="wrap">
  <div>© AI Storyboard · 텍스트 콘티를 그림 콘티로</div>
  <div><a href="viewer.html">뷰어</a> &nbsp;·&nbsp; <a href="https://github.com/brhoyoung2/storyboard" target="_blank">GitHub</a></div>
</div></footer>

</body></html>"""


def main():
    html = PAGE.replace("__EXAMPLE_TEXT__", esc(EXAMPLE))
    (ROOT / "output" / "index.html").write_text(html, encoding="utf-8")
    print("✓ output/index.html (서비스 랜딩, 고딕 로고 · 데모 입력만)")


if __name__ == "__main__":
    main()
