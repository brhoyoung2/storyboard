# -*- coding: utf-8 -*-
"""
글콘티 → 그림콘티 SVG 렌더러 (4~5번 단계, PoC)

설계 원칙:
  분류기/LLM = 배치 '값'만 결정(샷·인물·표정·시선·말풍선) →
  이 결정론적 렌더러가 SVG를 그린다.

구성:
  - 캐릭터 에셋: 파라메트릭(머리/몸 + 표정 슬롯 + 시선)
  - 샷 프레이밍: 카메라 거리 → 캔버스 박스 + 인물 스케일/크롭
  - 구도 템플릿: single / two_shot
  - 말풍선(dialogue/inner/narration) + 효과음 레터링
  - 손그림 느낌: feTurbulence displacement(연필 떨림) + 블루 라인

출력: output/*.svg  (세로 웹툰 스트립 + 유형 샘플 시트)
"""
import json
import math
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
CLS_DIR = ROOT / "data" / "classified"
OUT_DIR = ROOT / "output"

# ---- 스타일 토큰 ----------------------------------------------------------
# SKETCH=True : 채움을 모두 흰색으로 → 러프한 선 스케치 느낌 (색 없는 콘티)
SKETCH = True
W = 720                       # 웹툰 패널 폭
INK = "#3a3a3a" if SKETCH else "#2f5d8a"   # 스케치=짙은 연필선 / 컬러=블루
INK2 = "#9a9a9a" if SKETCH else "#5b8bbf"
NOTE = "#c0392b"             # 연출 메모(빨강)
SFX_FILL = "#ffffff" if SKETCH else "#9bbbd8"
PANEL_BG = "#ffffff"


def PAINT(c):
    """채움색 — 스케치 모드면 흰색으로."""
    return "#ffffff" if SKETCH else c
FONT = "'Nanum Pen Script','Gulim','Malgun Gothic',sans-serif"

# 샷 프레이밍: 패널 높이 + 인물 head 반지름 + head 중심 y비율
SHOT_FRAME = {
    "extreme_closeup": dict(h=520, head_r=170, head_cy=0.50, body="none"),
    "closeup":         dict(h=520, head_r=120, head_cy=0.42, body="bust"),
    "medium":          dict(h=480, head_r=82,  head_cy=0.24, body="waist"),
    "full":            dict(h=820, head_r=58,  head_cy=0.12, body="full"),
    "long":            dict(h=680, head_r=34,  head_cy=0.10, body="full"),
    "insert":          dict(h=440, head_r=0,   head_cy=0.0,  body="none"),
    "sd":              dict(h=460, head_r=85,  head_cy=0.30, body="chibi"),
    "title":           dict(h=400, head_r=0,   head_cy=0.0,  body="none"),
    "unspecified":     dict(h=480, head_r=80,  head_cy=0.25, body="waist"),
}

# 캐릭터 레지스트리: hair 스타일·색, accent(의상색), gender, glasses, outfit
SKIN = "#ffffff" if SKETCH else "#fff3ea"
CHARS = {
    # 풀하우스
    "엘리":   dict(hair="updo",    hairc="#5b4636", accent="#d65a7a", gender="F", outfit="dress"),
    "라이더": dict(hair="swept",   hairc="#33312f", accent="#3f7fb0", gender="M", outfit="shirt"),
    "민준석": dict(hair="slick",   hairc="#201d1b", accent="#3b3f4a", gender="M", outfit="suit", glasses=True),
    # 매리는 외박중
    "매리":   dict(hair="long",    hairc="#6a4326", accent="#e08a3c", gender="F", outfit="hoodie"),
    "무결":   dict(hair="medium",  hairc="#262320", accent="#5fa0a0", gender="M", outfit="shirt"),
    "정인":   dict(hair="short",   hairc="#4a3520", accent="#8a6a40", gender="M", outfit="jacket"),
    "신성우": dict(hair="swept",   hairc="#2a2622", accent="#7a5a8a", gender="M", outfit="shirt"),
    "하은":   dict(hair="ponytail",hairc="#3a2c20", accent="#e0a0b0", gender="F", outfit="dress"),
    "주태경": dict(hair="slick",   hairc="#1e1b18", accent="#444a52", gender="M", outfit="suit"),
}
DEFAULT_CHAR = dict(hair="short", hairc="#555", accent="#8a9aa8", gender="M", outfit="shirt")
# 이름 없는 일반 인물(성별 단어로만 판단될 때)
DEFAULT_MALE = dict(hair="short", hairc="#4a4a4a", accent="#8a9aa8", gender="M", outfit="shirt")
DEFAULT_FEMALE = dict(hair="long", hairc="#5a4636", accent="#c98aa0", gender="F", outfit="dress")

# 이름 기반 성별 예측 (레지스트리 우선, 그 외 알려진 이름)
FEMALE_NAMES = {"엘리", "매리", "하은", "루나", "수아", "지은", "유나", "서연", "민지", "은비", "소희"}
MALE_NAMES = {"라이더", "무결", "정인", "신성우", "주태경", "민준석", "이한", "찬", "태경", "성우", "준석"}


def predict_gender(name):
    if not name:
        return "M"
    if name in CHARS:
        return CHARS[name].get("gender", "M")
    if name in FEMALE_NAMES:
        return "F"
    if name in MALE_NAMES:
        return "M"
    return "M"


def esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---- 머리 형태(턱선 있는 얼굴) + 귀 ---------------------------------------
def head_shape(cx, cy, r, sw, view="front", facing=0.0, male=False):
    st = f'fill="{SKIN}" stroke="{INK}" stroke-width="{sw:.1f}" stroke-linejoin="round"'
    d = 1 if facing >= 0 else -1
    if view == "profile":
        # 완측면 실루엣. d=+1 오른쪽을 봄. 남=코/턱 돌출·각짐, 여=작은 코(살짝 들림)·둥근 턱.
        X = lambda v: cx + d*v*r
        Y = lambda v: cy + v*r
        nose = 1.12 if male else 0.94           # 코 돌출(남 큼, 여 작음)
        nose_y = 0.18 if male else 0.06         # 코끝 높이(여=살짝 들림)
        chin_x = 0.10 if male else -0.08        # 턱 전후(남=앞, 여=들어감)
        chin_y = 1.13 if male else 1.02
        jaw_x = 0.74 if male else 0.52          # 턱선 강도(남=각짐)
        lip_y = 0.58
        p = (f'M{X(-0.85):.1f},{Y(-0.5):.1f} '
             f'C{X(-0.95):.1f},{Y(-1.05):.1f} {X(0.45):.1f},{Y(-1.12):.1f} {X(0.72):.1f},{Y(-0.5):.1f} '       # 뒤통수~정수리~이마
             f'C{X(0.80):.1f},{Y(-0.20):.1f} {X(0.74):.1f},{Y(nose_y-0.18):.1f} {X(nose):.1f},{Y(nose_y):.1f} '  # 이마~콧대~코끝
             f'L{X(0.80):.1f},{Y(0.30):.1f} '                                                                   # 코밑(인중)
             f'C{X(0.93):.1f},{Y(0.46):.1f} {X(0.86):.1f},{Y(lip_y-0.04):.1f} {X(0.78):.1f},{Y(lip_y):.1f} '     # 입술
             f'C{X(jaw_x):.1f},{Y(0.94):.1f} {X(0.40):.1f},{Y(chin_y):.1f} {X(chin_x):.1f},{Y(chin_y):.1f} '     # 턱
             f'C{X(-0.45):.1f},{Y(0.98):.1f} {X(-0.85):.1f},{Y(0.72):.1f} {X(-0.85):.1f},{Y(-0.5):.1f} Z')       # 턱뒤~목
        ear = f'<path d="M{X(-0.08):.1f},{Y(0.0):.1f} q{-d*r*0.14:.1f},{r*0.05:.1f} 0,{r*0.26:.1f}" fill="{SKIN}" stroke="{INK}" stroke-width="{sw:.1f}"/>'
        return f'<path d="{p}" {st}/>' + ear
    # 정면/3-4: 타원+턱. male=각진 턱(넓고 짧음), female=둥근 턱(좁고 김)
    sx = facing * r * 0.10 if view == "q3" else 0.0
    rw, top = (r*1.0 if male else r*0.95), cy - r
    chin = cy + (r*1.06 if male else r*1.18)
    jw = 0.74 if male else 0.46          # 턱 넓이(클수록 각짐)
    jdrop = 0.78 if male else 0.62       # 턱선 시작 높이
    rwL = rw*(1.12 if (view == "q3" and facing < 0) else 1.0)
    rwR = rw*(1.12 if (view == "q3" and facing > 0) else 1.0)
    ears = (f'<path d="M{cx-rwL:.1f},{cy-r*0.05:.1f} q{-r*0.16:.1f},{r*0.06:.1f} 0,{r*0.28:.1f}" '
            f'fill="{SKIN}" stroke="{INK}" stroke-width="{sw:.1f}"/>'
            f'<path d="M{cx+rwR:.1f},{cy-r*0.05:.1f} q{r*0.16:.1f},{r*0.06:.1f} 0,{r*0.28:.1f}" '
            f'fill="{SKIN}" stroke="{INK}" stroke-width="{sw:.1f}"/>')
    if male:
        # 각진 턱: 옆선 수직으로 내려와 짧은 직선 턱
        head = (f'<path d="M{cx-rwL:.1f},{cy:.1f} '
                f'C{cx-rwL:.1f},{top:.1f} {cx+rwR:.1f},{top:.1f} {cx+rwR:.1f},{cy:.1f} '
                f'C{cx+rwR:.1f},{cy+r*jdrop:.1f} {cx+rwR*jw:.1f},{chin-r*0.04:.1f} {cx+rwR*jw*0.55+sx:.1f},{chin:.1f} '
                f'L{cx-rwL*jw*0.55+sx:.1f},{chin:.1f} '
                f'C{cx-rwR*jw:.1f},{chin-r*0.04:.1f} {cx-rwL:.1f},{cy+r*jdrop:.1f} {cx-rwL:.1f},{cy-r*0.16:.1f}" {st}/>')  # 살짝 열림(좌측 틈)
    else:
        head = (f'<path d="M{cx-rwL:.1f},{cy:.1f} '
                f'C{cx-rwL:.1f},{top:.1f} {cx+rwR:.1f},{top:.1f} {cx+rwR:.1f},{cy:.1f} '
                f'C{cx+rwR:.1f},{cy+r*jdrop:.1f} {cx+rwR*jw:.1f},{chin-r*0.08:.1f} {cx+sx:.1f},{chin:.1f} '
                f'C{cx-rwL*jw:.1f},{chin-r*0.08:.1f} {cx-rwL:.1f},{cy+r*jdrop:.1f} {cx-rwL:.1f},{cy-r*0.16:.1f}" {st}/>')  # 살짝 열림
    return ears + head


def _open_eye(ex, ey, r, look, lid=0.0, lash=False, sw=1.5):
    """웹툰형 눈: 흰자+동공+하이라이트+윗꺼풀."""
    ew, eh = r*0.20, r*0.24*(1-lid*0.6)
    px = ex + look*ew*0.4
    st = f'stroke="{INK}" stroke-width="{sw:.1f}" fill="none" stroke-linecap="round"'
    nf = f'stroke="{INK}" stroke-width="{sw:.1f}" stroke-linecap="round"'  # fill 없는 stroke
    s = (f'<ellipse cx="{ex:.1f}" cy="{ey:.1f}" rx="{ew:.1f}" ry="{eh:.1f}" fill="white" {nf}/>'
         f'<circle cx="{px:.1f}" cy="{ey+eh*0.12:.1f}" r="{eh*0.55:.1f}" fill="{INK}"/>'
         f'<circle cx="{px-eh*0.18:.1f}" cy="{ey-eh*0.12:.1f}" r="{eh*0.16:.1f}" fill="white"/>'
         f'<path d="M{ex-ew:.1f},{ey-eh*0.7:.1f} Q{ex:.1f},{ey-eh*1.25:.1f} {ex+ew:.1f},{ey-eh*0.7:.1f}" stroke="{INK}" stroke-width="{sw*1.2:.1f}" fill="none"/>')
    if lash:
        s += f'<path d="M{ex+ew:.1f},{ey-eh*0.5:.1f} l{r*0.07:.1f},{-r*0.05:.1f}" {st}/>'
    return s


def _brow(bx, by, r, kind, sw, male=False):
    bw = sw*(1.9 if male else 1.05)          # 남성 눈썹 두껍게
    st = f'stroke="{INK}" stroke-width="{bw:.1f}" fill="none" stroke-linecap="round"'
    w = r*(0.20 if male else 0.18)
    if kind == "down_in":
        return f'<path d="M{bx-w:.1f},{by-r*0.04:.1f} L{bx+w:.1f},{by+r*0.10:.1f}" {st}/>'
    if kind == "up_in":
        return f'<path d="M{bx-w:.1f},{by+r*0.08:.1f} L{bx+w:.1f},{by-r*0.04:.1f}" {st}/>'
    if kind == "raise":
        return f'<path d="M{bx-w:.1f},{by-r*0.10:.1f} Q{bx:.1f},{by-r*0.20:.1f} {bx+w:.1f},{by-r*0.10:.1f}" {st}/>'
    if male:                                  # 남성 기본: 곧은 일자 눈썹
        return f'<path d="M{bx-w:.1f},{by:.1f} L{bx+w:.1f},{by+r*0.01:.1f}" {st}/>'
    return f'<path d="M{bx-w:.1f},{by:.1f} Q{bx:.1f},{by-r*0.06:.1f} {bx+w:.1f},{by:.1f}" {st}/>'


