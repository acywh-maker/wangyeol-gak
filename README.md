# 완결각

쌓아 둔 노션 노트를 **하루 가용시간에 맞춘 웹소설식 회차**로 나눠 하루 한 화씩 보여 주는 웹앱.
기획: [docs/PRD_v0.3.md](docs/PRD_v0.3.md) · 디자인 시스템: [design/DESIGN.md](design/DESIGN.md)

## 구조
```
app.py          Flask 웹앱 (라우트) — Vercel이 자동 인식
wangyeol/       로직: parser(노션→조각) planner(회차 분할) rules(도착·선물) service(화면 상태)
                notion(노션 API) store(저장: 구글 시트 / 로컬 JSON) sheets auth render(블록→HTML)
templates/      화면 HTML (Jinja)
static/         tokens.css components.css app.js
design/         tokens.json build_tokens.py sync_figma_tokens.py DESIGN.md
docs/           PRD
tests/          pytest
```

## 로컬 실행
```bash
pip install -r requirements.txt
cp .env.example .env      # 값 채우기 (SHEET_ID가 비어 있으면 data/store.json에 저장)
python app.py             # http://localhost:8510
python -m pytest -q       # 테스트
```

## 배포 (Vercel)
1. Vercel에 GitHub로 로그인 → **Add New Project** → 이 저장소 선택 (Framework: 자동 감지 Flask)
2. **Environment Variables**에 `.env.example`의 항목을 넣는다 (`DEV_MODE`는 넣지 않는다)
3. Deploy. 이후 `main`에 푸시할 때마다 자동 배포
- 서버리스라 로컬 파일 저장은 유지되지 않는다 → 운영에는 **구글 시트 필수** (`SHEET_ID`, `GCP_SERVICE_ACCOUNT_JSON`)
- Streamlit 버전은 `streamlit-v1` 태그에 남아 있다
