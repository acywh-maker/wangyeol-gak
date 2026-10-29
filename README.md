# 완결각 디자인 시스템

| 파일 | 역할 | 직접 고치나 |
| --- | --- | --- |
| `tokens.json` | **유일한 원본** 토큰 (W3C DTCG 형식). 기본 값(`color.*`) → 의미 토큰(`semantic.*`) | ✅ 여기만 |
| `scripts/build_tokens.py` | `tokens.json` → `tokens.css` 변수 영역 + `.streamlit/config.toml` 생성 | — |
| `tokens.css` | CSS 변수(자동 생성 영역) + Streamlit 기본 덮어쓰기 + 범용 부품(`.ds-*`) | 변수 영역은 ❌ |
| `components.css` | 완결각 화면 부품(`.wg-*`: 배지, 서재 카드, 회차 행, 뷰어 첫머리…) | ✅ (의미 토큰만 사용) |
| `.streamlit/config.toml` | Streamlit 기본 테마 (자동 생성) | ❌ |
| `ds.py` | `ds.apply()`로 CSS 주입, `ds.chips()` 등 도우미 | ✅ |
| `ds_demo.py` | 견본 화면 — 토큰과 부품을 한 화면에서 확인 | ✅ |

## 토큰 바꾸는 법

```bash
# 1. tokens.json에서 값 수정 (예: color.brand.400)
# 2. 생성
python scripts/build_tokens.py
# 3. 견본 확인 (앱을 띄워 둔 상태라면 껐다 켜기)
streamlit run ds_demo.py
```

- **브랜드 교체**는 `color.brand.400/500/600` 3개만 바꾸면 버튼, 하단 바, 도착 배지, 칩에 모두 반영됩니다.
- 배지·회차 상태 색은 `semantic.status.*`에서 따로 조정합니다. 경고색(빨강)은 쓰지 않습니다(PRD 7장 1번).
- `components.css`에서는 `var(--의미 토큰)`만 씁니다. `--gray-*`, `--brand-*` 같은 기본 값을 직접 쓰지 마세요.
- `tests/test_tokens.py`가 생성 결과와 파일이 다르면 실패합니다(생성 스크립트를 안 돌린 경우).

## 요소별 크기 표 (화면 기준 — 바꿀 때는 이 표와 tokens.json을 같이 고친다)

| 요소 | 토큰 | 값 |
| --- | --- | --- |
| 화면 제목 (서재 이름, 시즌 제목, S6 제목) | `--fs-title-lg` | 24px (모바일 22px), Bold |
| 서재 카드 제목 | `--fs-title-sm` | 18px, Bold |
| 본문, 회차 행 제목, 하단 바 글자 | `--fs-body-lg` | 16px (하단 바 전 화면 16px 통일) |
| 서재 "지금까지 끝낸 회차 N개" | `--fs-meta-lg` | 15px |
| 버튼·칩·입력칸 이름표(Streamlit 기본 요소 포함), 메타(1/9화) | `--fs-body-md` | 14px (Streamlit 기본 12.25px를 덮어씀) |
| 캡션, 회차 번호(1화 · 약 30분) | `--fs-caption` | 14px (12 → 14, 10/29) |
| 배지 글자 (완결·도착·새 시즌·끝냄·선물) | `--fs-badge` | 12px (사용자 지정 유지) |
| 배지 | `--badge-height` · `--badge-padding-x` | 높이 24px, 좌우 10px ('완결'만 8px) |
| 하단 바 | `--cta-h` | 높이 56px |

## 피그마 연동

- 위치: 피그마 '비전보드' 파일 › '그림판' 페이지 › **'완결각 디자인 시스템' 섹션** (Starter 플랜이라 새 페이지 대신 섹션)
  - `WG Components`: 컴포넌트 11종 (Badge 6변형, Button 3변형, CTA Bar, Pill 2변형, Input, Library Card, Episode Row 3변형, Viewer Head, Summary Box, Prediction Card, Notice Box)
  - `WG Screens`: S1 입장 · S2 서재 · S2-b 시즌 홈 · S4 회차 · S5 완료 · S6 목표와 선물 (390×844, 컴포넌트 인스턴스로 조립)
- 변수 컬렉션: `완결각 Primitives`(gray·brand·focus) / `완결각 Semantic`(bg·text·line·action·status, Primitives 별칭) / `완결각 Size`(space·radius). 텍스트 스타일 `완결각/*`, 이펙트 `완결각/shadow-card`
- 이름 규칙: tokens.json 경로와 1:1 — `color.brand.400` ↔ `brand/400`, `semantic.status.arrived-bg` ↔ `status/arrived-bg`, `space.6` ↔ `space/6`
- 글꼴: 피그마에 Pretendard가 없어 **Noto Sans KR**(400 Regular / 600 Medium / 700 Bold)로 만들었다. Pretendard를 PC에 설치하면 텍스트 스타일 글꼴만 바꾸면 된다.

**피그마 → 코드 되돌리기**
1. 피그마에서 변수 값을 바꾼다 (예: `brand/400`). 모든 화면이 함께 바뀐다.
2. Claude에게 "피그마 토큰 반영해줘"라고 요청 → Claude가 변수 값을 `{이름: 값}` JSON으로 읽어
3. `python scripts/sync_figma_tokens.py 값.json --check`로 차이 확인 → 확인 후 `--check` 없이 실행하면 tokens.json 갱신 + `build_tokens.py` 자동 실행
- 컴포넌트 모양(간격, 라운드, 구성)을 바꿨다면 Claude가 피그마 디자인을 읽어 `components.css`에 반영한다.

## 주의

- `tokens.css` 주석에 꺾쇠(`<`, `>` 로 감싼 단어)를 쓰지 마세요. `st.html`이 태그로 해석해 스타일 전체가 빠집니다.
- 초기 값은 빠른 개발을 위해 millie.co.kr에서 추출한 것입니다. 밀리 고유 부품(표지 히어로, 유리 알약, 카테고리 배지, 하단 탭바)은 제거했습니다(PRD 7장 10번).
- Streamlit 1.66.1에서 확인했습니다.