def _profile_face(cx, cy, r, expr, facing, gender, glasses):
    """완측면 얼굴: 앞쪽(facing) 가장자리에 눈 하나 + 눈썹 + 입. 코는 머리 실루엣에."""
    d = 1 if facing >= 0 else -1
    male = (gender != "F")
    sw = max(1.4, r * 0.028)
    st = f'stroke="{INK}" stroke-width="{sw:.1f}" fill="none" stroke-linecap="round"'
    ex = cx + d*r*0.46
    ey = cy + r*0.06
    by = ey - r*0.30
    my = cy + r*0.56
    mx = cx + d*r*0.58
    s = []
    bk = {"angry": "down_in", "sad": "up_in", "crying": "up_in",
          "surprise": "raise", "shock": "raise", "flustered": "raise",
          "dumbfound": "raise", "smile": "up", "happy": "up"}.get(expr, "flat")
    # 눈썹(앞쪽만, 짧게, 성별 반영)
    s.append(_brow(ex, by, r*0.7, bk, sw, male))
    # 눈 (측면이라 좁은 아몬드형)
    if expr in ("smile", "happy"):
        s.append(f'<path d="M{ex-r*0.1:.1f},{ey:.1f} Q{ex:.1f},{ey-r*0.14:.1f} {ex+r*0.12:.1f},{ey:.1f}" {st}/>')
    elif expr in ("thinking", "serious"):
        s.append(f'<path d="M{ex-r*0.1:.1f},{ey:.1f} L{ex+r*0.12:.1f},{ey:.1f}" {st}/>')
    else:
        ew = r*(0.15 if expr in ("surprise", "shock") else 0.11)
        nf = f'stroke="{INK}" stroke-width="{sw:.1f}" stroke-linecap="round"'
        # 측면 눈: 앞(코쪽)이 뾰족한 삼각형 느낌
        s.append(f'<path d="M{ex-r*0.11:.1f},{ey:.1f} Q{ex:.1f},{ey-ew:.1f} {ex+d*r*0.13:.1f},{ey-r*0.01:.1f} '
                 f'Q{ex:.1f},{ey+ew:.1f} {ex-r*0.11:.1f},{ey:.1f} Z" fill="white" {nf}/>'
                 f'<circle cx="{ex+d*r*0.03:.1f}" cy="{ey:.1f}" r="{ew*0.55:.1f}" fill="{INK}"/>')
        if not male:   # 여성 속눈썹/윗라인
            s.append(f'<path d="M{ex+d*r*0.13:.1f},{ey-r*0.02:.1f} l{d*r*0.06:.1f},{-r*0.04:.1f}" {st}/>')
    # 입(앞 가장자리 짧게)
    if expr in ("smile", "happy"):
        s.append(f'<path d="M{mx-d*r*0.16:.1f},{my:.1f} Q{mx:.1f},{my+r*0.14:.1f} {mx+d*r*0.05:.1f},{my-r*0.02:.1f}" {st}/>')
    elif expr in ("sad", "crying"):
        s.append(f'<path d="M{mx-d*r*0.14:.1f},{my+r*0.05:.1f} Q{mx:.1f},{my-r*0.06:.1f} {mx+d*r*0.05:.1f},{my+r*0.03:.1f}" {st}/>')
        if expr == "crying":
            s.append(f'<path d="M{ex:.1f},{ey+r*0.12:.1f} q0,{r*0.35:.1f} {-d*r*0.04:.1f},{r*0.42:.1f}" {st}/>')
    elif expr in ("surprise", "shock"):
        s.append(f'<ellipse cx="{mx:.1f}" cy="{my:.1f}" rx="{r*0.08:.1f}" ry="{r*0.12:.1f}" fill="{PAINT('#7a4a4a')}" stroke="{INK}" stroke-width="{sw:.1f}"/>')
    else:
        s.append(f'<path d="M{mx-d*r*0.14:.1f},{my:.1f} L{mx+d*r*0.04:.1f},{my:.1f}" {st}/>')
    if glasses:
        s.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="{r*0.2:.1f}" {st}/>')
    return "".join(s)


def _blush(cx, cy, r, ox=0.0):
    if SKETCH:   # 러프 스케치엔 볼터치 생략(흰색 무의미)
        return (f'<path d="M{cx-r*0.66+ox:.1f},{cy+r*0.36:.1f} l{r*0.18:.1f},0 M{cx-r*0.6+ox:.1f},{cy+r*0.46:.1f} l{r*0.16:.1f},0" stroke="{INK2}" stroke-width="{max(1.2,r*0.02):.1f}" fill="none" stroke-linecap="round"/>'
                f'<path d="M{cx+r*0.48+ox:.1f},{cy+r*0.36:.1f} l{r*0.18:.1f},0 M{cx+r*0.44+ox:.1f},{cy+r*0.46:.1f} l{r*0.16:.1f},0" stroke="{INK2}" stroke-width="{max(1.2,r*0.02):.1f}" fill="none" stroke-linecap="round"/>')
    return (f'<ellipse cx="{cx-r*0.55+ox:.1f}" cy="{cy+r*0.4:.1f}" rx="{r*0.18:.1f}" ry="{r*0.11:.1f}" fill="#f6a6b2" opacity="0.6" stroke="none"/>'
            f'<ellipse cx="{cx+r*0.55+ox:.1f}" cy="{cy+r*0.4:.1f}" rx="{r*0.18:.1f}" ry="{r*0.11:.1f}" fill="#f6a6b2" opacity="0.6" stroke="none"/>')


def _heart(x, y, s):
    return (f'<path d="M{x:.1f},{y+s*0.35:.1f} C{x-s:.1f},{y-s*0.35:.1f} {x-s*0.35:.1f},{y-s:.1f} {x:.1f},{y-s*0.45:.1f} '
            f'C{x+s*0.35:.1f},{y-s:.1f} {x+s:.1f},{y-s*0.35:.1f} {x:.1f},{y+s*0.35:.1f} Z" '
            f'fill="{PAINT("#e8516b")}" stroke="{INK if SKETCH else "none"}" stroke-width="{1.4 if SKETCH else 0}"/>')


def _sweat(x, y, r, sw):
    return f'<path d="M{x:.1f},{y:.1f} q{-r*0.1:.1f},{r*0.18:.1f} 0,{r*0.3:.1f} q{r*0.1:.1f},{-r*0.12:.1f} 0,{-r*0.3:.1f}" fill="{INK2}" stroke="none"/>'


# ---- 표정 슬롯 (눈썹·웹툰눈·코·입) -----------------------------------------
def face(cx, cy, r, expr, facing=0.0, gender="M", glasses=False, view="front"):
    if view == "profile":
        return _profile_face(cx, cy, r, expr, facing, gender, glasses)
    male = (gender != "F")
    ox = facing * r * (0.28 if view == "q3" else 0.12)
    look = facing
    ex = r * 0.36
    eye_y = cy + r * 0.02
    brow_y = eye_y - r*(0.26 if male else 0.34)     # 남성 눈썹 눈에 가깝게(낮게)
    el, er_ = cx - ex + ox, cx + ex + ox
    bl, br_ = cx - ex + ox, cx + ex + ox
    sw = max(1.4, r * 0.028)
    lash = (gender == "F")
    s = []

    def stroke():
        return f'stroke="{INK}" stroke-width="{sw:.1f}" fill="none" stroke-linecap="round"'

    my = cy + r * 0.58
    nose = f'<path d="M{cx-r*0.03+ox:.1f},{cy+r*0.22:.1f} l{-r*0.06:.1f},{r*0.12:.1f} l{r*0.10:.1f},0" {stroke()}/>'
    bk = "flat"
    mouth = ""

    if expr in ("smile", "happy"):
        bk = "up"
        s.append(f'<path d="M{el-r*0.18:.1f},{eye_y:.1f} Q{el:.1f},{eye_y-r*0.20:.1f} {el+r*0.18:.1f},{eye_y:.1f}" {stroke()}/>'
                 f'<path d="M{er_-r*0.18:.1f},{eye_y:.1f} Q{er_:.1f},{eye_y-r*0.20:.1f} {er_+r*0.18:.1f},{eye_y:.1f}" {stroke()}/>')
        mouth = f'<path d="M{cx-r*0.26+ox:.1f},{my-r*0.04:.1f} Q{cx+ox:.1f},{my+r*0.26:.1f} {cx+r*0.26+ox:.1f},{my-r*0.04:.1f}" {stroke()}/>'
    elif expr in ("surprise", "shock"):
        bk = "raise"
        s.append(_open_eye(el, eye_y, r*1.12, look, lash=lash, sw=sw) + _open_eye(er_, eye_y, r*1.12, look, lash=lash, sw=sw))
        mouth = f'<ellipse cx="{cx+ox:.1f}" cy="{my+r*0.04:.1f}" rx="{r*0.13:.1f}" ry="{r*0.18:.1f}" fill="{PAINT('#7a4a4a')}" stroke="{INK}" stroke-width="{sw:.1f}" stroke-linecap="round"/>'
        if expr == "shock":
            s.append(f'<path d="M{cx+r*0.62:.1f},{cy-r*0.55:.1f} l{r*0.14:.1f},{-r*0.2:.1f} M{cx+r*0.8:.1f},{cy-r*0.42:.1f} l{r*0.18:.1f},{-r*0.1:.1f}" {stroke()}/>')
    elif expr == "angry":
        bk = "down_in"
        s.append(_open_eye(el, eye_y, r, look, lid=0.2, sw=sw) + _open_eye(er_, eye_y, r, look, lid=0.2, sw=sw))
        mouth = f'<path d="M{cx-r*0.22+ox:.1f},{my+r*0.10:.1f} Q{cx+ox:.1f},{my-r*0.04:.1f} {cx+r*0.22+ox:.1f},{my+r*0.10:.1f}" {stroke()}/>'
        s.append(f'<path d="M{cx+r*0.58:.1f},{cy-r*0.55:.1f} l{r*0.2:.1f},{r*0.05:.1f} M{cx+r*0.62:.1f},{cy-r*0.4:.1f} l{r*0.2:.1f},0" {stroke()}/>')
    elif expr in ("sad", "crying"):
        bk = "up_in"
        s.append(f'<path d="M{el-r*0.16:.1f},{eye_y+r*0.05:.1f} Q{el:.1f},{eye_y-r*0.12:.1f} {el+r*0.16:.1f},{eye_y+r*0.05:.1f}" {stroke()}/>'
                 f'<path d="M{er_-r*0.16:.1f},{eye_y+r*0.05:.1f} Q{er_:.1f},{eye_y-r*0.12:.1f} {er_+r*0.16:.1f},{eye_y+r*0.05:.1f}" {stroke()}/>')
        mouth = f'<path d="M{cx-r*0.18+ox:.1f},{my+r*0.08:.1f} Q{cx+ox:.1f},{my-r*0.08:.1f} {cx+r*0.18+ox:.1f},{my+r*0.08:.1f}" {stroke()}/>'
        if expr == "crying":
            s.append(f'<path d="M{el:.1f},{eye_y+r*0.14:.1f} q{-r*0.04:.1f},{r*0.3:.1f} 0,{r*0.44:.1f}" {stroke()}/>'
                     f'<path d="M{er_:.1f},{eye_y+r*0.14:.1f} q{r*0.04:.1f},{r*0.3:.1f} 0,{r*0.44:.1f}" {stroke()}/>')
    elif expr in ("thinking", "serious"):
        bk = "flat"
        s.append(_open_eye(el, eye_y, r, look, lid=0.35, sw=sw) + _open_eye(er_, eye_y, r, look, lid=0.35, sw=sw))
        mouth = f'<path d="M{cx-r*0.16+ox:.1f},{my:.1f} L{cx+r*0.16+ox:.1f},{my:.1f}" {stroke()}/>'
    elif expr in ("flustered", "dumbfound"):
        bk = "raise"
        s.append(_open_eye(el, eye_y, r, look, lid=0.5, sw=sw) + _open_eye(er_, eye_y, r, look, sw=sw))
        mouth = f'<path d="M{cx-r*0.16+ox:.1f},{my+r*0.05:.1f} Q{cx+r*0.05+ox:.1f},{my-r*0.04:.1f} {cx+r*0.18+ox:.1f},{my+r*0.07:.1f}" {stroke()}/>'
        if expr == "flustered":
            s.append(_sweat(cx-r*0.7, cy-r*0.15, r, sw))
    elif expr == "love":
        bk = "up"
        s.append(_heart(el, eye_y, r*0.2) + _heart(er_, eye_y, r*0.2))
        s.append(_blush(cx, cy, r, ox))
        mouth = f'<path d="M{cx-r*0.22+ox:.1f},{my-r*0.02:.1f} Q{cx+ox:.1f},{my+r*0.24:.1f} {cx+r*0.22+ox:.1f},{my-r*0.02:.1f}" {stroke()}/>'
    elif expr == "wink":
        bk = "up"
        # 한쪽 감음(앞쪽 눈), 반대쪽 뜸
        s.append(f'<path d="M{er_-r*0.18:.1f},{eye_y:.1f} Q{er_:.1f},{eye_y-r*0.20:.1f} {er_+r*0.18:.1f},{eye_y:.1f}" {stroke()}/>')
        s.append(_open_eye(el, eye_y, r, look, lash=lash, sw=sw))
        mouth = f'<path d="M{cx-r*0.2+ox:.1f},{my-r*0.02:.1f} Q{cx+r*0.06+ox:.1f},{my+r*0.2:.1f} {cx+r*0.22+ox:.1f},{my-r*0.04:.1f}" {stroke()}/>'
    elif expr == "laugh":
        bk = "up"
        s.append(f'<path d="M{el-r*0.18:.1f},{eye_y-r*0.02:.1f} Q{el:.1f},{eye_y-r*0.24:.1f} {el+r*0.18:.1f},{eye_y-r*0.02:.1f}" {stroke()}/>'
                 f'<path d="M{er_-r*0.18:.1f},{eye_y-r*0.02:.1f} Q{er_:.1f},{eye_y-r*0.24:.1f} {er_+r*0.18:.1f},{eye_y-r*0.02:.1f}" {stroke()}/>')
        mouth = f'<path d="M{cx-r*0.3+ox:.1f},{my-r*0.08:.1f} Q{cx+ox:.1f},{my+r*0.42:.1f} {cx+r*0.3+ox:.1f},{my-r*0.08:.1f} Q{cx+ox:.1f},{my+r*0.12:.1f} {cx-r*0.3+ox:.1f},{my-r*0.08:.1f} Z" fill="{PAINT('#7a4a4a')}" stroke="{INK}" stroke-width="{sw:.1f}" stroke-linecap="round"/>'
    elif expr == "smirk":
        bk = "raise"
        s.append(_open_eye(el, eye_y, r, look, lid=0.3, sw=sw) + _open_eye(er_, eye_y, r, look, lid=0.3, sw=sw))
        mouth = f'<path d="M{cx-r*0.22+ox:.1f},{my+r*0.06:.1f} Q{cx+r*0.05+ox:.1f},{my+r*0.04:.1f} {cx+r*0.24+ox:.1f},{my-r*0.1:.1f}" {stroke()}/>'
    elif expr == "smug":
        bk = "up"
        s.append(f'<path d="M{el-r*0.16:.1f},{eye_y+r*0.04:.1f} Q{el:.1f},{eye_y-r*0.06:.1f} {el+r*0.16:.1f},{eye_y+r*0.04:.1f}" {stroke()}/>'
                 f'<path d="M{er_-r*0.16:.1f},{eye_y+r*0.04:.1f} Q{er_:.1f},{eye_y-r*0.06:.1f} {er_+r*0.16:.1f},{eye_y+r*0.04:.1f}" {stroke()}/>')
        mouth = f'<path d="M{cx-r*0.2+ox:.1f},{my-r*0.02:.1f} Q{cx+ox:.1f},{my+r*0.14:.1f} {cx+r*0.2+ox:.1f},{my-r*0.02:.1f}" {stroke()}/>'
    elif expr == "tired":
        bk = "up_in"
        s.append(_open_eye(el, eye_y, r, look, lid=0.62, sw=sw) + _open_eye(er_, eye_y, r, look, lid=0.62, sw=sw))
        s.append(f'<path d="M{el-r*0.12:.1f},{eye_y+r*0.16:.1f} q{r*0.12:.1f},{r*0.06:.1f} {r*0.24:.1f},0" {stroke()}/>'
                 f'<path d="M{er_-r*0.12:.1f},{eye_y+r*0.16:.1f} q{r*0.12:.1f},{r*0.06:.1f} {r*0.24:.1f},0" {stroke()}/>')  # 다크서클
        mouth = f'<path d="M{cx-r*0.14+ox:.1f},{my+r*0.02:.1f} L{cx+r*0.14+ox:.1f},{my-r*0.02:.1f}" {stroke()}/>'
    elif expr == "worried":
        bk = "up_in"
        s.append(_open_eye(el, eye_y, r, look, lid=0.2, sw=sw) + _open_eye(er_, eye_y, r, look, lid=0.2, sw=sw))
        s.append(_sweat(cx+r*0.66, cy-r*0.15, r, sw))
        mouth = f'<path d="M{cx-r*0.16+ox:.1f},{my+r*0.04:.1f} Q{cx+r*0.04+ox:.1f},{my-r*0.04:.1f} {cx-r*0.02+ox:.1f},{my+r*0.06:.1f} Q{cx+r*0.1+ox:.1f},{my+r*0.12:.1f} {cx+r*0.16+ox:.1f},{my+r*0.02:.1f}" {stroke()}/>'
    elif expr == "scared":
        bk = "up_in"
        s.append(_open_eye(el, eye_y, r*1.1, look, sw=sw) + _open_eye(er_, eye_y, r*1.1, look, sw=sw))
        s.append(_sweat(cx-r*0.66, cy-r*0.1, r, sw))
        s.append(f'<path d="M{cx+r*0.5:.1f},{cy-r*0.55:.1f} l{r*0.12:.1f},{-r*0.16:.1f} M{cx+r*0.64:.1f},{cy-r*0.5:.1f} l{r*0.14:.1f},{-r*0.08:.1f}" {stroke()}/>')
        mouth = f'<path d="M{cx-r*0.16+ox:.1f},{my+r*0.04:.1f} q{r*0.05:.1f},{-r*0.08:.1f} {r*0.1:.1f},0 q{r*0.05:.1f},{r*0.08:.1f} {r*0.1:.1f},0 q{r*0.05:.1f},{-r*0.08:.1f} {r*0.1:.1f},0" {stroke()}/>'
    elif expr == "pain":
        bk = "down_in"
        s.append(f'<path d="M{el-r*0.16:.1f},{eye_y-r*0.1:.1f} L{el+r*0.16:.1f},{eye_y+r*0.06:.1f} M{el-r*0.16:.1f},{eye_y+r*0.06:.1f} L{el+r*0.16:.1f},{eye_y-r*0.1:.1f}" {stroke()}/>'
                 f'<path d="M{er_-r*0.16:.1f},{eye_y-r*0.1:.1f} L{er_+r*0.16:.1f},{eye_y+r*0.06:.1f} M{er_-r*0.16:.1f},{eye_y+r*0.06:.1f} L{er_+r*0.16:.1f},{eye_y-r*0.1:.1f}" {stroke()}/>')  # >< 질끈
        mouth = f'<path d="M{cx-r*0.22+ox:.1f},{my:.1f} l{r*0.11:.1f},{-r*0.1:.1f} l{r*0.11:.1f},{r*0.1:.1f} l{r*0.11:.1f},{-r*0.1:.1f} l{r*0.11:.1f},{r*0.1:.1f}" {stroke()}/>'  # 악문 이
    elif expr == "pout":
        bk = "down_in"
        s.append(_open_eye(el, eye_y, r, look, lid=0.3, sw=sw) + _open_eye(er_, eye_y, r, look, lid=0.3, sw=sw))
        s.append(_blush(cx, cy, r, ox))
        mouth = f'<path d="M{cx-r*0.14+ox:.1f},{my+r*0.06:.1f} Q{cx+ox:.1f},{my-r*0.06:.1f} {cx+r*0.14+ox:.1f},{my+r*0.06:.1f}" {stroke()}/>'
    else:  # neutral / curious
        bk = "flat"
        s.append(_open_eye(el, eye_y, r, look, lash=lash, sw=sw) + _open_eye(er_, eye_y, r, look, lash=lash, sw=sw))
        mouth = f'<path d="M{cx-r*0.14+ox:.1f},{my:.1f} Q{cx+ox:.1f},{my+r*0.07:.1f} {cx+r*0.14+ox:.1f},{my:.1f}" {stroke()}/>'

    s.append(_brow(bl, brow_y, r, bk, sw, male))
    s.append(_brow(br_, brow_y, r, bk, sw, male))
    s.append(nose)
    s.append(mouth)
    if glasses:
        s.append(f'<rect x="{el-r*0.24:.1f}" y="{eye_y-r*0.22:.1f}" width="{r*0.48:.1f}" height="{r*0.44:.1f}" rx="4" {stroke()}/>'
                 f'<rect x="{er_-r*0.24:.1f}" y="{eye_y-r*0.22:.1f}" width="{r*0.48:.1f}" height="{r*0.44:.1f}" rx="4" {stroke()}/>'
                 f'<path d="M{el+r*0.24:.1f},{eye_y:.1f} L{er_-r*0.24:.1f},{eye_y:.1f}" {stroke()}/>')
    return "".join(s)


# ---- 헤어 (얼굴 뒤 머리 덩어리 + 이마 앞머리). 반환: (back, front) -------
def hair(cx, cy, r, kind, color):
    sw = max(1.6, r * 0.05)
    hc, hs = PAINT(color), (INK if SKETCH else color)   # 스케치=흰 채움+INK 윤곽
    fill = f'fill="{hc}" stroke="{hs}" stroke-width="{sw*0.7:.1f}" stroke-linejoin="round"'
    line = f'fill="none" stroke="{hs}" stroke-width="{sw:.1f}" stroke-linecap="round"'
    top = cy - r
    back, front = [], []

    if kind in ("long", "ponytail"):
        back.append(f'<path d="M{cx-r*1.12:.1f},{cy+r*1.4:.1f} C{cx-r*1.3:.1f},{cy:.1f} {cx-r*1.2:.1f},{top-r*0.35:.1f} {cx:.1f},{top-r*0.42:.1f} '
                    f'C{cx+r*1.2:.1f},{top-r*0.35:.1f} {cx+r*1.3:.1f},{cy:.1f} {cx+r*1.12:.1f},{cy+r*1.4:.1f}" {fill}/>')
        if kind == "ponytail":
            back.append(f'<path d="M{cx+r*0.9:.1f},{cy-r*0.7:.1f} q{r*0.7:.1f},{r*0.3:.1f} {r*0.5:.1f},{r*1.5:.1f} q{-r*0.2:.1f},{-r*0.5:.1f} {-r*0.6:.1f},{-r*1.0:.1f}" {fill}/>')
    elif kind == "bob":
        back.append(f'<path d="M{cx-r*1.12:.1f},{cy+r*0.55:.1f} C{cx-r*1.25:.1f},{top:.1f} {cx-r*0.6:.1f},{top-r*0.4:.1f} {cx:.1f},{top-r*0.4:.1f} '
                    f'C{cx+r*0.6:.1f},{top-r*0.4:.1f} {cx+r*1.25:.1f},{top:.1f} {cx+r*1.12:.1f},{cy+r*0.55:.1f}" {fill}/>')
    elif kind == "updo":
        back.append(f'<path d="M{cx-r*1.05:.1f},{cy+r*0.1:.1f} C{cx-r*1.15:.1f},{top-r*0.2:.1f} {cx-r*0.5:.1f},{top-r*0.45:.1f} {cx:.1f},{top-r*0.42:.1f} '
                    f'C{cx+r*0.5:.1f},{top-r*0.45:.1f} {cx+r*1.15:.1f},{top-r*0.2:.1f} {cx+r*1.05:.1f},{cy+r*0.1:.1f}" {fill}/>')
        back.append(f'<circle cx="{cx:.1f}" cy="{top-r*0.5:.1f}" r="{r*0.42:.1f}" {fill}/>')
    elif kind in ("medium", "swept"):
        back.append(f'<path d="M{cx-r*1.08:.1f},{cy+r*0.4:.1f} C{cx-r*1.15:.1f},{top-r*0.2:.1f} {cx-r*0.6:.1f},{top-r*0.42:.1f} {cx:.1f},{top-r*0.4:.1f} '
                    f'C{cx+r*0.6:.1f},{top-r*0.42:.1f} {cx+r*1.15:.1f},{top-r*0.2:.1f} {cx+r*1.08:.1f},{cy+r*0.4:.1f}" {fill}/>')
    else:  # short / slick
        back.append(f'<path d="M{cx-r*1.02:.1f},{cy:.1f} C{cx-r*1.05:.1f},{top-r*0.25:.1f} {cx-r*0.5:.1f},{top-r*0.36:.1f} {cx:.1f},{top-r*0.34:.1f} '
                    f'C{cx+r*0.5:.1f},{top-r*0.36:.1f} {cx+r*1.05:.1f},{top-r*0.25:.1f} {cx+r*1.02:.1f},{cy:.1f}" {fill}/>')

    fy = cy - r*0.55
    if kind == "slick":
        front.append(f'<path d="M{cx-r*0.85:.1f},{fy:.1f} Q{cx:.1f},{cy-r*1.05:.1f} {cx+r*0.85:.1f},{fy:.1f}" {line}/>')
    elif kind in ("swept", "medium", "short"):
        front.append(f'<path d="M{cx-r*0.8:.1f},{fy+r*0.1:.1f} Q{cx-r*0.2:.1f},{cy-r*1.1:.1f} {cx+r*0.55:.1f},{fy:.1f}" {line}/>'
                     f'<path d="M{cx-r*0.1:.1f},{cy-r:.1f} L{cx+r*0.5:.1f},{fy-r*0.05:.1f}" {line}/>')
    else:  # 가운데 가르마
        front.append(f'<path d="M{cx-r*0.8:.1f},{fy:.1f} Q{cx-r*0.4:.1f},{cy-r*1.05:.1f} {cx:.1f},{cy-r*0.9:.1f} '
                     f'Q{cx+r*0.4:.1f},{cy-r*1.05:.1f} {cx+r*0.8:.1f},{fy:.1f}" {line}/>')
    return "".join(back), "".join(front)


def hair_profile(cx, cy, r, kind, color, facing):
    """측면 전용 머리: 크라운+뒤통수 덩어리 + 이마 앞머리(뱅). 긴머리는 뒤로 흐름.
    반환 (back, front). d=+1이면 오른쪽을 봄(얼굴이 +x쪽)."""
    d = 1 if facing >= 0 else -1
    sw = max(1.6, r * 0.05)
    X = lambda v: cx + d*v*r
    Y = lambda v: cy + v*r
    hc, hs = PAINT(color), (INK if SKETCH else color)
    fill = f'fill="{hc}" stroke="{hs}" stroke-width="{sw*0.7:.1f}" stroke-linejoin="round"'
    line = f'fill="none" stroke="{hs}" stroke-width="{sw:.1f}" stroke-linecap="round"'
    longhair = kind in ("long", "ponytail", "bob")
    updo = (kind == "updo")
    nape = 1.85 if longhair else (0.5 if updo else 0.62)   # 뒤로 내려오는 길이

    # 뒤/위 머리 덩어리: 이마 헤어라인→정수리 볼륨→뒤통수→목덜미(길이)→안쪽으로 복귀
    back = (f'<path d="M{X(0.56):.1f},{Y(-0.52):.1f} '
            f'C{X(0.18):.1f},{Y(-1.34):.1f} {X(-0.5):.1f},{Y(-1.32):.1f} {X(-0.95):.1f},{Y(-0.9):.1f} '   # 정수리 볼륨
            f'C{X(-1.2):.1f},{Y(-0.5):.1f} {X(-1.18):.1f},{Y(-0.02):.1f} {X(-1.04):.1f},{Y(nape):.1f} '    # 뒤통수~길이
            f'L{X(-0.6):.1f},{Y(nape):.1f} '
            f'C{X(-0.78):.1f},{Y(0.05):.1f} {X(-0.72):.1f},{Y(-0.5):.1f} {X(-0.42):.1f},{Y(-0.76):.1f} '   # 안쪽 라인 위로
            f'C{X(-0.05):.1f},{Y(-1.0):.1f} {X(0.36):.1f},{Y(-0.96):.1f} {X(0.56):.1f},{Y(-0.52):.1f} Z" {fill}/>')
    if updo:   # 올림머리 번
        back += f'<circle cx="{X(-0.62):.1f}" cy="{Y(-1.0):.1f}" r="{r*0.42:.1f}" {fill}/>'

    # 앞머리(뱅): 이마 위에서 얼굴쪽으로 흘러내림
    front = (f'<path d="M{X(0.5):.1f},{Y(-0.6):.1f} '
             f'C{X(0.86):.1f},{Y(-0.42):.1f} {X(0.86):.1f},{Y(-0.02):.1f} {X(0.66):.1f},{Y(0.14):.1f} '   # 뱅 끝(눈썹 근처)
             f'C{X(0.78):.1f},{Y(-0.16):.1f} {X(0.7):.1f},{Y(-0.44):.1f} {X(0.52):.1f},{Y(-0.52):.1f} Z" {fill}/>')
    front += f'<path d="M{X(0.2):.1f},{Y(-0.95):.1f} Q{X(0.55):.1f},{Y(-0.78):.1f} {X(0.62):.1f},{Y(-0.5):.1f}" {line}/>'  # 결
    return back, front


# ---- 포즈: 관절 각도(0°=아래, +=오른쪽, ±180=위) ---------------------------
# arm/leg = (상박/허벅지 각도, 전박/종아리 각도)
POSES = {
    "stand":      dict(aL=(-14,-17), aR=(14,17)),
    # 걷기(레퍼런스2): 한쪽 다리 앞으로 가볍게 내딛고 종아리는 거의 수직(교차 방지) + 팔 스윙
    "walk":       dict(aL=(-18,-22), aR=(12,16), lL=(15,3), lR=(-13,-2)),
    # 달리기(레퍼런스1): 앞다리 무릎 들고 굽힘, 뒷다리 차고 뻗음, 팔 90도 굽혀 교차
    "run":        dict(aL=(24,150), aR=(-30,-150), lL=(52,-28), lR=(-32,-30), lean=0.12),
    "phone":      dict(aL=(-14,-17), tR=(0.52,0.12), prop="phone"),    # 손→귀
    "look_phone": dict(aL=(-22,42), aR=(22,-42), prop="lookphone", headlook=0.2),
    "raise_hand": dict(aL=(-14,-17), aR=(164,171)),
    "wave":       dict(aL=(-14,-17), aR=(150,166)),
    "both_up":    dict(aL=(-156,-168), aR=(156,168)),
    "stretch":    dict(aL=(-150,-160), aR=(150,160)),
    "reach":      dict(aL=(-14,-17), aR=(62,82)),
    "point":      dict(aL=(-14,-17), aR=(72,90)),
    "hold_head":  dict(tL=(-0.7,-0.1), tR=(0.7,-0.1)),                # 양손→관자놀이
    "scratch_head": dict(aL=(-14,-17), tR=(0.45,-0.45)),             # 손→머리 옆위(머리 앞에 보이게)
    "think_chin": dict(aL=(-18,-22), tR=(0.06,1.0), eR=-1),          # 손→턱(팔꿈치 아래로)
    "cover_face": dict(aL=(-14,-17), tR=(0.0,0.15)),                 # 손→얼굴
    "arms_cross": dict(aL=(-30,92), aR=(30,-92)),
    "hand_no":    dict(aL=(-40,-138), aR=(40,138)),
    "hug":        dict(aL=(42,74), aR=(-42,-74)),
    "head_down":  dict(aL=(-12,-15), aR=(12,15), droop=True),
    "fall":       dict(aL=(-120,-140), aR=(120,140), lean=0.5),
    "sit":        dict(aL=(-18,-22), aR=(18,22), lL=(-58,-6), lR=(58,6), sit=True),
    "turn_away":  dict(aL=(-14,-17), aR=(14,17), back=True),
    "kiss":       dict(aL=(-14,-17), aR=(14,17)),
    "wave_both":  dict(aL=(-150,-166), aR=(150,166)),
    # 추가 포즈
    "hands_on_hips": dict(aL=(-42,72), aR=(42,-72)),
    "clap":          dict(aL=(28,66), aR=(-28,-66)),
    "shrug":         dict(aL=(-52,-116), aR=(52,116)),
    "thumbs_up":     dict(aL=(-14,-17), aR=(16,150)),
    "facepalm":      dict(aL=(-14,-17), tR=(0.06,-0.32)),   # 손→이마
    "peace_sign":    dict(aL=(-14,-17), aR=(44,150)),
    "beckon":        dict(aL=(-14,-17), aR=(66,82)),
    "jump":          dict(aL=(-150,-164), aR=(150,164), lL=(-36,-70), lR=(36,70)),
    "hands_behind":  dict(aL=(-8,10), aR=(8,-10)),
    "crouch":        dict(aL=(-20,-26), aR=(20,26), lL=(-46,-110), lR=(46,110), sit=True),
    # 추가 포즈 2차
    "drink":         dict(aL=(-14,-17), tR=(0.05,0.5)),               # 손→입(마시기)
    "pray":          dict(tL=(-0.12,0.25), tR=(0.12,0.25)),           # 두 손 모음
    "carry":         dict(aL=(46,72), aR=(-46,-72)),                  # 두 팔 앞으로(들기)
    "dance":         dict(aL=(-150,-150), aR=(44,120), lL=(-14,-8), lR=(16,10)),
    "bow":           dict(aL=(22,30), aR=(-22,-30), droop=True),      # 절/굽혀 인사
    "kneel":         dict(aL=(-14,-17), aR=(14,17), lL=(8,4), lR=(78,4), sit=True),
    # 추가 포즈 3차 — 엄선 웹툰 포즈 확장
    "both_out":      dict(aL=(-92,-96), aR=(92,96)),                  # 양팔 벌림(환영)
    "present":       dict(aL=(-14,-17), aR=(56,40)),                  # 한 손 내밀어 제시
    "block":         dict(aL=(-58,-112), aR=(58,112)),                # 양팔 방어/막기
    "stop_hand":     dict(aL=(-14,-17), aR=(86,96)),                  # 손바닥 내밀어 멈춰
    "point_up":      dict(aL=(-14,-17), aR=(150,150)),                # 위 가리킴
    "flex":          dict(aL=(-150,-56), aR=(150,56)),                # 알통(이두 자랑)
    "salute":        dict(aL=(-14,-17), tR=(0.30,-0.50)),             # 경례(손→이마 옆)
    "cover_mouth":   dict(aL=(-14,-17), tR=(0.05,0.46)),              # 입 가림
    "wipe_tears":    dict(aL=(-14,-17), tR=(0.22,0.12)),              # 눈물 닦기
    "whisper":       dict(aL=(-14,-17), tR=(0.50,0.14)),              # 귓속말(손→입 옆)
    "listen":        dict(aL=(-14,-17), tR=(0.62,0.02)),              # 귀 기울임(손→귀)
    "chin_both":     dict(tL=(-0.22,1.0), tR=(0.22,1.0)),             # 양손 턱 괴기
    "hands_back_head": dict(tL=(-0.50,-0.46), tR=(0.50,-0.46)),       # 뒤통수 깍지(여유)
    "crossed_legs":  dict(aL=(-14,-17), aR=(14,17), lL=(-6,-2), lR=(12,30)),   # 짝다리
    "kick":          dict(aL=(-32,-44), aR=(32,44), lL=(-12,-6), lR=(72,16)),  # 발차기
    "lean":          dict(aL=(-12,-15), aR=(22,30), lean=0.16),       # 기대다
}

# 비율(×r): 목/어깨/몸통/골반/허벅지/종아리/팔
P_NECK, P_SHO, P_TORSO, P_HIPY = 0.32, 0.82, 2.05, 0.0
P_HIP, P_THIGH, P_CALF = 0.52, 1.65, 1.55
P_UPARM, P_FOREARM, P_HAND = 1.20, 1.08, 0.30   # 팔 약간 길게(머리/턱 닿기 여유)
PANTS = "#ffffff" if SKETCH else "#5b6470"


def _pt(x, y, length, ang):
    a = math.radians(ang)
    return x + length*math.sin(a), y + length*math.cos(a)


def _seg(x1, y1, x2, y2, w, color, sw):
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{color}" stroke-width="{w:.1f}" stroke-linecap="round"/>'
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{INK}" stroke-width="{w+sw:.1f}" stroke-linecap="round" opacity="0.0"/>')


def _limb(x1, y1, x2, y2, w, fillc, sw):
    """관절 세그먼트: 외곽선(INK) 위에 색 채움 느낌 — 두꺼운 INK선 + 안쪽 색선."""
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{INK}" stroke-width="{w+sw*1.4:.1f}" stroke-linecap="round"/>'
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{fillc}" stroke-width="{w:.1f}" stroke-linecap="round"/>')


def _taper(x1, y1, w1, x2, y2, w2, fillc, sw, ext=0.0, open_root=False):
    """테이퍼 세그먼트: 뿌리(w1) 두껍고 끝(w2) 가는 사다리꼴. ext=양끝 살짝 연장(겹쳐 러프).
    open_root=True면 뿌리(관절쪽) 외곽선을 닫지 않고 살짝 열어 손그림 느낌(채움은 유지)."""
    dx, dy = x2-x1, y2-y1
    L = math.hypot(dx, dy) or 0.001
    ux, uy = dx/L, dy/L
    x1 -= ux*ext; y1 -= uy*ext; x2 += ux*ext; y2 += uy*ext
    nx, ny = -uy*0.5, ux*0.5
    a = (x1+nx*w1, y1+ny*w1)   # 뿌리 좌
    b = (x2+nx*w2, y2+ny*w2)   # 끝 좌
    c = (x2-nx*w2, y2-ny*w2)   # 끝 우
    d = (x1-nx*w1, y1-ny*w1)   # 뿌리 우
    # 채움: 닫힌 실루엣(테두리 없음) — 열어도 면은 유지
    fill = (f'<path d="M{a[0]:.1f},{a[1]:.1f} L{b[0]:.1f},{b[1]:.1f} L{c[0]:.1f},{c[1]:.1f} '
            f'L{d[0]:.1f},{d[1]:.1f} Z" fill="{fillc}" stroke="none"/>')
    if open_root:
        # 뿌리 캡(d→a)을 생략 → 관절쪽이 열린 외곽선. 끝쪽으로 살짝 안 닿게 짧게.
        stroke = (f'<path d="M{a[0]:.1f},{a[1]:.1f} L{b[0]:.1f},{b[1]:.1f} L{c[0]:.1f},{c[1]:.1f} '
                  f'L{d[0]:.1f},{d[1]:.1f}" fill="none" stroke="{INK}" stroke-width="{sw:.1f}" '
                  f'stroke-linejoin="round" stroke-linecap="round"/>')
    else:
        stroke = (f'<path d="M{a[0]:.1f},{a[1]:.1f} L{b[0]:.1f},{b[1]:.1f} L{c[0]:.1f},{c[1]:.1f} '
                  f'L{d[0]:.1f},{d[1]:.1f} Z" fill="none" stroke="{INK}" stroke-width="{sw:.1f}" '
                  f'stroke-linejoin="round"/>')
    return fill + stroke


def _arm_seg(rx, ry, ex, ey, hx, hy, r, sleeve, sw):
    """상박(어깨 두껍게→팔꿈치) + 전박(팔꿈치→손목 가늘게). 관절은 겹쳐서 자연스럽게(원 없음)."""
    e = r*0.06
    return (_taper(rx, ry, r*0.33, ex, ey, r*0.21, sleeve, sw, ext=e, open_root=True)
            + _taper(ex, ey, r*0.23, hx, hy, r*0.16, sleeve, sw, ext=e, open_root=True)
            + f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="{r*0.14:.1f}" fill="{SKIN}" stroke="{INK}" stroke-width="{sw:.1f}"/>')


def prop_at(kind, hx, hy, r):
    if kind == "phone":
        return (f'<rect x="{hx-r*0.12:.1f}" y="{hy-r*0.22:.1f}" width="{r*0.24:.1f}" '
                f'height="{r*0.44:.1f}" rx="3" fill="white" stroke="{INK}" stroke-width="1.4"/>')
    if kind == "lookphone":
        return (f'<rect x="{hx-r*0.3:.1f}" y="{hy-r*0.05:.1f}" width="{r*0.6:.1f}" '
                f'height="{r*0.4:.1f}" rx="3" fill="white" stroke="{INK}" stroke-width="1.4"/>')
    return ""


def _arm(root, ua, fa, r, sleeve, sw, prop=None):
    """상박+전박+손. root=(x,y). ua/fa=상박/전박 각도. 반환 (svg, hand_xy)."""
    ex, ey = _pt(root[0], root[1], P_UPARM*r, ua)
    hx, hy = _pt(ex, ey, P_FOREARM*r, fa)
    s = _arm_seg(root[0], root[1], ex, ey, hx, hy, r, sleeve, sw)
    if prop:
        s += prop_at(prop, hx, hy, r)
    return s, (hx, hy)


def _arm_to(rx, ry, tx, ty, r, sleeve, sw, elbow_sign=1, prop=None):
    """역운동학(IK): 손을 목표(tx,ty)에 놓고 팔꿈치를 계산. 손이 턱·머리에 정확히 닿게."""
    L1, L2 = P_UPARM*r, P_FOREARM*r
    dx, dy = tx-rx, ty-ry
    D = math.hypot(dx, dy) or 0.001
    if D >= L1+L2:                          # 못 닿으면 곧게 뻗어 근접
        ux, uy = dx/D, dy/D
        ex, ey = rx+L1*ux, ry+L1*uy
        hx, hy = rx+(L1+L2)*ux, ry+(L1+L2)*uy
    else:
        Dc = max(D, abs(L1-L2)+0.1)
        ux, uy = dx/Dc, dy/Dc
        a = (L1*L1 - L2*L2 + Dc*Dc)/(2*Dc)
        h = math.sqrt(max(0.0, L1*L1 - a*a))
        mx, my = rx+a*ux, ry+a*uy
        ex = mx + elbow_sign*h*(-uy)        # 팔꿈치 굽힘 방향
        ey = my + elbow_sign*h*(ux)
        hx, hy = tx, ty
    s = _arm_seg(rx, ry, ex, ey, hx, hy, r, sleeve, sw)
    if prop:
        s += prop_at(prop, hx, hy, r)
    return s


def _leg(root, ta, ca, r, foot_dir, sw, dress=False):
    kx, ky = _pt(root[0], root[1], P_THIGH*r, ta)
    ax, ay = _pt(kx, ky, P_CALF*r, ca)
    fx, fy = _pt(ax, ay, P_HAND*r*1.4, 90*foot_dir)   # 발: 옆으로
    pants = PAINT(PANTS) if not dress else SKIN
    e = r*0.06
    s = ""
    if not dress:   # 허벅지: 골반(두껍게)→무릎(가늘게). 관절쪽 외곽선 열기
        s += _taper(root[0], root[1], r*0.48, kx, ky, r*0.32, pants, sw, ext=e, open_root=True)
    # 종아리: 무릎→발목(더 가늘게)
    s += _taper(kx, ky, r*0.34, ax, ay, r*0.20, pants, sw, ext=e, open_root=True)
    s += f'<path d="M{ax:.1f},{ay:.1f} Q{fx:.1f},{ay+r*0.2:.1f} {fx:.1f},{ay+r*0.04:.1f}" stroke="{INK}" stroke-width="{r*0.32:.1f}" stroke-linecap="round" fill="none"/>'  # 신발
    return s


# ---- 인물 (관절 리그) ------------------------------------------------------
def person(cx, frame, expr, char, facing=0.0, pose="stand", view="front", gender=None):
    r = frame["head_r"]
    if r == 0:
        return ""
    cfg = POSES.get(pose, POSES["stand"])
    cy = frame["h"] * frame["head_cy"]
    lean = cfg.get("lean", 0.0) * r
    # 성별/외형: 등록 캐릭터는 레지스트리, 이름 없으면 성별힌트(gender)로 일반 남/여
    if char in CHARS:
        info = CHARS[char]
        gender = info.get("gender", "M")
    else:
        gender = gender or predict_gender(char)
        info = DEFAULT_FEMALE if gender == "F" else DEFAULT_MALE
    male = (gender != "F")
    sw = max(1.4, r * 0.035)
    accent = PAINT(info.get("accent", "#8a9aa8"))
    dress = info.get("outfit") == "dress"
    body = frame["body"]
    cloth = f'fill="{accent}" stroke="{INK}" stroke-width="{sw:.1f}" stroke-linejoin="round"'
    skinf = f'fill="{SKIN}" stroke="{INK}" stroke-width="{sw:.1f}"'
    g = [f'<!-- {char or "?"} : {expr} / {pose} / {view} / {gender} -->']

    # 시점(각도) 파라미터
    d = 1 if facing >= 0 else -1
    prof = (view == "profile")
    q3 = (view == "q3")
    bshift = (d*r*0.12 if q3 else (d*r*0.04 if prof else 0))
    sho_h = (r*0.34 if prof else (P_SHO*r*0.82 if q3 else P_SHO*r))
    hip_h = (r*0.30 if prof else (P_HIP*r*0.9 if q3 else P_HIP*r))
    wf = (0.5 if prof else (0.82 if q3 else 1.0))     # 몸통 폭 배율
    # 성별 체형: 남=넓은어깨·곧은몸통·좁은골반, 여=좁은어깨·잘록허리·넓은골반
    if not prof:
        sho_h *= (1.14 if male else 0.9)
    hip_h *= (0.85 if male else 1.05)
    waist_f = 0.64 if male else 0.44                  # 허리 폭(클수록 곧음)
    neck_w = r*(0.32 if male else 0.24)               # 목 두께

    # 골격 좌표
    hcx = cx + lean*0.7 + (d*r*0.06 if q3 else 0)
    hcy = cy + (r*0.16 if cfg.get("droop") else 0)
    chin = hcy + r*1.16
    sho_y = chin + P_NECK*r
    cxb = cx + lean + bshift                           # 몸통 중심
    sLx, sRx = cxb - sho_h, cxb + sho_h
    hip_y = sho_y + (P_TORSO*r if not cfg.get("sit") else P_TORSO*r*0.8)
    hLx, hRx = cxb - hip_h, cxb + hip_h
    arm_root_y = sho_y + r*0.12

    if prof:
        back_hair, front_hair = hair_profile(hcx, hcy, r, info["hair"], info["hairc"], facing)
    else:
        back_hair, front_hair = hair(hcx, hcy, r, info["hair"], info["hairc"])
    g.append(back_hair)

    # 목 — 머리·몸 레이어보다 '뒤'에 그리고, 턱 안쪽까지 올려 얼굴과 끊김 없이 연결.
    #      (머리/몸이 위·아래를 덮어 가운데 목만 보이게 됨)
    if body != "none":
        nyt, nyb = chin-r*0.30, sho_y+r*0.28          # 목 위/아래 y
        # 면은 닫아 채우고(테두리 없음), 위·아래(턱·어깨 연결부)는 외곽선을 비워 열어둔다(러프)
        g.append(f'<path d="M{hcx-neck_w:.1f},{nyt:.1f} L{hcx-neck_w:.1f},{nyb:.1f} '
                 f'L{hcx+neck_w:.1f},{nyb:.1f} L{hcx+neck_w:.1f},{nyt:.1f} Z" fill="{SKIN}" stroke="none"/>')
        g.append(f'<path d="M{hcx-neck_w:.1f},{nyt:.1f} L{hcx-neck_w:.1f},{nyb:.1f}" fill="none" '
                 f'stroke="{INK}" stroke-width="{sw:.1f}" stroke-linecap="round"/>')
        g.append(f'<path d="M{hcx+neck_w:.1f},{nyt:.1f} L{hcx+neck_w:.1f},{nyb:.1f}" fill="none" '
                 f'stroke="{INK}" stroke-width="{sw:.1f}" stroke-linecap="round"/>')

    show_legs = body in ("full", "chibi")
    show_arms = body in ("waist", "full", "chibi")

    # 1) 다리 + 골반 — full만. 다리는 골반 관절에서 뿌리내리고, 골반(바지)이 연결부를 덮는다.
    hipJ = r*0.36                 # 골반 관절 반폭
    hjy = hip_y + r*0.12          # 골반 관절 높이
    if show_legs:
        lL = cfg.get("lL", (-4, -3)); lR = cfg.get("lR", (4, 3))
        g.append(_leg((cxb-hipJ, hjy), lL[0], lL[1], r, -1, sw, dress))
        g.append(_leg((cxb+hipJ, hjy), lR[0], lR[1], r, 1, sw, dress))
        if not dress:
            # 골반(바지): 면은 닫아 채우되, 아래 다리연결부(사타구니)는 외곽선을 비워 열어둔다(러프)
            pelvis_d = (f'M{cxb-r*0.52:.1f},{hip_y-r*0.25:.1f} '
                        f'L{cxb-hipJ-r*0.06:.1f},{hjy+r*0.05:.1f} '
                        f'Q{cxb:.1f},{hjy+r*0.42:.1f} {cxb+hipJ+r*0.06:.1f},{hjy+r*0.05:.1f} '
                        f'L{cxb+r*0.52:.1f},{hip_y-r*0.25:.1f} Z')
            g.append(f'<path d="{pelvis_d}" fill="{PANTS}" stroke="none"/>')   # 면만 채움
            # 외곽선: 양옆(허리→다리뿌리)만 — 사타구니 아래 곡선은 생략해 다리연결부가 열림
            g.append(f'<path d="M{cxb-r*0.52:.1f},{hip_y-r*0.25:.1f} '
                     f'L{cxb-hipJ-r*0.06:.1f},{hjy+r*0.05:.1f}" fill="none" '
                     f'stroke="{INK}" stroke-width="{sw:.1f}" stroke-linecap="round"/>')
            g.append(f'<path d="M{cxb+r*0.52:.1f},{hip_y-r*0.25:.1f} '
                     f'L{cxb+hipJ+r*0.06:.1f},{hjy+r*0.05:.1f}" fill="none" '
                     f'stroke="{INK}" stroke-width="{sw:.1f}" stroke-linecap="round"/>')

    # 2) 몸통(의상)
    if body == "bust":
        # 어깨~가슴, 프레임 하단까지(클로즈업 크롭)
        g.append(f'<path d="M{cx-r*1.5:.1f},{frame["h"]:.1f} '
                 f'C{cx-r*1.5:.1f},{sho_y+r*0.4:.1f} {cx-r*1.0:.1f},{sho_y:.1f} {cx-r*0.55:.1f},{sho_y+r*0.05:.1f} '
                 f'L{cx+r*0.55:.1f},{sho_y+r*0.05:.1f} C{cx+r*1.0:.1f},{sho_y:.1f} {cx+r*1.5:.1f},{sho_y+r*0.4:.1f} {cx+r*1.5:.1f},{frame["h"]:.1f} Z" {cloth}/>')
        g.append(f'<path d="M{cx-r*0.3:.1f},{sho_y+r*0.05:.1f} L{cx:.1f},{sho_y+r*0.4:.1f} L{cx+r*0.3:.1f},{sho_y+r*0.05:.1f}" fill="none" stroke="{INK}" stroke-width="{sw:.1f}"/>')
    else:
        # 어깨~허리~골반 실루엣 (cxb 중심, wf 폭배율, waist_f 성별 허리)
        wy = sho_y + (hip_y-sho_y)*0.55
        waist_h = r*waist_f*wf
        if dress:
            botL, botR = cxb-r*1.15*wf, cxb+r*1.15*wf
            boty = hip_y + r*0.7
        elif body == "waist":
            # 자연스런 골반에서 끝 — 상체가 프레임 끝까지 길어지지 않게 (인체 비율 유지)
            botL, botR, boty = cxb-r*0.58*wf, cxb+r*0.58*wf, hip_y
        else:
            botL, botR, boty = cxb-r*0.5, cxb+r*0.5, hip_y-r*0.02  # 상의는 골반 위에서 끝(골반 노출)
        g.append(f'<path d="M{sLx:.1f},{sho_y:.1f} '
                 f'C{sLx-r*0.05:.1f},{wy:.1f} {cxb-waist_h:.1f},{wy:.1f} {cxb-waist_h:.1f},{wy:.1f} '
                 f'L{botL:.1f},{boty:.1f} L{botR:.1f},{boty:.1f} '
                 f'C{cxb+waist_h:.1f},{wy:.1f} {sRx+r*0.05:.1f},{wy:.1f} {sRx:.1f},{sho_y:.1f} '
                 f'C{cxb+r*0.3*wf:.1f},{sho_y-r*0.18:.1f} {cxb-r*0.3*wf:.1f},{sho_y-r*0.18:.1f} {sLx+r*0.1:.1f},{sho_y-r*0.02:.1f}" {cloth}/>')  # 살짝 열림
        if not prof:
            g.append(f'<path d="M{cxb-r*0.28*wf:.1f},{sho_y-r*0.05:.1f} L{cxb:.1f},{sho_y+r*0.3:.1f} L{cxb+r*0.28*wf:.1f},{sho_y-r*0.05:.1f}" fill="none" stroke="{INK}" stroke-width="{sw:.1f}"/>')

    # 3) 팔 + 손. t타깃(머리 근처)이면 IK + 머리에 가리지 않게 '머리 뒤'에 그릴지 판단.
    #    얼굴/머리 위쪽으로 가는 손은 머리 다음에 그려 앞으로 보이게 한다.
    front_arms = []   # 머리 위에 덧그릴 팔(손이 머리/얼굴에 닿는 포즈)
    if show_arms:
        prop = cfg.get("prop")

        def build_arm(side, rootx):
            tgt = cfg.get("t" + side)
            pr = prop if side == "R" else None
            if tgt:
                tx, ty = hcx + tgt[0]*r, hcy + tgt[1]*r
                esign = cfg.get("e" + side, 1 if side == "R" else -1)
                svg = _arm_to(rootx, arm_root_y, tx, ty, r, accent, sw, esign, pr)
                # 손이 턱(1.0r)보다 위면 머리에 가리므로 앞에 그림
                if tgt[1] < 1.05:
                    front_arms.append(svg)
                else:
                    g.append(svg)
            else:
                a = cfg.get("a" + side, (-14, -17) if side == "L" else (14, 17))
                s, _ = _arm((rootx, arm_root_y), a[0], a[1], r, accent, sw, pr)
                g.append(s)

        if prof:
            na_side = "R" if d > 0 else "L"
            build_arm(na_side, cxb + d*sho_h*0.2)
        else:
            build_arm("L", sLx)
            build_arm("R", sRx)
    elif body == "bust" and pose in ("phone",):
        g.append(prop_at("phone", hcx + r*0.95, hcy, r))

    # 4) 머리 (목은 위에서 back_hair 다음에 이미 그림)
    if cfg.get("back"):
        g.append(f'<ellipse cx="{hcx:.1f}" cy="{hcy:.1f}" rx="{r*0.98:.1f}" ry="{r*1.05:.1f}" '
                 f'fill="{PAINT(info["hairc"])}" stroke="{INK}" stroke-width="{sw:.1f}"/>')
        g.append(f'<path d="M{hcx:.1f},{hcy-r*0.7:.1f} L{hcx:.1f},{hcy+r*0.5:.1f}" fill="none" stroke="{INK2}" stroke-width="{sw*0.8:.1f}"/>')
    else:
        g.append(head_shape(hcx, hcy, r, sw, view, facing, male))
        g.append(front_hair)
        g.append(face(hcx, hcy, r, expr, facing, gender, info.get("glasses", False), view))

    # 4b) 머리/얼굴에 닿는 손 — 머리 위에 덧그려 보이게
    g.extend(front_arms)
    return "".join(g)


# ---- 말풍선 ---------------------------------------------------------------
def wrap(text, n):
    text = text.strip().strip("“”\"‘’'")
    out, line = [], ""
    for ch in text:
        line += ch
        if len(line) >= n:
            out.append(line); line = ""
    if line:
        out.append(line)
    return out or [""]


def bubble_size(text, kind="dialogue", maxw=250):
    chars_per = max(5, int(maxw / 28))
    lines = wrap(text, chars_per)
    lh = 42
    w = min(maxw, max(108, max(len(l) for l in lines) * 28 + 34))
    return w, len(lines) * lh + 34


def bubble(x, y, text, kind="dialogue", maxw=250, tail=0.3):
    chars_per = max(5, int(maxw / 28))
    lines = wrap(text, chars_per)
    lh = 42
    h = len(lines) * lh + 34
    w = min(maxw, max(108, max(len(l) for l in lines) * 28 + 34))
    s = []
    if kind == "narration":
        s.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" '
                 f'fill="#fffef2" stroke="{INK}" stroke-width="1.5"/>')
    elif kind == "inner":
        s.append(f'<ellipse cx="{x+w/2}" cy="{y+h/2}" rx="{w/2}" ry="{h/2}" '
                 f'fill="white" stroke="{INK}" stroke-width="1.5" stroke-dasharray="2 5"/>')
        for i, dy in enumerate((h*0.5, h*0.5+16, h*0.5+30)):
            s.append(f'<circle cx="{x-8-i*7}" cy="{y+dy}" r="{5-i*1.3:.1f}" fill="white" stroke="{INK}" stroke-width="1.2"/>')
    else:
        s.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" '
                 f'fill="white" stroke="{INK}" stroke-width="1.8"/>')
        # 꼬리: 화자 쪽(tail 비율)으로 향함
        tx = x + w*min(0.82, max(0.18, tail))
        d = -1 if tail < 0.5 else 1
        s.append(f'<path d="M{tx:.1f},{y+h} l{-7*d:.1f},19 l{24*d:.1f},-17 z" fill="white" stroke="{INK}" stroke-width="1.8"/>')
    ty = y + 34
    for ln in lines:
        s.append(f'<text x="{x+w/2}" y="{ty}" font-family="{FONT}" font-size="33" '
                 f'fill="#222" text-anchor="middle">{esc(ln)}</text>')
        ty += lh
    return "".join(s), (w, h)


