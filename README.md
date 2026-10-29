# Streamlit Design System

| 파일 | 역할 |
|---|---|
| `tokens.json` | 원본 토큰 (W3C DTCG 형식). 값마다 `$description`에 근거 표기 |
| `tokens.css` | CSS 변수 + Streamlit 위젯 덮어쓰기 + 컴포넌트 클래스(`.ds-*`) + 모바일(<600px) 규칙 |
| `.streamlit/config.toml` | Streamlit 기본 테마 (색, 폰트, 라운드) |
| `ds.py` | `ds.apply()`로 CSS 주입, `ds.chips()` 등 컴포넌트 함수 |
| `ds_demo.py` | 데모 (가이드 / 루틴 알림 / 상세 화면). `streamlit run ds_demo.py` |

## 사용법

```python
import streamlit as st
import ds

ds.apply()                                   # 페이지마다 맨 위에서 1번
ds.header("독서 루틴 알림 만들기", back="?")
ds.chips(["# 판타지", "+ 9개"])

with st.container(key="ds-cta"):             # 모바일에서 하단 고정 노란 CTA 바
    st.button("확인", type="primary", width="stretch")

with st.container(horizontal=True, key="ds-row-time"):   # 모바일에서도 한 줄 유지
    ...
```

- 프로젝트 루트에 `.streamlit/` 폴더째로 두어야 config.toml이 적용됩니다.
- Streamlit 1.66.1에서 확인했습니다. `st.container(horizontal=True)`, `width="stretch"`는 구버전에 없을 수 있습니다.
- `tokens.css` 주석에 꺾쇠(`<`, `>` 로 감싼 단어)를 쓰지 마세요. `st.html`이 태그로 해석해 스타일 전체가 빠집니다.
- 상태 색(에러/성공)은 레퍼런스에서 추출되지 않아 Streamlit 기본값을 씁니다.
