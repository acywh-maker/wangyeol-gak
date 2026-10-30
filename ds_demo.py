"""완결각 디자인 시스템 견본 — 토큰과 화면 부품을 한 화면에서 본다.

Run:  streamlit run ds_demo.py   (모바일 확인: 개발자 도구 기기 모드, 폭 600px 미만)
색은 모두 var(--토큰)으로 칠하므로 tokens.json을 고치고 scripts/build_tokens.py를 돌리면 그대로 반영된다.
"""
import streamlit as st

import ds

st.set_page_config(page_title="완결각 디자인 시스템", layout="centered")
ds.apply()
if (st.pills("테마", ["다크", "라이트"], default="다크", label_visibility="collapsed") or "다크") == "다크":
    st.html('<div class="wg-theme-dark"></div>')


def swatches(title: str, names: list[str]) -> None:
    cells = "".join(
        f'<div style="text-align:center;font-size:11px;color:var(--text-tertiary);width:72px">'
        f'<div style="height:48px;border-radius:var(--radius-sm);background:var(--{n});'
        f'border:1px solid var(--line-default);margin-bottom:4px"></div>{n}</div>'
        for n in names
    )
    st.html(f'<p class="wg-label" style="margin-top:16px">{title}</p>'
            f'<div style="display:flex;flex-wrap:wrap;gap:8px">{cells}</div>')


st.html('<div class="wg-title">완결각 디자인 시스템</div>'
        '<div class="wg-meta">tokens.json → scripts/build_tokens.py → tokens.css · components.css · config.toml</div>')

st.subheader("브랜드 · 의미 색")
swatches("brand (교체 예정)", ["brand-400", "brand-500", "brand-600"])
swatches("action", ["action-primary", "action-primary-press", "action-secondary", "action-highlight"])
swatches("bg · text", ["bg-default", "bg-surface", "bg-notice", "text-strong", "text-primary", "text-tertiary", "text-on-surface"])
swatches("status (배지·회차 상태)", ["status-arrived-bg", "status-waiting-bg", "status-done-bg",
                                    "status-gift-line", "status-read-fg", "status-current-bg"])

st.subheader("글자")
for name in ("display", "title-lg", "title-md", "title-sm", "body-lg", "body-md", "caption"):
    st.html(f'<div class="ds-{name}">{name} — 오늘 몫 끝!</div>')

st.subheader("배지")
st.html('<div style="display:flex;flex-wrap:wrap;gap:8px">'
        '<span class="wg-badge wg-badge--arrived">오늘의 화 도착</span>'
        '<span class="wg-badge wg-badge--waiting">14시간 30분 남음</span>'
        '<span class="wg-badge wg-badge--done">완결</span>'
        '<span class="wg-badge wg-badge--new">새 시즌</span>'
        '<span class="wg-badge wg-badge--done-ep">✓ 끝냄</span>'
        '<span class="wg-badge wg-badge--gift">◆ 중간 선물</span></div>')

st.subheader("서재 카드")
with st.container(key="wg-card-demo"):
    st.html('<div class="wg-card-title">퍼포먼스 마케팅은 Iteration할 수 있는 영역</div>'
            '<div class="wg-card-meta"><span class="wg-badge wg-badge--arrived">오늘의 화 도착</span><span>3/12화</span></div>')

st.subheader("시즌 홈 회차 행")
st.html('<div class="wg-ep wg-ep--done"><div class="wg-ep__no">1화 · 약 10분</div>'
        '<div class="wg-ep__title">1. 목표: 오늘 잘하고 있는지 판단할 기준</div>'
        '<div class="wg-ep__tags"><span class="wg-badge wg-badge--done-ep">✓ 끝냄</span></div></div>'
        '<div class="wg-ep wg-ep--current"><div class="wg-ep__no">2화 · 약 10분</div>'
        '<div class="wg-ep__title">2. 환경: 믿을 수 있는 숫자</div>'
        '<div class="wg-ep__tags"><span class="wg-badge wg-badge--waiting">내일 오전 6시 도착 · 14시간 30분 남음</span>'
        '<span class="wg-badge wg-badge--gift">◆ 중간 선물</span></div></div>'
        '<div class="wg-ep"><div class="wg-ep__no">3화 · 약 9분</div><div class="wg-ep__title">3. 실행: 리듬대로</div></div>')

st.subheader("뷰어 첫머리 · 1분 요약")
st.html('<div class="wg-viewer-head"><div class="wg-viewer-head__no">논리의 기초 · 2화</div>'
        '<div class="wg-viewer-head__title">논리적으로 삽시다 (2/4)</div>'
        '<div class="wg-viewer-head__min">약 30분</div></div>')
with st.container(key="wg-summary-demo"):
    st.html('<div class="wg-label">1분 요약</div>인지 다음은 비교·고려 단계. 고객이 망설이는 이유를 줄이는 게 핵심.')

st.subheader("버튼 · 선택지")
with st.container(key="wg-box-demo"):
    st.html('<div class="wg-label">다음 화에서 공개 · 예측해 보세요</div>'
            '<strong>할인 쿠폰 vs 무료 배송, 장바구니 이탈을 더 줄인 건?</strong>')
    with st.container(horizontal=True, key="ds-row-demo"):  # 같은 크기·같은 스타일 (PRD 7장 8번)
        st.button("할인 쿠폰", width="stretch")
        st.button("✓ 무료 배송", width="stretch")
st.pills("가용시간", ["5분", "10분", "20분", "30분", "60분"], default="30분", label_visibility="collapsed")
st.button("다 봤어요", type="primary", width="stretch")

st.subheader("안내 상자")
st.html('<div class="wg-notice"><div class="wg-notice__title">선물이 선택됐어요</div>'
        '<div>아메리카노 (예시) · 10화 완결 때 도착해요. 결제 기능은 아직 준비 중이에요.</div></div>')

with st.container(key="ds-cta"):
    st.button("이어보기 · 논리의 기초 2화", type="primary", width="stretch")