def caption_box(text, h, panel_w=W):
    """하단 캡션(나레이션·묘사) — 네모 박스, 가운데 정렬, 바닥에서 살짝 띄움, 큰 글씨."""
    text = (text or "").strip()
    if not text:
        return ""
    fs = 52                                   # 식자(캡션) 글씨 — 크게(2배급)
    maxw = int(panel_w * 0.9)
    cps = max(8, int(maxw / (fs * 0.62)))
    lines = wrap(text, cps)[:3]
    lh = fs + 11
    cw = int(fs * 0.62)
    bw = min(maxw, max(180, max(len(l) for l in lines) * cw + 44))
    bh = len(lines) * lh + 24
    bx = (panel_w - bw) / 2                    # 가운데 정렬
    by = h - bh - 30                           # 하단에서 살짝 띄움
    s = [f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="9" '
         f'fill="#fffef2" stroke="{INK}" stroke-width="2"/>']
    ty = by + fs + 9
    for ln in lines:
        s.append(f'<text x="{panel_w/2:.1f}" y="{ty:.1f}" font-family="{FONT}" font-size="{fs}" '
                 f'fill="#222" text-anchor="middle">{esc(ln)}</text>')
        ty += lh
    return "".join(s)


def sfx(x, y, text):
    t = esc(text.strip().strip("‘’'“”\""))
    return (f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="64" '
            f'fill="{SFX_FILL}" stroke="{INK}" stroke-width="1.2" '
            f'transform="rotate(-8 {x} {y})" opacity="0.9">{t}</text>')


