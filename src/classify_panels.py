# -*- coding: utf-8 -*-
"""
글콘티 패널 5축 분류기 (2~3번 단계)

입력: data/glconti/*.txt  (PDF에서 추출된 글콘티 원문)
출력: data/classified/
    - <title>_EP##.json   : 패널 단위 구조화 + 5축 라벨
    - _taxonomy.json      : 축별 어휘/분포
    - _types.json         : 유형(축 조합) 시그니처 랭킹  ← "유형 N개"의 답
    - 콘솔: 사람이 읽는 요약

5축:
  A. shot      샷 프레이밍(카메라 거리)      → 캔버스 박스 + 인물 스케일
  B. compose   구도/인원/앵글/연속성          → 인물 배치 레이아웃
  C. emotion   표정/감정                       → 캐릭터 표정 슬롯
  D. text      말풍선/텍스트 종류             → 버블/레터링 배치
  E. scene     배경/씬                         → 배경 레이어
  (+flags: 회상 flashback / 효과 effect)
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Windows 콘솔(cp949)에서도 UTF-8 / 박스문자 출력
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "data" / "glconti"
OUT_DIR = ROOT / "data" / "classified"

# ---------------------------------------------------------------------------
# 정규화 사전 (raw 문자열 → 표준 라벨)
# ---------------------------------------------------------------------------

# A. 샷 프레이밍 — 우선순위 순서대로 매칭(구체적인 것 먼저)
SHOT_RULES = [
    ("extreme_closeup", ["익스트림 클로즈업", "익스트림클로즈업", "익스트림"]),
    ("closeup",         ["클로즈업"]),                # 부위 클로즈업도 일단 closeup, 부위는 focus로 따로
    ("medium",          ["미디엄", "미들"]),
    ("full",            ["풀샷", "풀 샷"]),
    ("long",            ["롱샷", "롱 샷"]),
    ("insert",          ["인서트"]),
    ("sd",              ["sd컷", "sd"]),
    ("title",           ["타이틀"]),
]

# 부위/대상 클로즈업 감지 (예: "손 클로즈업", "고양이 발 클로즈업", "매리 얼굴 클로즈업샷")
BODYPART_RE = re.compile(r"([가-힣A-Za-z]+(?:\s*[가-힣A-Za-z]+)?)\s*(?:얼굴|손|발|눈|입|뒷모습)?\s*클로즈업")

# B. 구도 modifier 키워드
COMPOSE_KEYWORDS = {
    "two_shot":  ["투샷", "투 샷", "둘의", "두 인물", "두개", "두 개"],
    "group":     ["사람들", "인파", "군중", "하객", "관중", "모두", "여럿", "다들", "무리", "손님들"],
    "sequence":  ["연속컷", "연속 컷", "연속"],          # 한 패널 안 여러 비트(몽타주)
    "solo":      ["단독샷", "단독컷", "단독"],
    "ots":       ["어깨너머", "어깨 너머"],
    "frontal":   ["정면"],
    "low_angle": ["로우앵글", "로우 앵글"],
    "high_angle":["하이앵글", "하이 앵글"],
    "cross":     ["크로스"],
}

# C. 감정/표정 키워드 (description 본문에서 탐지; 구체적인 신규 표정을 위로)
EMOTION_KEYWORDS = {
    "love":       ["설렘", "반한", "반해", "두근", "하트", "사랑스", "심쿵"],
    "laugh":      ["박장대소", "깔깔", "폭소", "빵 터", "자지러", "크게 웃", "껄껄"],
    "wink":       ["윙크"],
    "smug":       ["우쭐", "뿌듯", "의기양양", "자랑스", "잘난척", "득의"],
    "smirk":      ["씨익", "능청", "음흉", "비죽 웃", "씩 웃", "히죽"],
    "pout":       ["삐짐", "삐친", "토라", "뾰로통", "입을 삐죽", "입을 내밀"],
    "scared":     ["겁먹", "무서", "두려", "벌벌", "겁에 질", "오싹"],
    "pain":       ["아파", "아픈", "찡그", "인상을 쓰", "신음", "고통"],
    "tired":      ["피곤", "지친", "졸린", "나른", "녹초", "축 처", "지쳐"],
    "worried":    ["걱정", "근심", "불안", "초조", "조마조마", "노심초사"],
    "smile":      ["웃", "미소", "피식"],
    "happy":      ["행복", "기분 좋", "기분이 좋", "신나"],
    "thinking":   ["생각", "고민", "속마음", "골똘"],
    "surprise":   ["놀란", "놀라", "깜짝", "멈칫"],
    "serious":    ["진지", "결연", "똑바로"],
    "flustered":  ["당황", "우물쭈물", "쑥스", "빨개", "홍조", "민망"],
    "dumbfound":  ["어이없", "황당", "뚱한", "어처구니"],
    "crying":     ["눈물", "울음", "울먹", "우는", "울고", "흐느", "훌쩍", "훔친"],  # '울리는' 오탐 방지
    "angry":      ["분노", "화내", "화난", "씩씩", "째려", "소리치", "소리지"],
    "shock":      ["충격", "기겁", "넋"],
    "sad":        ["슬픈", "슬프", "기죽", "심란", "한숨", "쓴 웃음", "쓴웃음"],
    "curious":    ["호기심", "궁금", "의문"],
}

# E. 씬/배경 키워드
SCENE_KEYWORDS = {
    "establishing": ["외관", "전경", "전경.", "풀하우스 앞", "거리", "길거리", "공연장", "콘서트"],
    "exterior":     ["밖", "정원", "야외", "거리", "길", "공원"],
    "interior":     ["카페", "집", "방", "서재", "조리실", "지하", "다락", "실내", "무대", "카운터", "작업실"],
    "symbolic":     ["번개", "천둥", "먹구름", "빛", "번쩍", "먼지", "안개", "유적", "설계도"],
}

# 포즈/동작 (description에서 탐지, 우선순위 순 — 구체적인 것 먼저)
POSE_KEYWORDS = [
    ("kiss",        ["키스"]),
    ("hug",         ["안아", "껴안", "안고", "포옹", "끌어안"]),
    ("phone",       ["통화", "전화", "핸드폰", "폰을", "이어폰을 낀", "이어폰 낀"]),
    ("look_phone",  ["스크롤", "화면을", "댓글", "핸드폰을 보", "폰을 보"]),
    ("scratch_head",["머리를 긁", "뒤통수를 긁", "긁적", "머쓱"]),
    ("hold_head",   ["머리를 부여잡", "머리를 감싸", "부여잡", "머리를 쥐"]),
    ("think_chin",  ["턱을 괴", "턱에 손", "턱을 만지", "곰곰", "골똘"]),
    ("cover_face",  ["얼굴을 가리", "손으로 얼굴", "낯을 가리"]),
    ("both_up",     ["만세", "두 손을 들", "두손을 들", "두 팔을 들", "환호", "두 손 번쩍", "두손 번쩍"]),
    ("hand_no",     ["손을 내저", "손사래", "손을 휘저", "절레절레", "손을 흔들며 거부", "손을 들어 거부"]),
    ("raise_hand",  ["손을 번쩍", "치켜", "번쩍 든", "손을 들", "손을 올"]),
    ("reach",       ["손을 내밀", "내밀며", "건넨다", "건네", "손을 잡", "잡는다"]),
    ("point",       ["가리키", "가리킨다"]),
    ("stretch",     ["기지개"]),
    ("arms_cross",  ["팔짱", "팔을 꼬"]),
    ("hands_on_hips",["허리에 손", "허리춤", "양손을 허리", "팔을 허리", "허리에 양손"]),
    ("clap",        ["박수", "손뼉", "짝짝짝"]),
    ("thumbs_up",   ["엄지", "엄지척", "따봉", "엄지를 들"]),
    ("peace_sign",  ["브이", "브이를", "손가락 브이", "검지와 중지"]),
    ("facepalm",    ["이마를 짚", "이마에 손", "얼굴을 쓸", "이마를 감싸"]),
    ("shrug",       ["어깨를 으쓱", "으쓱", "어깨를 들썩"]),
    ("beckon",      ["손짓", "오라고", "손가락을 까딱", "이리 오라"]),
    ("clap",        ["손뼉을 치"]),
    ("jump",        ["점프", "펄쩍", "뛰어오르", "폴짝"]),
    ("pray",        ["기도", "두 손을 모", "손을 모으", "간청", "애원", "빌어", "빈다"]),
    ("drink",       ["마신다", "마시", "한 모금", "잔을 들", "컵을 들", "들이켠"]),
    ("dance",       ["춤", "댄스", "춤춘"]),
    ("bow",         ["절을", "절한", "고개 숙여 인사", "허리 굽혀", "굽신", "꾸벅"]),
    ("kneel",       ["무릎을 꿇", "무릎 꿇", "주저앉아 무릎"]),
    ("carry",       ["들고 있", "안아 들", "옮기", "나르", "받쳐 들"]),
    ("crouch",      ["쪼그려", "웅크", "움츠"]),
    ("sit",         ["앉아", "앉은", "앉는다", "주저앉", "걸터앉", "의자에", "소파에 앉"]),
    ("fall",        ["고꾸라", "넘어", "쓰러", "자빠"]),
    ("run",         ["뛰어", "달려", "달린다", "헤치고", "뛰쳐"]),
    ("walk",        ["걷는", "걸어가", "걸어간다", "걸음", "거니", "산책", "걸어"]),
    ("head_down",   ["고개를 숙", "고개 숙", "바닥을 쳐다", "풀이 죽"]),
    ("turn_away",   ["등을 돌려", "뒤돌아", "돌아선", "등을 보이"]),
    ("wave",        ["손을 흔", "인사한다", "인사하"]),
]

# 시점(VIEW): 카메라 각도
VIEW_KEYWORDS = [
    ("profile", ["옆모습", "옆얼굴", "측면", "옆에서", "프로필", "옆으로"]),
    ("q3",      ["반측면", "비스듬", "어깨너머", "고개를 돌려", "돌아보", "마주보", "돌아본다"]),
]

# 장소(LOCATION): 구체 장소 → (location, scene_type). 상속(forward-fill)의 단위.
# scene_type: interior / exterior / establishing  (symbolic은 일시 효과라 상속 안 함)
LOCATION_KEYWORDS = [
    ("house_ext", "establishing", ["풀하우스 외관", "풀하우스 앞", "풀하우스 전경", "집 외관", "외관", "전경"]),
    ("cafe",      "interior",     ["카페", "카운터", "조리실", "매장"]),
    ("study",     "interior",     ["서재"]),
    ("attic",     "interior",     ["다락"]),
    ("basement",  "interior",     ["지하", "비밀공간", "비밀 공간", "유적"]),
    ("bedroom",   "interior",     ["침대", "침실"]),
    ("studio",    "interior",     ["작업실", "스튜디오"]),
    ("stage",     "interior",     ["무대", "공연", "콘서트"]),
    ("home",      "interior",     ["집", "거실", "방 ", "방.", "방안", "방 안"]),
    ("street",    "exterior",     ["길거리", "거리", "길을", "길 ", "인파"]),
    ("garden",    "exterior",     ["정원", "공원", "마당"]),
]

# 특수 플래그
FLASHBACK_KW = ["회상", "과거", "시절", "었던 시절"]
EFFECT_KW = ["번쩍", "빛으로", "휩싸", "진동", "흔들", "화악", "변해", "젊게"]

# ---------------------------------------------------------------------------
# 파싱
# ---------------------------------------------------------------------------

ZW = "".join(["​", "‌", "‍", "﻿", "⁠"])  # zero-width 류
PANEL_START = re.compile(r"^\s*(\d+)\.\s*", re.M)


def clean(s: str) -> str:
    s = "".join(ch for ch in s if ch not in ZW)
    s = s.replace(" ", " ")
    return s


def load_panels_from_text(raw: str):
    """원문 문자열 → [(num, raw_body)] 패널 단위 분리 (줄바꿈으로 잘린 패널 병합)."""
    raw = clean(raw)
    lines = [ln for ln in raw.splitlines() if not ln.lstrip().startswith("#")]
    body = "\n".join(lines)
    matches = list(PANEL_START.finditer(body))
    panels = []
    for i, m in enumerate(matches):
        num = int(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        chunk = body[start:end].strip()
        chunk = re.sub(r"\s*\n\s*", " ", chunk).strip()  # 줄바꿈 병합
        if chunk:
            panels.append((num, chunk))
    return panels


def load_panels(txt_path: Path):
    """txt 파일 → [(num, raw_body)]."""
    return load_panels_from_text(txt_path.read_text(encoding="utf-8"))


def panels_from_text(raw: str):
    """원문 → 분류·배경상속까지 끝낸 panel dict 리스트 (단일 진입점용)."""
    panels = [classify_panel(n, b) for n, b in load_panels_from_text(raw)]
    resolve_backgrounds(panels)
    return panels


def split_speakers(s: str):
    """'엘리, 라이더' → ['엘리','라이더']. 쉼표/가운뎃점/슬래시로 분리."""
    parts = re.split(r"[,，、/·]", s or "")
    return [p.strip() for p in parts if p.strip()]


def extract_fields(body: str):
    """패널 본문 → shot_raw, description, dialogue[], sfx[], narration[], inner[], lyrics[]"""
    shot_raw = None
    m = re.match(r"\s*\[([^\]]*)\]", body)
    rest = body
    if m:
        shot_raw = m.group(1).strip()
        rest = body[m.end():].strip()

    # '/' 로 구분된 세그먼트
    segs = [s.strip() for s in rest.split("/") if s.strip()]

    description_parts = []
    dialogue, sfx, narration, inner, lyrics = [], [], [], [], []

    # 화자: 쉼표/가운뎃점으로 합쳐진 다중 화자도 허용 (예: "엘리, 라이더:")
    speaker_re = re.compile(r"^([가-힣A-Za-z0-9 ,，、·]{1,18})\s*[:：]\s*(.*)$")
    for seg in segs:
        if seg.startswith("효과음"):
            after = seg.split(":", 1)[-1].split("：", 1)[-1].strip()
            sfx.append(after)
            continue
        if seg.startswith("나레이션") or seg.startswith("내레이션"):
            after = seg.split(":", 1)[-1].split("：", 1)[-1].strip()
            narration.append(after)
            continue
        sm = speaker_re.match(seg)
        if sm:
            speaker, line = sm.group(1).strip(), sm.group(2).strip()
            if "노래" in speaker or "가사" in line or "노래 가사" in seg:
                lyrics.append({"speaker": speaker, "text": line})
            elif "속마음" in line or "(속마음)" in seg:
                inner.append({"speaker": speaker, "text": line.replace("(속마음)", "").strip()})
            else:
                # 속마음이 line 앞쪽에 붙는 경우 처리
                if line.startswith("(속마음)"):
                    inner.append({"speaker": speaker, "text": line.replace("(속마음)", "").strip()})
                else:
                    dialogue.append({"speaker": speaker, "text": line})
            continue
        # 화자 없는 따옴표 대사 (예: '“.....”')
        if seg.startswith("“") or seg.startswith("\"") or seg.startswith("‘"):
            dialogue.append({"speaker": None, "text": seg})
            continue
        # 묘사 안에 큰따옴표 대사가 섞인 경우 → 대사로 추출 (예: 여자가 말한다 "사랑해")
        quotes = re.findall(r'["“]([^"”]{1,60})["”]', seg)
        if quotes:
            for q in quotes:
                if q.strip():
                    dialogue.append({"speaker": None, "text": q.strip()})
            seg = re.sub(r'["“][^"”]{1,60}["”]', "", seg).strip()
        if seg:
            description_parts.append(seg)

    description = " ".join(description_parts).strip()
    return {
        "shot_raw": shot_raw,
        "description": description,
        "dialogue": dialogue,
        "sfx": sfx,
        "narration": narration,
        "inner": inner,
        "lyrics": lyrics,
    }


# ---------------------------------------------------------------------------
# 5축 분류
# ---------------------------------------------------------------------------

# 무브래킷 패널 샷 추론 키워드 (우선순위 순)
INFER_SHOT = [
    ("insert",  ["화면", "사진", "액자", "신문", "핸드폰 화면", "댓글", "문자", "메모", "편지", "간판", "팻말"]),
    ("long",    ["전경", "외관", "전체", "멀리", "풍경", "원경", "건물", "하늘"]),
    ("full",    ["뒷모습", "전신", "걸어", "걷는", "달려", "뛰어", "서 있", "앉아", "전체 모습"]),
    ("closeup", ["얼굴", "표정", "눈물", "미소", "눈", "입", "볼", "이마"]),
]


def classify_shot(shot_raw, description):
    text = (shot_raw or "")
    low = text.lower().replace(" ", "")
    # 복합 브래킷에서 여러 샷이 보이면 가장 '가까운'(클로즈업 우선) 것을 채택
    hits = [lab for lab, keys in SHOT_RULES
            if any(k.lower().replace(" ", "") in low for k in keys)]
    label = hits[0] if hits else "unspecified"
    # 브래킷이 없거나 미지정이면 묘사에서 추론
    if label == "unspecified":
        for lab, keys in INFER_SHOT:
            if any(k in description for k in keys):
                label = lab
                break
        if label == "unspecified":
            label = "medium"   # 합리적 기본값(대사 컷 다수)
    # 부위 클로즈업 focus 대상
    focus = None
    if "closeup" in label or label == "insert":
        for part in ["얼굴", "손", "발", "눈", "입", "뒷모습"]:
            if part in (shot_raw or "") + description:
                focus = part
                break
    return label, focus


def classify_compose(shot_raw, description, n_speakers):
    text = (shot_raw or "") + " " + description
    mods = []
    for lab, keys in COMPOSE_KEYWORDS.items():
        if any(k in text for k in keys):
            mods.append(lab)
    # 인원 추정: two_shot 명시 or 화자 2명 이상
    if "two_shot" not in mods and n_speakers >= 2:
        mods.append("two_shot")
    if not mods:
        mods.append("single")
    return sorted(set(mods))


def classify_emotion(description, inner):
    text = description + " " + " ".join(i["text"] for i in inner)
    found = []
    for lab, keys in EMOTION_KEYWORDS.items():
        if any(k in text for k in keys):
            found.append(lab)
    return found or ["neutral"]


def classify_text(fields):
    t = []
    if fields["dialogue"]:
        t.append("dialogue")
    if fields["narration"]:
        t.append("narration")
    if fields["inner"]:
        t.append("inner_thought")
    if fields["sfx"]:
        t.append("sfx")
    if fields["lyrics"]:
        t.append("lyrics")
    return t or ["silent"]


def classify_scene(description):
    found = []
    for lab, keys in SCENE_KEYWORDS.items():
        if any(k in description for k in keys):
            found.append(lab)
    return found or ["unspecified"]


def classify_pose(description):
    for lab, keys in POSE_KEYWORDS:
        if any(k in description for k in keys):
            return lab
    return "stand"


def classify_view(description):
    for lab, keys in VIEW_KEYWORDS:
        if any(k in description for k in keys):
            return lab
    return "front"


def detect_location(description):
    """명시적 장소 탐지 → (location, scene_type) 또는 (None, None)."""
    for loc, scene, keys in LOCATION_KEYWORDS:
        if any(k in description for k in keys):
            return loc, scene
    return None, None


# 작품 주요 등장인물 (묘사에서 이름 추출용)
KNOWN_CHARS = ["엘리", "라이더", "민준석", "매리", "무결", "정인",
               "신성우", "하은", "주태경", "루나", "이한", "찬"]
# 2인 신호(대명사) — 이름 없으면 직전 인물 상속. '둘러보다' 오탐 피하려 경계 포함.
PAIR_KW = ["두 사람", "두사람", "둘이", "둘의", "둘을", "둘,", "둘.", "둘 ",
           "서로", "마주보", "마주 보", "두 명", "두명", "양쪽", "투샷", "투 샷"]
GROUP_KW2 = ["사람들", "인파", "군중", "하객", "관중", "무리", "손님들",
             "셋이", "세 사람", "세사람", "다들", "모두가"]


# 일반 성별 단어(이름 없을 때 성별 추정)
FEMALE_WORDS = ["여자", "여성", "소녀", "그녀", "엄마", "어머니", "누나", "언니",
                "할머니", "아줌마", "아주머니", "아가씨", "여학생", "여자아이", "딸", "이모", "고모"]
MALE_WORDS = ["남자", "남성", "소년", "아빠", "아버지", "오빠", "할아버지",
              "아저씨", "남학생", "남자아이", "아들", "삼촌", "청년", "사내"]


def detect_gender_word(desc):
    """묘사의 일반 성별어로 성별 추정. 둘 다/없으면 None."""
    f = any(w in desc for w in FEMALE_WORDS)
    m = any(w in desc for w in MALE_WORDS)
    if f and not m:
        return "F"
    if m and not f:
        return "M"
    return None


def detect_cast(desc):
    """묘사에서 알려진 인물 이름을 등장 순서대로(중복 제거)."""
    found = sorted((desc.find(n), n) for n in KNOWN_CHARS if n in desc)
    out = []
    for _, n in found:
        if n not in out:
            out.append(n)
    return out


def detect_actors(desc):
    """등장인물 = 이름 + 일반 성별어(남자/여자 등). 각 (name|None, gender|None), 등장순."""
    found = [(desc.find(n), n, None) for n in KNOWN_CHARS if n in desc]
    mis = [desc.find(w) for w in MALE_WORDS if w in desc]
    fis = [desc.find(w) for w in FEMALE_WORDS if w in desc]
    if mis:
        found.append((min(mis), None, "M"))
    if fis:
        found.append((min(fis), None, "F"))
    found.sort()
    out, seen = [], set()
    for _, n, g in found:
        key = n if n else ("g", g)
        if key in seen:
            continue
        seen.add(key)
        out.append((n, g))
    return out


def resolve_backgrounds(panels):
    """패널 순회: 장소 forward-fill + 등장인물(cast)/인원수 해소.
    '둘/서로' 같은 대명사만 있으면 직전 인물을 상속한다."""
    cur_loc, cur_scene = None, None
    recent_actors = []
    for p in panels:
        desc = p.get("description", "")
        # --- 장소 ---
        loc, scene = detect_location(desc)
        if "flashback" in p.get("flags", []) and loc is None:
            cur_loc, cur_scene = loc, scene
        if loc is not None:
            cur_loc, cur_scene = loc, scene
        p["location"] = cur_loc or "unknown"
        p["scene_resolved"] = cur_scene or "blank"
        p["scene_explicit"] = loc is not None

        # --- 등장인물(이름+성별) / 인원수 ---
        actors = detect_actors(desc)         # [(name|None, gender|None), ...]
        is_group = any(k in desc for k in GROUP_KW2)
        is_pair = any(k in desc for k in PAIR_KW)
        speakers = p.get("speakers", [])
        spk_known = [(s, None) for s in speakers if s in KNOWN_CHARS]
        if actors:
            cur = actors
            recent_actors = actors
        elif spk_known:
            cur = spk_known
            recent_actors = spk_known
        elif (is_pair or is_group) and recent_actors:
            cur = recent_actors[:]           # 대명사 → 직전 인물 상속
        else:
            cur = actors                     # []
        # 인원수 판정
        two_in_compose = "two_shot" in p["axes"]["B_compose"]
        if is_group or len(cur) >= 3:
            people = "group"
        elif is_pair or two_in_compose or len(cur) >= 2 or len(speakers) >= 2:
            people = 2
        else:
            people = 1
        p["actors"] = cur
        p["cast"] = [n for n, g in cur if n]   # 이름만(하위호환)
        p["n_people"] = people
        # B_compose 동기화
        comp = set(p["axes"]["B_compose"])
        if people == "group":
            comp.add("group"); comp.discard("single")
        elif people == 2:
            comp.add("two_shot"); comp.discard("single")
        p["axes"]["B_compose"] = sorted(comp)


def classify_panel(num, body):
    fields = extract_fields(body)
    speakers = set()
    for grp in ("dialogue", "inner", "lyrics"):
        for d in fields[grp]:
            if d.get("speaker"):
                for nm in split_speakers(d["speaker"]):   # 합쳐진 화자 분리
                    speakers.add(nm)
    shot, focus = classify_shot(fields["shot_raw"], fields["description"])
    desc = fields["description"]
    axes = {
        "A_shot": shot,
        "A_focus": focus,
        "B_compose": classify_compose(fields["shot_raw"], desc, len(speakers)),
        "C_emotion": classify_emotion(desc, fields["inner"]),
        "D_text": classify_text(fields),
        "E_scene": classify_scene(desc),
        "F_pose": classify_pose(desc),
        "G_view": classify_view(desc),
    }
    flags = []
    alltext = desc + " " + " ".join(n for n in fields["narration"])
    if any(k in alltext for k in FLASHBACK_KW):
        flags.append("flashback")
    if any(k in desc for k in EFFECT_KW):
        flags.append("effect")
    return {
        "num": num,
        **fields,
        "speakers": sorted(speakers),
        "axes": axes,
        "flags": flags,
        "gender_hint": detect_gender_word(desc),   # 일반 성별어(여자/남자 등)
    }


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    txts = sorted(SRC_DIR.glob("*.txt"))

    all_panels = []
    per_axis = {a: Counter() for a in ["A_shot", "B_compose", "C_emotion", "D_text", "E_scene"]}
    type_sig = Counter()       # (shot, compose-primary, text-primary)
    flag_counter = Counter()

    for txt in txts:
        title_ep = txt.stem  # e.g. 풀하우스_EP01
        panels_raw = load_panels(txt)
        panels = [classify_panel(n, b) for n, b in panels_raw]
        resolve_backgrounds(panels)  # 장소 상속(forward-fill)

        out = {"file": txt.name, "panel_count": len(panels), "panels": panels}
        (OUT_DIR / f"{title_ep}.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        for p in panels:
            all_panels.append(p)
            ax = p["axes"]
            per_axis["A_shot"][ax["A_shot"]] += 1
            for v in ax["B_compose"]:
                per_axis["B_compose"][v] += 1
            for v in ax["C_emotion"]:
                per_axis["C_emotion"][v] += 1
            for v in ax["D_text"]:
                per_axis["D_text"][v] += 1
            for v in ax["E_scene"]:
                per_axis["E_scene"][v] += 1
            for f in p["flags"]:
                flag_counter[f] += 1
            per_axis.setdefault("scene_resolved", Counter())[p["scene_resolved"]] += 1
            per_axis.setdefault("location", Counter())[p["location"]] += 1
            # 유형 시그니처: 샷 × 구도주축 × 텍스트주축
            compose_primary = "two_shot" if "two_shot" in ax["B_compose"] else (
                "sequence" if "sequence" in ax["B_compose"] else "single")
            text_primary = ax["D_text"][0]
            type_sig[(ax["A_shot"], compose_primary, text_primary)] += 1

    # 저장: taxonomy
    taxonomy = {a: dict(c.most_common()) for a, c in per_axis.items()}
    taxonomy["flags"] = dict(flag_counter.most_common())
    taxonomy["total_panels"] = len(all_panels)
    taxonomy["episodes"] = len(txts)
    (OUT_DIR / "_taxonomy.json").write_text(
        json.dumps(taxonomy, ensure_ascii=False, indent=2), encoding="utf-8")

    # 저장: types (유형 N개)
    types = [{"shot": k[0], "compose": k[1], "text": k[2], "count": v}
             for k, v in type_sig.most_common()]
    (OUT_DIR / "_types.json").write_text(
        json.dumps({"distinct_types": len(types), "types": types},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    # 콘솔 요약
    print(f"=== 분류 완료: {len(txts)}화 / {len(all_panels)} 패널 ===\n")
    titles = {"A_shot": "A. 샷 프레이밍", "B_compose": "B. 구도/인원",
              "C_emotion": "C. 감정/표정", "D_text": "D. 텍스트", "E_scene": "E. 씬/배경"}
    for a in ["A_shot", "B_compose", "C_emotion", "D_text", "E_scene"]:
        print(f"[{titles[a]}]")
        for k, v in per_axis[a].most_common():
            bar = "█" * max(1, round(v / max(per_axis[a].values()) * 24))
            print(f"  {k:16s} {v:4d}  {bar}")
        print()
    print("[특수 플래그]")
    for k, v in flag_counter.most_common():
        print(f"  {k:16s} {v:4d}")
    print()
    print(f"[유형(축 조합) 개수] = {len(types)}개  (상위 15개)")
    for t in types[:15]:
        print(f"  {t['count']:4d}  {t['shot']:16s} | {t['compose']:9s} | {t['text']}")
    cover = sum(t['count'] for t in types[:15])
    print(f"\n  상위 15개 유형이 전체의 {cover/len(all_panels)*100:.1f}% 커버")


if __name__ == "__main__":
    main()
