# 완결각

쌓아 둔 노션 노트를 **하루 가용시간에 맞춘 웹소설식 회차**로 나눠 하루 한 화씩 보여 주는 웹앱.
기획: [docs/PRD_v0.3.md](docs/PRD_v0.3.md) · 디자인 시스템: [design/DESIGN.md](design/DESIGN.md)

## 구조
```
app.py          Flask 웹앱 (라우트) — Vercel이 자동 인식
wangyeol/       로직: parser(노션→조각) planner(회차 분할) rules(도착·선물) service(화면 상태)
                notion(노션 API) store(저장: Upstash Redis / 구글 시트 / 로컬 JSON) redis_store sheets auth render
templates/      화면 HTML (Jinja)
static/         tokens.css components.css app.js
design/         tokens.json build_tokens.py sync_figma_tokens.py DESIGN.md
docs/           PRD
tests/          pytest
```