def note(x, y, text):
    """연출 메모(빨강) — 글콘티 묘사를 콘티 메모처럼."""
    lines = wrap(text, 16)
    s = []
    for i, ln in enumerate(lines[:3]):
        s.append(f'<text x="{x}" y="{y+i*18}" font-family="{FONT}" font-size="15" '
                 f'fill="{NOTE}">{esc(ln)}</text>')
    return "".join(s)


def panel_number(n, y):
    return (f'<circle cx="26" cy="{y+24}" r="15" fill="white" stroke="{INK}" stroke-width="1.5"/>'
            f'<text x="26" y="{y+30}" font-family="{FONT}" font-size="18" fill="{INK}" '
            f'text-anchor="middle">{n}</text>')


# ---- 배경 -----------------------------------------------------------------
BG = f'fill="none" stroke="{INK2}" stroke-width="1.6" stroke-linejoin="round" opacity="0.7"'
BG_FILL = f'fill="{PAINT("#eef4fa")}" stroke="{INK2}" stroke-width="1.4" opacity="0.7"'


def background(scene_type, location, h):
    """장소 유형별 단순 배경선. 인물 뒤(연하게). 클로즈업류는 호출부에서 생략."""
    horizon = h * 0.60
    s = []
    if scene_type == "establishing" or location == "house_ext":
        # 집 외관 실루엣 (장소를 '보여주는' 설정샷)
        bx, bw = W*0.22, W*0.56
        roof = h*0.30
        s.append(f'<rect x="{bx}" y="{h*0.42}" width="{bw}" height="{h*0.34}" {BG_FILL}/>')
        s.append(f'<path d="M{bx-12},{h*0.42} L{W*0.5},{roof} L{bx+bw+12},{h*0.42} Z" {BG_FILL}/>')
        for wx in (0.33, 0.46, 0.59):
            s.append(f'<rect x="{W*wx}" y="{h*0.5}" width="{W*0.07}" height="{h*0.08}" {BG}/>')
        s.append(f'<path d="M{W*0.49},{h*0.66} h{W*0.06} v{h*0.10} h-{W*0.06} z" {BG}/>')  # 문
        s.append(f'<line x1="0" y1="{h*0.76}" x2="{W}" y2="{h*0.76}" {BG}/>')
    elif scene_type == "exterior" and location in ("street", "unknown"):
        # 거리: 원경 빌딩 + 지면
        for i, (bx, bh) in enumerate([(0.04,0.30),(0.20,0.42),(0.40,0.24),(0.62,0.38),(0.82,0.30)]):
            s.append(f'<rect x="{W*bx}" y="{horizon-h*bh}" width="{W*0.15}" height="{h*bh}" {BG}/>')
        s.append(f'<line x1="0" y1="{horizon}" x2="{W}" y2="{horizon}" {BG}/>')
    elif scene_type == "exterior":  # garden 등
        s.append(f'<line x1="0" y1="{horizon}" x2="{W}" y2="{horizon}" {BG}/>')
        for bx in (0.12, 0.78, 0.5):
            s.append(f'<path d="M{W*bx-26},{horizon} q26,-46 52,0" {BG}/>')  # 덤불
    elif location == "stage":
        # 무대: 단상 + 스포트라이트
        s.append(f'<path d="M{W*0.18},{h*0.7} L{W*0.82},{h*0.7} L{W*0.9},{h*0.82} L{W*0.1},{h*0.82} Z" {BG}/>')
        s.append(f'<path d="M{W*0.5},0 L{W*0.32},{h*0.7} L{W*0.68},{h*0.7} Z" fill="#fbf7e6" opacity="0.5" stroke="none"/>')
    elif location == "basement":
        # 지하/유적: 거친 돌벽
        s.append(f'<line x1="0" y1="{h*0.72}" x2="{W}" y2="{h*0.72}" {BG}/>')
        for ry in (0.3, 0.45, 0.6):
            for rx in (0.1, 0.4, 0.7):
                s.append(f'<rect x="{W*rx}" y="{h*ry}" width="{W*0.18}" height="{h*0.12}" {BG}/>')
    elif scene_type == "interior":
        # 실내: 뒷벽 모서리 + 바닥선 + 창문
        s.append(f'<line x1="0" y1="{h*0.64}" x2="{W}" y2="{h*0.64}" {BG}/>')      # 바닥
        s.append(f'<path d="M0,{h*0.18} L{W*0.16},{h*0.30} M{W},{h*0.18} L{W*0.84},{h*0.30}" {BG}/>')  # 천장 모서리
        s.append(f'<rect x="{W*0.10}" y="{h*0.20}" width="{W*0.18}" height="{h*0.22}" {BG}/>')  # 창
        s.append(f'<line x1="{W*0.19}" y1="{h*0.20}" x2="{W*0.19}" y2="{h*0.42}" {BG}/>')
    return "".join(s)


