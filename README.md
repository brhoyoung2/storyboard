# 글콘티 → 그림콘티 (Storyboard SVG)

텍스트 콘티(글콘티)를 넣으면 그림 콘티를 **SVG**로 자동 생성하는 도구.
손그림(rough) 필터·손글씨 폰트, 흑백/컬러, 캐릭터·포즈·표정·시점 표현.

## 🌐 웹에서 바로 사용
**https://storyboard-jet-pi.vercel.app** — 설치 없이 `직접 생성` 탭에서 글콘티 입력 → 생성.

## 입력 형식
```
번호. [샷] 상황묘사 / 화자: "대사"
```
- 샷: `풀샷` · `미들샷` · `클로즈업` · `롱샷`
- 인물 이름(매리·라이더·엘리·무결 등) → 색·성별 자동 / 일반어(여자·남자)도 인식
- `둘`/`서로` → 2명, `사람들` → 다인물, `(속마음)` → 생각 풍선, `나레이션:` → 하단 박스, `효과음:` → 손글씨

## 로컬 실행
```bash
python src/server.py          # http://127.0.0.1:8000 (뷰어 + 실시간 생성)
python src/generate.py 콘티.txt   # 파일 1개 → SVG (.pdf 입력도 가능, PyMuPDF 필요)
```
Windows는 `서버실행.bat` 더블클릭.

## 구조
```
api/generate.py    Vercel 서버리스 함수 (POST /api/generate)
src/
  classify_panels.py  글콘티 파싱·6축 분류(샷/구도/감정/텍스트/씬/포즈)+성별·등장인물
  svg_render.py       SVG 렌더(관절 리그·표정·포즈·시점·말풍선·배경)
  server.py           로컬 웹서버(정적+생성)
  build_viewer.py     뷰어 HTML 생성
  batch_generate.py   data의 20화 일괄 생성
output/            정적 산출물(index.html, viewer.html, refs/, strips/)
vercel.json        Vercel 설정(정적 + python 함수)
```

분류기/렌더러(텍스트→SVG)는 **파이썬 표준 라이브러리만** 사용(외부 의존성 없음).