# ---- 소품/오브젝트 에셋 ----------------------------------------------------
# 모두 라인아트(INK 선 + 옅은 채움) — rough 필터·흑백과 호환.
WOOD, OBJ, OBJ2, WHT = (("#ffffff",)*4 if SKETCH else ("#cbb796", "#dfe6ee", "#cdd6e0", "#ffffff"))


def _pk(sw):
    return f'stroke="{INK}" stroke-width="{sw:.1f}" stroke-linejoin="round" stroke-linecap="round"'


def prop_table(cx, topy, w, legh, sw):
    L, th = cx-w/2, max(8, w*0.05)
    return (f'<rect x="{L:.1f}" y="{topy:.1f}" width="{w:.1f}" height="{th:.1f}" rx="4" fill="{WOOD}" {_pk(sw)}/>'
            f'<line x1="{L+w*0.11:.1f}" y1="{topy+th:.1f}" x2="{L+w*0.14:.1f}" y2="{topy+legh:.1f}" stroke="{INK}" stroke-width="{sw*1.7:.1f}" stroke-linecap="round"/>'
            f'<line x1="{cx+w*0.39:.1f}" y1="{topy+th:.1f}" x2="{cx+w*0.36:.1f}" y2="{topy+legh:.1f}" stroke="{INK}" stroke-width="{sw*1.7:.1f}" stroke-linecap="round"/>')


def prop_chair(cx, seaty, w, sw):
    s = w
    return (f'<rect x="{cx-s*0.42:.1f}" y="{seaty-s*0.95:.1f}" width="{s*0.84:.1f}" height="{s*0.72:.1f}" rx="7" fill="{WOOD}" {_pk(sw)}/>'
            f'<rect x="{cx-s*0.5:.1f}" y="{seaty:.1f}" width="{s:.1f}" height="{s*0.16:.1f}" rx="4" fill="{OBJ2}" {_pk(sw)}/>'
            f'<line x1="{cx-s*0.4:.1f}" y1="{seaty+s*0.16:.1f}" x2="{cx-s*0.43:.1f}" y2="{seaty+s*0.72:.1f}" stroke="{INK}" stroke-width="{sw*1.5:.1f}"/>'
            f'<line x1="{cx+s*0.4:.1f}" y1="{seaty+s*0.16:.1f}" x2="{cx+s*0.43:.1f}" y2="{seaty+s*0.72:.1f}" stroke="{INK}" stroke-width="{sw*1.5:.1f}"/>')


def prop_bowl(cx, y, s, sw):   # 밥그릇(흰밥+김)
    return (f'<path d="M{cx-s*0.15:.1f},{y-s*0.62:.1f} q{-s*0.1:.1f},{-s*0.16:.1f} 0,{-s*0.32:.1f}" fill="none" stroke="{INK2}" stroke-width="{sw:.1f}"/>'
            f'<path d="M{cx+s*0.12:.1f},{y-s*0.66:.1f} q{s*0.1:.1f},{-s*0.16:.1f} 0,{-s*0.32:.1f}" fill="none" stroke="{INK2}" stroke-width="{sw:.1f}"/>'
            f'<path d="M{cx-s*0.52:.1f},{y-s*0.28:.1f} Q{cx-s*0.28:.1f},{y-s*0.62:.1f} {cx-s*0.05:.1f},{y-s*0.42:.1f} '
            f'Q{cx+s*0.1:.1f},{y-s*0.64:.1f} {cx+s*0.3:.1f},{y-s*0.44:.1f} Q{cx+s*0.45:.1f},{y-s*0.58:.1f} {cx+s*0.52:.1f},{y-s*0.28:.1f} Z" fill="{WHT}" {_pk(sw)}/>'
            f'<path d="M{cx-s*0.6:.1f},{y-s*0.3:.1f} Q{cx:.1f},{y+s*0.32:.1f} {cx+s*0.6:.1f},{y-s*0.3:.1f}" fill="{OBJ}" {_pk(sw)}/>'
            f'<line x1="{cx-s*0.6:.1f}" y1="{y-s*0.3:.1f}" x2="{cx+s*0.6:.1f}" y2="{y-s*0.3:.1f}" {_pk(sw)}/>')


def prop_spoon(cx, y, s, sw):
    return (f'<ellipse cx="{cx:.1f}" cy="{y-s*0.4:.1f}" rx="{s*0.16:.1f}" ry="{s*0.24:.1f}" fill="{OBJ}" {_pk(sw)}/>'
            f'<line x1="{cx:.1f}" y1="{y-s*0.16:.1f}" x2="{cx:.1f}" y2="{y+s*0.05:.1f}" stroke="{INK}" stroke-width="{sw*1.5:.1f}" stroke-linecap="round"/>')


def prop_cup(cx, y, s, sw):
    return (f'<path d="M{cx-s*0.06:.1f},{y-s*0.72:.1f} q{-s*0.08:.1f},{-s*0.14:.1f} 0,{-s*0.28:.1f}" fill="none" stroke="{INK2}" stroke-width="{sw:.1f}"/>'
            f'<path d="M{cx-s*0.3:.1f},{y-s*0.55:.1f} L{cx-s*0.24:.1f},{y:.1f} Q{cx:.1f},{y+s*0.12:.1f} {cx+s*0.24:.1f},{y:.1f} L{cx+s*0.3:.1f},{y-s*0.55:.1f} Z" fill="{OBJ}" {_pk(sw)}/>'
            f'<path d="M{cx+s*0.28:.1f},{y-s*0.46:.1f} q{s*0.26:.1f},0 {s*0.24:.1f},{s*0.2:.1f} q{-s*0.02:.1f},{s*0.12:.1f} {-s*0.2:.1f},{s*0.08:.1f}" fill="none" {_pk(sw)}/>')


def prop_plate(cx, y, s, sw):
    return (f'<ellipse cx="{cx:.1f}" cy="{y-s*0.12:.1f}" rx="{s*0.6:.1f}" ry="{s*0.18:.1f}" fill="{OBJ}" {_pk(sw)}/>'
            f'<ellipse cx="{cx:.1f}" cy="{y-s*0.12:.1f}" rx="{s*0.38:.1f}" ry="{s*0.11:.1f}" fill="none" stroke="{INK}" stroke-width="{sw*0.8:.1f}"/>')


def prop_book(cx, y, s, sw):   # 펼친 책
    return (f'<path d="M{cx-s*0.62:.1f},{y-s*0.02:.1f} Q{cx:.1f},{y-s*0.2:.1f} {cx+s*0.62:.1f},{y-s*0.02:.1f} '
            f'L{cx+s*0.62:.1f},{y+s*0.12:.1f} Q{cx:.1f},{y-s*0.06:.1f} {cx-s*0.62:.1f},{y+s*0.12:.1f} Z" fill="{WHT}" {_pk(sw)}/>'
            f'<line x1="{cx:.1f}" y1="{y-s*0.14:.1f}" x2="{cx:.1f}" y2="{y+s*0.03:.1f}" {_pk(sw)}/>')


def prop_laptop(cx, y, s, sw):
    return (f'<rect x="{cx-s*0.5:.1f}" y="{y-s*0.78:.1f}" width="{s:.1f}" height="{s*0.62:.1f}" rx="4" fill="{OBJ2}" {_pk(sw)}/>'
            f'<rect x="{cx-s*0.42:.1f}" y="{y-s*0.7:.1f}" width="{s*0.84:.1f}" height="{s*0.46:.1f}" rx="2" fill="{OBJ}" stroke="none"/>'
            f'<path d="M{cx-s*0.6:.1f},{y:.1f} L{cx-s*0.5:.1f},{y-s*0.16:.1f} L{cx+s*0.5:.1f},{y-s*0.16:.1f} L{cx+s*0.6:.1f},{y:.1f} Z" fill="{OBJ}" {_pk(sw)}/>')


def prop_bed(cx, topy, w, sw):
    h = w*0.42
    return (f'<rect x="{cx-w/2:.1f}" y="{topy:.1f}" width="{w:.1f}" height="{h:.1f}" rx="9" fill="{OBJ}" {_pk(sw)}/>'
            f'<rect x="{cx-w*0.43:.1f}" y="{topy+h*0.1:.1f}" width="{w*0.3:.1f}" height="{h*0.32:.1f}" rx="8" fill="{WHT}" {_pk(sw)}/>'
            f'<path d="M{cx-w*0.05:.1f},{topy+h*0.5:.1f} L{cx+w*0.5:.1f},{topy+h*0.5:.1f}" fill="none" {_pk(sw)}/>')


def prop_sofa(cx, topy, w, sw):
    h = w*0.4
    return (f'<rect x="{cx-w/2:.1f}" y="{topy-h*0.5:.1f}" width="{w:.1f}" height="{h*0.6:.1f}" rx="12" fill="{OBJ}" {_pk(sw)}/>'
            f'<rect x="{cx-w/2:.1f}" y="{topy:.1f}" width="{w:.1f}" height="{h:.1f}" rx="13" fill="{OBJ2}" {_pk(sw)}/>'
            f'<rect x="{cx-w/2:.1f}" y="{topy-h*0.35:.1f}" width="{w*0.15:.1f}" height="{h*0.9:.1f}" rx="9" fill="{OBJ}" {_pk(sw)}/>'
            f'<rect x="{cx+w/2-w*0.15:.1f}" y="{topy-h*0.35:.1f}" width="{w*0.15:.1f}" height="{h*0.9:.1f}" rx="9" fill="{OBJ}" {_pk(sw)}/>')


# ---- 추가 소품 에셋(엄선 확장) — 모두 (cx, y, s, sw), (cx,y) 중심 -----------
def prop_umbrella(cx, y, s, sw):
    return (f'<path d="M{cx-s*0.55:.1f},{y-s*0.18:.1f} Q{cx:.1f},{y-s*0.85:.1f} {cx+s*0.55:.1f},{y-s*0.18:.1f} '
            f'Q{cx+s*0.27:.1f},{y-s*0.34:.1f} {cx:.1f},{y-s*0.18:.1f} Q{cx-s*0.27:.1f},{y-s*0.34:.1f} {cx-s*0.55:.1f},{y-s*0.18:.1f} Z" fill="{OBJ}" {_pk(sw)}/>'
            f'<line x1="{cx:.1f}" y1="{y-s*0.62:.1f}" x2="{cx:.1f}" y2="{y+s*0.55:.1f}" {_pk(sw)}/>'
            f'<path d="M{cx:.1f},{y+s*0.55:.1f} q{-s*0.18:.1f},0 {-s*0.18:.1f},{-s*0.16:.1f}" fill="none" {_pk(sw)}/>')


def prop_bag(cx, y, s, sw):     # 핸드백
    return (f'<path d="M{cx-s*0.42:.1f},{y-s*0.18:.1f} L{cx-s*0.32:.1f},{y+s*0.4:.1f} L{cx+s*0.32:.1f},{y+s*0.4:.1f} '
            f'L{cx+s*0.42:.1f},{y-s*0.18:.1f} Z" fill="{OBJ}" {_pk(sw)}/>'
            f'<path d="M{cx-s*0.26:.1f},{y-s*0.18:.1f} Q{cx:.1f},{y-s*0.62:.1f} {cx+s*0.26:.1f},{y-s*0.18:.1f}" fill="none" {_pk(sw)}/>')


def prop_backpack(cx, y, s, sw):
    return (f'<rect x="{cx-s*0.34:.1f}" y="{y-s*0.34:.1f}" width="{s*0.68:.1f}" height="{s*0.74:.1f}" rx="14" fill="{OBJ}" {_pk(sw)}/>'
            f'<rect x="{cx-s*0.24:.1f}" y="{y-s*0.04:.1f}" width="{s*0.48:.1f}" height="{s*0.3:.1f}" rx="7" fill="{OBJ2}" {_pk(sw)}/>'
            f'<path d="M{cx-s*0.2:.1f},{y-s*0.34:.1f} Q{cx:.1f},{y-s*0.5:.1f} {cx+s*0.2:.1f},{y-s*0.34:.1f}" fill="none" {_pk(sw)}/>')


def prop_coffee(cx, y, s, sw):  # 테이크아웃 컵
    return (f'<path d="M{cx-s*0.26:.1f},{y-s*0.2:.1f} L{cx-s*0.2:.1f},{y+s*0.42:.1f} Q{cx:.1f},{y+s*0.5:.1f} {cx+s*0.2:.1f},{y+s*0.42:.1f} '
            f'L{cx+s*0.26:.1f},{y-s*0.2:.1f} Z" fill="{OBJ}" {_pk(sw)}/>'
            f'<rect x="{cx-s*0.3:.1f}" y="{y-s*0.3:.1f}" width="{s*0.6:.1f}" height="{s*0.12:.1f}" rx="3" fill="{OBJ2}" {_pk(sw)}/>'
            f'<line x1="{cx+s*0.12:.1f}" y1="{y-s*0.3:.1f}" x2="{cx+s*0.2:.1f}" y2="{y-s*0.6:.1f}" {_pk(sw)}/>')


def prop_books(cx, y, s, sw):   # 책 더미
    return "".join(
        f'<rect x="{cx-s*0.4+i*s*0.05:.1f}" y="{y+s*0.34-i*s*0.18:.1f}" width="{s*0.8-i*s*0.1:.1f}" '
        f'height="{s*0.15:.1f}" rx="2" fill="{WHT}" {_pk(sw)}/>' for i in range(3))


def prop_plant(cx, y, s, sw):   # 화분
    return (f'<path d="M{cx-s*0.26:.1f},{y+s*0.1:.1f} L{cx-s*0.2:.1f},{y+s*0.45:.1f} L{cx+s*0.2:.1f},{y+s*0.45:.1f} '
            f'L{cx+s*0.26:.1f},{y+s*0.1:.1f} Z" fill="{WOOD}" {_pk(sw)}/>'
            f'<path d="M{cx:.1f},{y+s*0.1:.1f} Q{cx-s*0.4:.1f},{y-s*0.2:.1f} {cx-s*0.28:.1f},{y-s*0.55:.1f}" fill="none" {_pk(sw)}/>'
            f'<path d="M{cx:.1f},{y+s*0.1:.1f} Q{cx:.1f},{y-s*0.4:.1f} {cx:.1f},{y-s*0.6:.1f}" fill="none" {_pk(sw)}/>'
            f'<path d="M{cx:.1f},{y+s*0.1:.1f} Q{cx+s*0.4:.1f},{y-s*0.2:.1f} {cx+s*0.28:.1f},{y-s*0.55:.1f}" fill="none" {_pk(sw)}/>')


def prop_clock(cx, y, s, sw):
    return (f'<circle cx="{cx:.1f}" cy="{y:.1f}" r="{s*0.42:.1f}" fill="{WHT}" {_pk(sw)}/>'
            f'<line x1="{cx:.1f}" y1="{y:.1f}" x2="{cx:.1f}" y2="{y-s*0.28:.1f}" {_pk(sw)}/>'
            f'<line x1="{cx:.1f}" y1="{y:.1f}" x2="{cx+s*0.2:.1f}" y2="{y+s*0.06:.1f}" {_pk(sw)}/>')


def prop_phone2(cx, y, s, sw):  # 스마트폰
    return (f'<rect x="{cx-s*0.22:.1f}" y="{y-s*0.42:.1f}" width="{s*0.44:.1f}" height="{s*0.84:.1f}" rx="7" fill="{OBJ2}" {_pk(sw)}/>'
            f'<rect x="{cx-s*0.16:.1f}" y="{y-s*0.32:.1f}" width="{s*0.32:.1f}" height="{s*0.56:.1f}" rx="2" fill="{WHT}" stroke="none"/>'
            f'<circle cx="{cx:.1f}" cy="{y+s*0.32:.1f}" r="{s*0.04:.1f}" fill="none" {_pk(sw)}/>')


def prop_guitar(cx, y, s, sw):
    return (f'<ellipse cx="{cx:.1f}" cy="{y+s*0.22:.1f}" rx="{s*0.34:.1f}" ry="{s*0.4:.1f}" fill="{WOOD}" {_pk(sw)}/>'
            f'<circle cx="{cx:.1f}" cy="{y+s*0.22:.1f}" r="{s*0.12:.1f}" fill="none" {_pk(sw)}/>'
            f'<rect x="{cx-s*0.07:.1f}" y="{y-s*0.62:.1f}" width="{s*0.14:.1f}" height="{s*0.55:.1f}" rx="3" fill="{OBJ}" {_pk(sw)}/>'
            f'<rect x="{cx-s*0.1:.1f}" y="{y-s*0.72:.1f}" width="{s*0.2:.1f}" height="{s*0.12:.1f}" rx="2" fill="{OBJ2}" {_pk(sw)}/>')


def prop_mic(cx, y, s, sw):
    return (f'<ellipse cx="{cx:.1f}" cy="{y-s*0.3:.1f}" rx="{s*0.18:.1f}" ry="{s*0.22:.1f}" fill="{OBJ2}" {_pk(sw)}/>'
            f'<line x1="{cx:.1f}" y1="{y-s*0.08:.1f}" x2="{cx:.1f}" y2="{y+s*0.45:.1f}" stroke="{INK}" stroke-width="{sw*1.8:.1f}" stroke-linecap="round"/>')


def prop_balloon(cx, y, s, sw):
    return (f'<ellipse cx="{cx:.1f}" cy="{y-s*0.18:.1f}" rx="{s*0.3:.1f}" ry="{s*0.36:.1f}" fill="{OBJ}" {_pk(sw)}/>'
            f'<path d="M{cx:.1f},{y+s*0.18:.1f} l{-s*0.05:.1f},{s*0.06:.1f} l{s*0.1:.1f},0 z" fill="{OBJ}" {_pk(sw)}/>'
            f'<path d="M{cx:.1f},{y+s*0.24:.1f} q{s*0.12:.1f},{s*0.18:.1f} 0,{s*0.36:.1f}" fill="none" stroke="{INK2}" stroke-width="{sw*0.8:.1f}"/>')


def prop_gift(cx, y, s, sw):
    return (f'<rect x="{cx-s*0.36:.1f}" y="{y-s*0.16:.1f}" width="{s*0.72:.1f}" height="{s*0.5:.1f}" rx="3" fill="{OBJ}" {_pk(sw)}/>'
            f'<rect x="{cx-s*0.4:.1f}" y="{y-s*0.28:.1f}" width="{s*0.8:.1f}" height="{s*0.16:.1f}" rx="3" fill="{OBJ2}" {_pk(sw)}/>'
            f'<line x1="{cx:.1f}" y1="{y-s*0.28:.1f}" x2="{cx:.1f}" y2="{y+s*0.34:.1f}" {_pk(sw)}/>'
            f'<path d="M{cx:.1f},{y-s*0.28:.1f} q{-s*0.16:.1f},{-s*0.18:.1f} {-s*0.02:.1f},{-s*0.02:.1f} q{s*0.14:.1f},{-s*0.16:.1f} {s*0.02:.1f},{s*0.02:.1f}" fill="none" {_pk(sw)}/>')


def prop_flower(cx, y, s, sw):
    petals = "".join(f'<circle cx="{cx+s*0.16*math.cos(a):.1f}" cy="{y-s*0.28+s*0.16*math.sin(a):.1f}" r="{s*0.12:.1f}" fill="{OBJ}" {_pk(sw)}/>'
                     for a in (0, 1.26, 2.51, 3.77, 5.03))
    return (petals + f'<circle cx="{cx:.1f}" cy="{y-s*0.28:.1f}" r="{s*0.1:.1f}" fill="{OBJ2}" {_pk(sw)}/>'
            f'<line x1="{cx:.1f}" y1="{y-s*0.16:.1f}" x2="{cx:.1f}" y2="{y+s*0.45:.1f}" {_pk(sw)}/>')


def prop_camera(cx, y, s, sw):
    return (f'<rect x="{cx-s*0.4:.1f}" y="{y-s*0.22:.1f}" width="{s*0.8:.1f}" height="{s*0.5:.1f}" rx="6" fill="{OBJ2}" {_pk(sw)}/>'
            f'<rect x="{cx-s*0.12:.1f}" y="{y-s*0.32:.1f}" width="{s*0.24:.1f}" height="{s*0.12:.1f}" rx="2" fill="{OBJ}" {_pk(sw)}/>'
            f'<circle cx="{cx:.1f}" cy="{y+s*0.03:.1f}" r="{s*0.18:.1f}" fill="{WHT}" {_pk(sw)}/>')


def prop_bottle(cx, y, s, sw):
    return (f'<path d="M{cx-s*0.16:.1f},{y+s*0.42:.1f} L{cx-s*0.16:.1f},{y-s*0.1:.1f} Q{cx-s*0.16:.1f},{y-s*0.28:.1f} {cx-s*0.07:.1f},{y-s*0.36:.1f} '
            f'L{cx-s*0.07:.1f},{y-s*0.5:.1f} L{cx+s*0.07:.1f},{y-s*0.5:.1f} L{cx+s*0.07:.1f},{y-s*0.36:.1f} '
            f'Q{cx+s*0.16:.1f},{y-s*0.28:.1f} {cx+s*0.16:.1f},{y-s*0.1:.1f} L{cx+s*0.16:.1f},{y+s*0.42:.1f} Z" fill="{OBJ}" {_pk(sw)}/>')


def prop_cake(cx, y, s, sw):    # 케이크 조각
    return (f'<path d="M{cx-s*0.36:.1f},{y+s*0.3:.1f} L{cx+s*0.36:.1f},{y+s*0.3:.1f} L{cx+s*0.1:.1f},{y-s*0.28:.1f} Z" fill="{WHT}" {_pk(sw)}/>'
            f'<path d="M{cx-s*0.36:.1f},{y+s*0.3:.1f} L{cx+s*0.36:.1f},{y+s*0.3:.1f} L{cx+s*0.36:.1f},{y+s*0.12:.1f} '
            f'Q{cx:.1f},{y-s*0.02:.1f} {cx-s*0.36:.1f},{y+s*0.12:.1f} Z" fill="{OBJ}" {_pk(sw)}/>'
            f'<circle cx="{cx-s*0.02:.1f}" cy="{y-s*0.18:.1f}" r="{s*0.06:.1f}" fill="{OBJ2}" {_pk(sw)}/>')


def prop_hat(cx, y, s, sw):     # 캡 모자
    return (f'<path d="M{cx-s*0.34:.1f},{y+s*0.06:.1f} Q{cx:.1f},{y-s*0.46:.1f} {cx+s*0.34:.1f},{y+s*0.06:.1f} Z" fill="{OBJ}" {_pk(sw)}/>'
            f'<path d="M{cx+s*0.1:.1f},{y+s*0.06:.1f} Q{cx+s*0.5:.1f},{y+s*0.06:.1f} {cx+s*0.5:.1f},{y+s*0.16:.1f} L{cx+s*0.1:.1f},{y+s*0.13:.1f} Z" fill="{OBJ2}" {_pk(sw)}/>')


def prop_glasses(cx, y, s, sw):
    return (f'<circle cx="{cx-s*0.22:.1f}" cy="{y:.1f}" r="{s*0.18:.1f}" fill="none" {_pk(sw)}/>'
            f'<circle cx="{cx+s*0.22:.1f}" cy="{y:.1f}" r="{s*0.18:.1f}" fill="none" {_pk(sw)}/>'
            f'<line x1="{cx-s*0.04:.1f}" y1="{y:.1f}" x2="{cx+s*0.04:.1f}" y2="{y:.1f}" {_pk(sw)}/>')


def prop_ball(cx, y, s, sw):
    return (f'<circle cx="{cx:.1f}" cy="{y:.1f}" r="{s*0.36:.1f}" fill="{WHT}" {_pk(sw)}/>'
            f'<path d="M{cx-s*0.36:.1f},{y:.1f} Q{cx:.1f},{y-s*0.16:.1f} {cx+s*0.36:.1f},{y:.1f}" fill="none" {_pk(sw)}/>'
            f'<path d="M{cx-s*0.26:.1f},{y-s*0.25:.1f} Q{cx:.1f},{y:.1f} {cx-s*0.26:.1f},{y+s*0.25:.1f}" fill="none" {_pk(sw)}/>')


def prop_suitcase(cx, y, s, sw):  # 캐리어
    return (f'<rect x="{cx-s*0.3:.1f}" y="{y-s*0.32:.1f}" width="{s*0.6:.1f}" height="{s*0.72:.1f}" rx="8" fill="{OBJ}" {_pk(sw)}/>'
            f'<line x1="{cx-s*0.1:.1f}" y1="{y-s*0.32:.1f}" x2="{cx-s*0.1:.1f}" y2="{y+s*0.4:.1f}" {_pk(sw)}/>'
            f'<path d="M{cx-s*0.12:.1f},{y-s*0.32:.1f} L{cx-s*0.12:.1f},{y-s*0.5:.1f} L{cx+s*0.04:.1f},{y-s*0.5:.1f} L{cx+s*0.04:.1f},{y-s*0.32:.1f}" fill="none" {_pk(sw)}/>')


PROP_FN = {"bowl": prop_bowl, "spoon": prop_spoon, "cup": prop_cup, "plate": prop_plate,
           "book": prop_book, "laptop": prop_laptop, "books": prop_books,
           "coffee": prop_coffee, "cake": prop_cake, "phone2": prop_phone2,
           "camera": prop_camera, "bottle": prop_bottle, "glasses": prop_glasses}

# 손에 들거나 인물 옆에 두는 소품(테이블 위가 아님) → 인물 옆 바닥/공중에 배치
HELD_FN = {"umbrella": prop_umbrella, "bag": prop_bag, "backpack": prop_backpack,
           "plant": prop_plant, "guitar": prop_guitar, "mic": prop_mic,
           "balloon": prop_balloon, "gift": prop_gift, "flower": prop_flower,
           "ball": prop_ball, "suitcase": prop_suitcase, "hat": prop_hat}


def scene_props(props, h, sw):
    """소품 배치 → (behind, front). behind=인물 뒤(의자·침대·소파), front=인물 앞(책상+위 물건)."""
    if not props:
        return "", ""
    cx = W/2
    behind, front = [], []
    if "bed" in props:
        behind.append(prop_bed(cx, h*0.46, W*0.72, sw))
    if "sofa" in props:
        behind.append(prop_sofa(cx, h*0.6, W*0.66, sw))
    if "chair" in props:
        behind.append(prop_chair(cx, h*0.64, W*0.36, sw))
    tableware = [p for p in ("bowl", "plate", "cup", "spoon", "book", "laptop",
                             "coffee", "cake", "phone2", "camera", "bottle", "glasses", "books") if p in props]
    if "table" in props or tableware:
        ty = h*0.66
        front.append(prop_table(cx, ty, W*0.8, h*0.32, sw))
        for i, it in enumerate(tableware):
            ix = cx + (i-(len(tableware)-1)/2.0)*W*0.17
            front.append(PROP_FN[it](ix, ty, W*0.11, sw))
    # 손에 들거나 인물 옆에 두는 소품 — 인물 좌우 지면 근처에 배치
    held = [p for p in HELD_FN if p in props]
    for i, it in enumerate(held):
        side = -1 if i % 2 == 0 else 1
        hx = cx + side*W*0.34 - (i//2)*W*0.04
        front.append(HELD_FN[it](hx, h*0.58, W*0.17, sw))
    return "".join(behind), "".join(front)


# ---- 패널 렌더 ------------------------------------------------------------
def render_panel(panel, y0):
    ax = panel["axes"]
    shot = ax["A_shot"]
    frame = SHOT_FRAME.get(shot, SHOT_FRAME["unspecified"])
    h = frame["h"]
    emo = ax["C_emotion"][0]
    pose = ax.get("F_pose", "stand")
    view = ax.get("G_view", "front")
    if pose == "stand" and "chair" in panel.get("props", []):   # 의자/식사 → 앉은 자세
        pose = "sit"
    people = panel.get("n_people")
    if people is None:                       # resolve 안 거친 데모 패널 폴백
        if "group" in ax["B_compose"]:
            people = "group"
        elif "two_shot" in ax["B_compose"]:
            people = 2
        else:
            people = 1
    cast = panel.get("cast", [])

    s = [f'<g transform="translate(0,{y0})">']
    # 패널 박스
    s.append(f'<rect x="6" y="6" width="{W-12}" height="{h-12}" fill="{PANEL_BG}" '
             f'stroke="{INK}" stroke-width="2.2"/>')
    s.append(f'<g filter="url(#rough)">')

    # 배경 (장소 있음 + 환경이 보이는 샷에서만; 클로즈업류는 얼굴이 화면을 채움)
    scene_type = panel.get("scene_resolved", "blank")
    location = panel.get("location", "unknown")
    if scene_type != "blank" and shot in ("medium", "full", "long", "unspecified", "insert"):
        s.append(background(scene_type, location, h))

    # 소품 — 인물 뒤(의자·침대·소파) / 인물 앞(책상+위 물건). 몸이 보이는 샷만.
    behind_props, front_props = "", ""
    if panel.get("props") and shot in ("medium", "full", "long", "unspecified"):
        behind_props, front_props = scene_props(panel["props"], h, 2.2)
        if behind_props:
            s.append(behind_props)

    # 인물 배치 — actors(이름·성별) 기반으로 1명/2명/다인물
    speakers = panel.get("speakers", [])
    gh = panel.get("gender_hint")
    actors = list(panel.get("actors", []))
    for sp in speakers:                                  # 화자도 보강
        if sp not in [n for n, _ in actors]:
            actors.append((sp, None))

    def actor(i):
        if i < len(actors):
            return actors[i]                             # (name, gender)
        return (None, gh)

    # 전신 샷: 발이 지면(배경 수평선 h*0.60)에 닿도록 head_cy 보정 (FOOT_K=발y≈cy+7r)
    GROUND_Y = h * 0.60
    gframe = frame
    if frame["body"] == "full":
        gframe = dict(frame)
        gframe["head_cy"] = (GROUND_Y - 7.0 * frame["head_r"]) / h

    if frame["body"] == "none":
        # insert/title — 묘사 박스만
        s.append(f'<rect x="{W*0.25}" y="{h*0.3}" width="{W*0.5}" height="{h*0.4}" '
                 f'fill="none" stroke="{INK2}" stroke-width="1.5" stroke-dasharray="6 6"/>')
    elif people == "group":
        # 다인물: 지면(수평선)에 발을 딛고 선 군중. 비균등 간격·원근(깊이)·다양한 포즈/방향으로 자연스럽게.
        horizon = h * 0.60
        na = len(actors)
        n = min(max(na if na >= 2 else 3, 2), 5)
        XS = {2: [0.33, 0.67], 3: [0.20, 0.50, 0.80],
              4: [0.17, 0.39, 0.62, 0.85], 5: [0.13, 0.33, 0.52, 0.71, 0.90]}[n]
        POSES_G = ["stand", "walk", "stand", "walk", "walk"]
        FACE_G = [0.0, 0.30, -0.25, 0.18, -0.12]
        SCL_G = [1.0, 0.80, 1.14, 0.90, 0.72]          # 깊이감(원근): 클수록 앞·아래
        members = []
        for i in range(n):
            sc = SCL_G[i % len(SCL_G)]
            gr = h * 0.060 * sc                         # 패널 높이에 비례(샷 무관하게 전신이 들어감)
            foot_y = horizon + (sc - 0.95) * h * 0.30   # 가까울수록 지면 아래, 멀수록 수평선 근처
            gf = dict(frame)
            gf["head_r"] = gr
            gf["head_cy"] = (foot_y - 7.0 * gr) / h     # 발이 foot_y에 닿도록 머리 위치 역산
            nm, ggd = actor(i)
            if nm is None and ggd is None:
                ggd = "F" if i % 2 == 0 else "M"        # 익명 군중은 성별 교차로 다양하게
            mid = (i == n // 2)
            pz = pose if (mid and pose != "stand") else POSES_G[i % len(POSES_G)]
            members.append((sc, person(W*XS[i], gf, emo if mid else "neutral",
                                       nm, facing=FACE_G[i % len(FACE_G)], pose=pz, gender=ggd)))
        for _sc, ps in sorted(members, key=lambda m: m[0]):   # 뒤(작은)→앞(큰) 순으로 그려 겹침 자연스럽게
            s.append(ps)
    elif people == 2:
        tv = "profile" if view == "profile" else "q3"
        close = pose in ("kiss", "hug")                 # 키스/포옹은 더 가까이
        xL, xR = (0.37, 0.63) if close else (0.30, 0.70)
        n0, g0 = actor(0); n1, g1 = actor(1)
        s.append(person(W*xL, gframe, emo, n0, facing=+1, pose=pose, view=tv, gender=g0))
        s.append(person(W*xR, gframe, emo, n1, facing=-1, pose=pose, view=tv, gender=g1))
    else:
        fac = 0.85 if view in ("q3", "profile") else 0.0
        n0, g0 = actor(0)
        s.append(person(W*0.5, gframe, emo, n0, facing=fac, pose=pose, view=view, gender=g0))

    if front_props:           # 책상+물건은 인물 앞(전경)
        s.append(front_props)

    s.append('</g>')  # /rough

    # 효과음 — 인물(중앙)·말풍선(우상단)과 안 겹치게 빈 좌상단 여백에 배치
    for i, fx in enumerate(panel.get("sfx", [])[:2]):
        s.append(sfx(W*0.07, h*0.17 + i*80, fx))

    # 말풍선 — 규칙: 얼굴/표정(눈·입)을 가리지 않게 화자 머리의 '표정 박스'를 피해 상단 코너에 배치.
    #          꼬리는 화자 쪽을 향함. 회피 불가 시 표정 위(이마/머리 위) 여백으로 올림.
    if frame["body"] == "full":
        hy_h = h * gframe["head_cy"]
    else:
        hy_h = h * frame["head_cy"]
    hr_h = frame["head_r"]
    if people == 2:
        _close = pose in ("kiss", "hug")
        head_xs = [W*0.37, W*0.63] if _close else [W*0.30, W*0.70]
    elif people == 1 and frame["body"] != "none":
        head_xs = [W*0.5]
    else:
        head_xs = []
    # 표정(눈·입) 박스 — 이마/머리 위는 가려도 됨, 이 박스만 피하면 됨
    exprs = [(hx-hr_h*0.85, hy_h-hr_h*0.10, hx+hr_h*0.85, hy_h+hr_h*0.65) for hx in head_xs]

    def _ovl(a, b):
        return not (a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3])

    def _spk_x(d):
        sp = d.get("speaker")
        if people == 2 and sp:
            names = [n for n, _ in actors]
            if sp in names:
                return head_xs[0] if names.index(sp) == 0 else head_xs[1]
            return head_xs[1]
        return head_xs[0] if head_xs else W*0.5

    used = []   # 이미 놓인 말풍선 사각형(겹침 방지)
    def _place(bw, bh, sx):
        m = 14
        right = (W-bw-m, m); left = (m, m)
        order = [right, left] if sx >= W/2 else [left, right]
        for bx, by0 in order:
            r = (bx, by0, bx+bw, by0+bh)
            if all(not _ovl(r, e) for e in exprs) and all(not _ovl(r, u) for u in used):
                return bx, by0
        # 회피 실패: 화자 위쪽, 기존 말풍선 아래로 쌓기
        bx = min(max(sx-bw/2, m), W-bw-m)
        by0 = m + sum(u[3]-u[1]+10 for u in used)
        return bx, by0

    def _emit(text, kind):
        bw, bh = bubble_size(text, kind)
        sx = _spk_x({}) if kind == "inner" else None
        sx = sx if sx is not None else W*0.5
        bx, by0 = _place(bw, bh, sx)
        tail = (sx - bx) / bw
        b, _sz = bubble(bx, by0, text, kind, tail=tail)
        s.append(b); used.append((bx, by0, bx+bw, by0+bh))

    for d in panel.get("dialogue", []):
        bw, bh = bubble_size(d["text"], "dialogue")
        sx = _spk_x(d)
        bx, by0 = _place(bw, bh, sx)
        b, _sz = bubble(bx, by0, d["text"], "dialogue", tail=(sx-bx)/bw)
        s.append(b); used.append((bx, by0, bx+bw, by0+bh))
    for d in panel.get("inner", []):
        _emit(d["text"], "inner")
    # 하단 캡션: 나레이션이 있으면 나레이션, 없으면 묘사 — 네모박스·가운데·큰 글씨
    cap = " ".join(panel.get("narration", [])).strip()
    if not cap:
        cap = panel.get("description", "")
    if cap:
        s.append(caption_box(cap, h))

    # 패널 번호
    s.append(panel_number(panel["num"], 6))
    s.append('</g>')
    return "".join(s), h


# 흑백(명도) 모드: 색감 제거하고 밝기만. False면 컬러.
GRAY = True


def svg_header(total_h, width=W, seed=5):
    # @import을 SVG 안에 넣어 <object>/<img>로 써도 손글씨 폰트가 적용되게 함
    # gray 필터: 채도 0(feColorMatrix saturate=0) → 원래 밝기 그대로 회색조. sRGB로 perceptual.
    # seed: rough 필터 난수 시드 — 패널 '리롤(다시 뽑기)'마다 바꿔 선 흔들림을 다르게.
    h = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{total_h}" '
         f'viewBox="0 0 {width} {total_h}">'
         f'<defs><style>@import url(https://fonts.googleapis.com/css2?family=Nanum+Pen+Script&amp;display=swap);</style>'
         f'<filter id="rough"><feTurbulence type="fractalNoise" baseFrequency="0.019 0.022" '
         f'numOctaves="2" seed="{seed}" result="n"/>'
         f'<feDisplacementMap in="SourceGraphic" in2="n" scale="4.6"/></filter>'
         f'<filter id="gray" color-interpolation-filters="sRGB"><feColorMatrix type="saturate" values="0"/></filter>'
         f'</defs>'
         f'<rect width="{width}" height="{total_h}" fill="white"/>')
    if GRAY:
        h += '<g filter="url(#gray)">'   # 이하 모든 콘텐츠를 회색조로
    return h


def svg_footer():
    return ('</g>' if GRAY else '') + '</svg>'


STRIP_GAP = 90   # 컷 사이 웹툰 여백(흰 거터) — 모든 스트립(샘플·에피소드·비교)에 일관 적용


def build_strip_svg(panels, limit=None, seed=5, gap=None):
    """패널 리스트 → (svg 문자열, 높이). 컷 사이에 일정 여백(gap)을 둬 웹툰처럼."""
    if limit:
        panels = panels[:limit]
    if gap is None:
        gap = STRIP_GAP
    body, y, n = [], 0, len(panels)
    for i, p in enumerate(panels):
        seg, h = render_panel(p, y)
        body.append(seg)
        y += h + (gap if i < n-1 else 0)
    return svg_header(y, seed=seed) + "".join(body) + svg_footer(), y


def build_panel_svg(panel, seed=5):
    """단일 패널 → (svg 문자열, 높이). 패널별 리롤/편집·PNG 내보내기용."""
    seg, h = render_panel(panel, 0)
    return svg_header(h, seed=seed) + seg + svg_footer(), h


def render_strip(panels, out_path, limit=None):
    svg, y = build_strip_svg(panels, limit)
    out_path.write_text(svg, encoding="utf-8")
    return y


# ---- 유형 샘플 시트(상위 템플릿 가시화) -----------------------------------
def render_type_samples(out_path):
    # (label, shot, emotion, pose, char, dialogue, sfx, inner)
    samples = [
        ("미들·대사·stand", "medium", "smile", "stand", "엘리",
         [{"speaker": "엘리", "text": "당신, 또 서재 청소 안했지?"}], [], []),
        ("미들·phone(통화)", "medium", "neutral", "phone", "라이더",
         [{"speaker": "라이더", "text": "감독님 작품이라면 믿고 가죠."}], [], []),
        ("풀샷·run(달리기)", "full", "surprise", "run", "매리", [], ["타다닥-"], []),
        ("미들·raise_hand(손번쩍)", "medium", "serious", "raise_hand", "매리",
         [{"speaker": "매리", "text": "저.. 곡 쓸 줄 알아요!!"}], [], []),
        ("미들·arms_cross(팔짱)", "medium", "dumbfound", "arms_cross", "무결", [], [], []),
        ("미들·point(가리킴)", "medium", "neutral", "point", "정인",
         [{"speaker": "정인", "text": "밴드 해볼 생각 없어요?"}], [], []),
        ("미들·hold_head(머리부여잡)", "medium", "angry", "hold_head", "라이더",
         [{"speaker": "라이더", "text": "엘리…. 제발!!"}], [], []),
        ("미들·투샷·hug(포옹)", "medium", "happy", "hug", None, [], [], []),
        ("미들·head_down(고개숙임)", "medium", "sad", "head_down", "매리", [], [],
         [{"speaker": "매리", "text": "음악이요.. 라고 할 순 없겠지."}]),
        ("풀샷·turn_away(뒷모습)", "full", "neutral", "turn_away", "무결",
         [{"speaker": "무결", "text": "그럼 안해요."}], [], []),
    ]
    # 일부 샘플에 배경 장소 주입(쇼케이스용)
    scenes = {3: ("exterior", "street"), 8: ("establishing", "house_ext"),
              9: ("interior", "cafe"), 10: ("exterior", "street")}
    panels = []
    for i, (label, shot, emo, pose, char, dlg, fx, inner) in enumerate(samples, 1):
        sc, loc = scenes.get(i, ("blank", "unknown"))
        panels.append({
            "num": i,
            "axes": dict(A_shot=shot, B_compose=["two_shot"] if char is None else ["single"],
                         C_emotion=[emo], F_pose=pose),
            "speakers": [char] if char else ["라이더", "엘리"],
            "dialogue": dlg, "sfx": fx, "inner": inner, "narration": [],
            "description": label, "scene_resolved": sc, "location": loc,
        })
    return render_strip(panels, out_path)


# ---- 캐릭터 시트(외형 검토용) ---------------------------------------------
def render_character_sheet(out_path):
    exprs = [("neutral", "기본"), ("smile", "미소"), ("surprise", "놀람"),
             ("angry", "분노"), ("sad", "슬픔")]
    chars = list(CHARS.keys())
    cw, rh, hdr, namew = 124, 196, 44, 96
    total_w = namew + cw * len(exprs)
    total_h = hdr + rh * len(chars)
    cell_frame = dict(h=rh, head_r=48, head_cy=0.40, body="bust")
    pose_frame = dict(h=rh, head_r=30, head_cy=0.26, body="full")

    s = [svg_header(total_h, total_w)]
    # 헤더(표정 라벨)
    s.append(f'<text x="{namew/2}" y="{hdr-14}" font-family="{FONT}" font-size="20" '
             f'fill="{INK}" text-anchor="middle">캐릭터</text>')
    for j, (_, lbl) in enumerate(exprs):
        s.append(f'<text x="{namew+cw*j+cw/2}" y="{hdr-14}" font-family="{FONT}" font-size="20" '
                 f'fill="{INK}" text-anchor="middle">{lbl}</text>')
    s.append(f'<line x1="0" y1="{hdr}" x2="{total_w}" y2="{hdr}" stroke="{INK}" stroke-width="1.5"/>')

    for i, ch in enumerate(chars):
        y0 = hdr + rh * i
        info = CHARS[ch]
        # 행 구분선 + 이름/속성
        s.append(f'<line x1="0" y1="{y0}" x2="{total_w}" y2="{y0}" stroke="{INK2}" stroke-width="0.8"/>')
        s.append(f'<text x="{namew/2}" y="{y0+rh/2-6}" font-family="{FONT}" font-size="22" '
                 f'fill="{INK}" text-anchor="middle">{ch}</text>')
        s.append(f'<text x="{namew/2}" y="{y0+rh/2+18}" font-family="{FONT}" font-size="14" '
                 f'fill="{INK2}" text-anchor="middle">{info["hair"]}/{info.get("gender")}</text>')
        for j, (ex, _) in enumerate(exprs):
            cellx = namew + cw * j
            s.append(f'<g transform="translate({cellx},{y0})" filter="url(#rough)">')
            s.append(person(cw/2, cell_frame, ex, ch, facing=0.0, pose="stand"))
            s.append('</g>')
        # 마지막 칸 옆 전신 미니(첫 표정 칸 위에 살짝)… 생략(폭 유지)
    s.append(svg_footer())
    out_path.write_text("".join(s), encoding="utf-8")
    return total_h


def render_expr_sheet(out_path, char="매리"):
    """한 캐릭터 × 모든 표정 그리드."""
    exprs = [("neutral","기본"),("smile","미소"),("laugh","박장대소"),("happy","행복"),
             ("love","설렘"),("wink","윙크"),("smirk","능청"),("smug","우쭐"),
             ("surprise","놀람"),("shock","충격"),("scared","겁"),("worried","걱정"),
             ("angry","분노"),("pain","아픔"),("pout","삐짐"),("dumbfound","어이없"),
             ("flustered","당황"),("thinking","생각"),("serious","진지"),("tired","피곤"),
             ("sad","슬픔"),("crying","울음")]
    cols, cw, ch, hdr = 6, 130, 156, 50
    rows = (len(exprs)+cols-1)//cols
    total_w, total_h = cw*cols, hdr + ch*rows
    fr = dict(h=ch-26, head_r=52, head_cy=0.46, body="bust")
    s = [svg_header(total_h, total_w)]
    s.append(f'<text x="{total_w/2}" y="32" font-family="{FONT}" font-size="24" '
             f'fill="{INK}" text-anchor="middle">표정 ({char}) — {len(exprs)}종</text>')
    for i, (ex, lbl) in enumerate(exprs):
        col, row = i % cols, i // cols
        x0, y0 = col*cw, hdr + row*ch
        s.append(f'<rect x="{x0+3}" y="{y0+3}" width="{cw-6}" height="{ch-6}" fill="white" stroke="{INK2}" stroke-width="1"/>')
        s.append(f'<g transform="translate({x0},{y0})" filter="url(#rough)">')
        s.append(person(cw/2, fr, ex, char, facing=0.0, pose="stand"))
        s.append('</g>')
        s.append(f'<text x="{x0+cw/2}" y="{y0+ch-10}" font-family="{FONT}" font-size="16" '
                 f'fill="{NOTE}" text-anchor="middle">{lbl}</text>')
    s.append(svg_footer())
    out_path.write_text("".join(s), encoding="utf-8")
    return total_h


# ---- 포즈 시트(바디/포즈 검토용) ------------------------------------------
def render_pose_sheet(out_path, char="매리"):
    poses = ["stand", "walk", "run", "jump", "kick", "crossed_legs", "lean", "crouch",
             "wave", "wave_both", "raise_hand", "both_up", "point", "point_up", "beckon",
             "stop_hand", "present", "reach", "carry", "hug", "kiss",
             "arms_cross", "hands_on_hips", "hands_behind", "hands_back_head", "block", "flex",
             "think_chin", "chin_both", "scratch_head", "hold_head", "facepalm",
             "cover_face", "cover_mouth", "wipe_tears", "whisper", "listen",
             "shrug", "thumbs_up", "peace_sign", "salute", "clap", "pray",
             "phone", "look_phone", "drink", "dance", "stretch",
             "head_down", "bow", "kneel", "sit", "turn_away", "hand_no", "fall"]
    labels = {"stand": "서기", "walk": "걷기", "run": "달리기", "jump": "점프", "kick": "발차기",
              "crossed_legs": "짝다리", "lean": "기대기", "crouch": "웅크림",
              "wave": "손인사", "wave_both": "양손인사", "raise_hand": "손번쩍", "both_up": "두손들기",
              "point": "가리킴", "point_up": "위가리킴", "beckon": "이리와", "stop_hand": "멈춰",
              "present": "내밀기", "reach": "손내밈", "carry": "들기", "hug": "포옹", "kiss": "키스",
              "arms_cross": "팔짱", "hands_on_hips": "허리손", "hands_behind": "뒷짐",
              "hands_back_head": "뒤통수깍지", "block": "막기", "flex": "알통",
              "think_chin": "생각(턱)", "chin_both": "양손턱", "scratch_head": "머리긁적",
              "hold_head": "머리감싸기", "facepalm": "이마짚기",
              "cover_face": "얼굴가림", "cover_mouth": "입가림", "wipe_tears": "눈물닦기",
              "whisper": "귓속말", "listen": "귀기울임", "shrug": "어깨으쓱", "thumbs_up": "엄지척",
              "peace_sign": "브이", "salute": "경례", "clap": "박수", "pray": "기도",
              "phone": "통화", "look_phone": "폰보기", "drink": "마시기", "dance": "춤", "stretch": "기지개",
              "head_down": "고개숙임", "bow": "절", "kneel": "무릎", "sit": "앉기",
              "turn_away": "뒷모습", "hand_no": "손으로안돼", "fall": "넘어짐"}
    cols, cw, ch, hdr = 4, 156, 320, 50
    rows = (len(poses) + cols - 1) // cols
    total_w, total_h = cw*cols, hdr + ch*rows
    cell_frame = dict(h=ch-30, head_r=30, head_cy=0.13, body="full")

    s = [svg_header(total_h, total_w)]
    s.append(f'<text x="{total_w/2}" y="32" font-family="{FONT}" font-size="24" '
             f'fill="{INK}" text-anchor="middle">바디 리그 · 포즈 ({char})</text>')
    for i, p in enumerate(poses):
        col, row = i % cols, i // cols
        x0, y0 = col*cw, hdr + row*ch
        s.append(f'<rect x="{x0+4}" y="{y0+4}" width="{cw-8}" height="{ch-8}" fill="white" stroke="{INK2}" stroke-width="1"/>')
        s.append(f'<g transform="translate({x0},{y0+20})" filter="url(#rough)">')
        s.append(person(cw/2, cell_frame, "neutral", char, facing=0.0, pose=p))
        s.append('</g>')
        s.append(f'<text x="{x0+cw/2}" y="{y0+ch-12}" font-family="{FONT}" font-size="17" '
                 f'fill="{NOTE}" text-anchor="middle">{labels.get(p,p)}</text>')
    s.append(svg_footer())
    out_path.write_text("".join(s), encoding="utf-8")
    return total_h


# ---- 앵글 시트(시점 검토) -------------------------------------------------
def render_angle_sheet(out_path, char="매리"):
    views = [("front", 0.0, "정면"), ("q3", -0.85, "반측면◀"),
             ("q3", 0.85, "반측면▶"), ("profile", 1.0, "완측면▶")]
    cw, hdr = 168, 50
    total_w, total_h = cw*len(views), hdr + 260 + 330
    mframe = dict(h=250, head_r=64, head_cy=0.34, body="waist")
    fframe = dict(h=320, head_r=30, head_cy=0.13, body="full")
    s = [svg_header(total_h, total_w)]
    s.append(f'<text x="{total_w/2}" y="32" font-family="{FONT}" font-size="24" '
             f'fill="{INK}" text-anchor="middle">시점(각도) · {char}</text>')
    for j, (vw, fac, lbl) in enumerate(views):
        x0 = cw*j
        s.append(f'<text x="{x0+cw/2}" y="{hdr-6}" font-family="{FONT}" font-size="19" '
                 f'fill="{NOTE}" text-anchor="middle">{lbl}</text>')
        s.append(f'<g transform="translate({x0},{hdr})" filter="url(#rough)">')
        s.append(person(cw/2, mframe, "smile", char, facing=fac, pose="stand", view=vw))
        s.append('</g>')
        s.append(f'<g transform="translate({x0},{hdr+250})" filter="url(#rough)">')
        s.append(person(cw/2, fframe, "neutral", char, facing=fac, pose="walk", view=vw))
        s.append('</g>')
    s.append(svg_footer())
    out_path.write_text("".join(s), encoding="utf-8")
    return total_h


def render_prop_sheet(out_path):
    """소품/오브젝트 에셋 그리드 (검토용)."""
    sw = 2.2
    items = [
        ("책상", lambda x, y: prop_table(x, y-6, 116, 54, sw)),
        ("의자", lambda x, y: prop_chair(x, y+6, 64, sw)),
        ("침대", lambda x, y: prop_bed(x, y-18, 128, sw)),
        ("소파", lambda x, y: prop_sofa(x, y+4, 118, sw)),
        ("밥그릇", lambda x, y: prop_bowl(x, y+30, 70, sw)),
        ("숟가락", lambda x, y: prop_spoon(x, y+26, 76, sw)),
        ("컵", lambda x, y: prop_cup(x, y+28, 70, sw)),
        ("접시", lambda x, y: prop_plate(x, y+24, 80, sw)),
        ("책", lambda x, y: prop_book(x, y+18, 84, sw)),
        ("노트북", lambda x, y: prop_laptop(x, y+34, 86, sw)),
        ("책더미", lambda x, y: prop_books(x, y, 86, sw)),
        ("커피", lambda x, y: prop_coffee(x, y, 80, sw)),
        ("우산", lambda x, y: prop_umbrella(x, y, 96, sw)),
        ("핸드백", lambda x, y: prop_bag(x, y, 90, sw)),
        ("백팩", lambda x, y: prop_backpack(x, y, 92, sw)),
        ("화분", lambda x, y: prop_plant(x, y, 96, sw)),
        ("시계", lambda x, y: prop_clock(x, y, 92, sw)),
        ("스마트폰", lambda x, y: prop_phone2(x, y, 86, sw)),
        ("기타", lambda x, y: prop_guitar(x, y, 100, sw)),
        ("마이크", lambda x, y: prop_mic(x, y, 92, sw)),
        ("풍선", lambda x, y: prop_balloon(x, y, 92, sw)),
        ("선물", lambda x, y: prop_gift(x, y, 90, sw)),
        ("꽃", lambda x, y: prop_flower(x, y, 96, sw)),
        ("카메라", lambda x, y: prop_camera(x, y, 90, sw)),
        ("물병", lambda x, y: prop_bottle(x, y, 96, sw)),
        ("케이크", lambda x, y: prop_cake(x, y, 90, sw)),
        ("모자", lambda x, y: prop_hat(x, y, 96, sw)),
        ("안경", lambda x, y: prop_glasses(x, y, 96, sw)),
        ("공", lambda x, y: prop_ball(x, y, 90, sw)),
        ("캐리어", lambda x, y: prop_suitcase(x, y, 92, sw)),
    ]
    cols, cw, ch, hdr = 5, 156, 156, 50
    rows = (len(items)+cols-1)//cols
    total_w, total_h = cw*cols, hdr + ch*rows
    s = [svg_header(total_h, total_w)]
    s.append(f'<text x="{total_w/2}" y="32" font-family="{FONT}" font-size="24" '
             f'fill="{INK}" text-anchor="middle">소품 에셋 — {len(items)}종</text>')
    for i, (lbl, fn) in enumerate(items):
        col, row = i % cols, i // cols
        x0, y0 = col*cw, hdr + row*ch
        s.append(f'<rect x="{x0+3}" y="{y0+3}" width="{cw-6}" height="{ch-6}" fill="white" stroke="{INK2}" stroke-width="1"/>')
        s.append(f'<g filter="url(#rough)">')
        s.append(fn(x0+cw/2, y0+ch/2))
        s.append('</g>')
        s.append(f'<text x="{x0+cw/2}" y="{y0+ch-12}" font-family="{FONT}" font-size="17" '
                 f'fill="{NOTE}" text-anchor="middle">{lbl}</text>')
    s.append(svg_footer())
    out_path.write_text("".join(s), encoding="utf-8")
    return total_h


def main():
    OUT_DIR.mkdir(exist_ok=True)
    # 0) 캐릭터 시트(외형 검토)
    render_character_sheet(OUT_DIR / "_character_sheet.svg")
    print("✓ output/_character_sheet.svg  (캐릭터 × 표정 그리드)")
    render_prop_sheet(OUT_DIR / "_prop_sheet.svg")
    print("✓ output/_prop_sheet.svg  (소품 에셋)")
    render_expr_sheet(OUT_DIR / "_expr_sheet.svg")
    print("✓ output/_expr_sheet.svg  (표정 22종)")
    render_pose_sheet(OUT_DIR / "_pose_sheet.svg")
    print("✓ output/_pose_sheet.svg  (바디 리그 × 포즈)")
    render_angle_sheet(OUT_DIR / "_angle_sheet.svg")
    print("✓ output/_angle_sheet.svg  (시점 각도)")
    # 1) 유형 샘플 시트
    render_type_samples(OUT_DIR / "_type_samples.svg")
    print("✓ output/_type_samples.svg  (상위 8개 유형 템플릿 가시화)")
    # 2) 실제 에피소드 스트립
    ep = json.load(open(CLS_DIR / "풀하우스_EP01.json", encoding="utf-8"))
    h = render_strip(ep["panels"], OUT_DIR / "풀하우스_EP01_strip.svg", limit=12)
    print(f"✓ output/풀하우스_EP01_strip.svg  (1~12컷, 높이 {h}px)")


if __name__ == "__main__":
    main()
