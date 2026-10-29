"""Demo: style guide + two mobile screens rebuilt with the design system.

Run:  streamlit run app.py
Mobile check: open DevTools > device toolbar (width < 600px).
"""
import streamlit as st

import ds

st.set_page_config(page_title="Design System", layout="centered")
ds.apply()

TABS = [
    ("guide",   "가이드", "&#9638;"),
    ("routine", "루틴",   "&#9719;"),
    ("detail",  "상세",   "&#9636;"),
]
tab = st.query_params.get("tab", "guide")


# --------------------------------------------------------------------------
def page_guide():
    st.title("Design System")
    st.caption("tokens.json · tokens.css · config.toml")

    t = ds.tokens()

    st.subheader("Color")
    for group in ("gray", "yellow", "category"):
        swatches = "".join(
            f'<div style="text-align:center;font-size:11px;color:var(--text-tertiary)">'
            f'<div style="width:56px;height:56px;border-radius:var(--radius-sm);background:{v["$value"]};'
            f'border:1px solid var(--line-default)"></div>{k}<br>{v["$value"]}</div>'
            for k, v in t["color"][group].items()
        )
        st.html(f'<p class="ds-caption" style="margin:8px 0 4px">{group}</p>'
                f'<div style="display:flex;flex-wrap:wrap;gap:8px">{swatches}</div>')

    st.subheader("Typography")
    for name in ("display", "title-lg", "title-md", "title-sm", "body-lg", "body-md", "caption"):
        st.html(f'<div class="ds-{name}">{name} — 오늘도 한 페이지 더</div>')
    ds.overline("Original")

    st.subheader("Radius · Shadow")
    boxes = "".join(
        f'<div style="text-align:center;font-size:11px;color:var(--text-tertiary)">'
        f'<div style="width:72px;height:72px;background:var(--bg-default);border-radius:var(--radius-{r});'
        f'box-shadow:var(--shadow-md);margin-bottom:6px"></div>{r}</div>'
        for r in ("xs", "sm", "md", "lg", "xl", "2xl", "pill")
    )
    st.html(f'<div style="display:flex;flex-wrap:wrap;gap:16px;padding:8px">{boxes}</div>')

    st.subheader("Components")
    ds.chips(["# 판타지", "# 성장물", "# 힐링", "+ 9개"])
    st.html('<div style="display:flex;gap:12px;margin-top:12px">'
            + ds.badge("웹소설", "&#9636;")
            + ds.badge("오디오", "&#9835;", "audio")
            + ds.badge("챗북", "&#9993;", "chat") + "</div>")
    ds.meta(4.8, ["연재", "판타지", "2026.10.28"])
    c1, c2 = st.columns(2)
    c1.button("Primary", type="primary", width="stretch")
    c2.button("Secondary", width="stretch")
    st.checkbox("체크박스")
    st.text_input("입력", placeholder="검색어를 입력하세요")


# --------------------------------------------------------------------------
def page_routine():
    ds.header("독서 루틴 알림 만들기", back="?tab=guide")
    st.write("")
    # horizontal container keeps the 3 pickers in one row on mobile (st.columns would stack)
    with st.container(horizontal=True, key="ds-row-time"):
        st.selectbox("오전/오후", ["오전", "오후"], label_visibility="collapsed")
        st.selectbox("시", [f"{h:02d}" for h in range(1, 13)], index=7, label_visibility="collapsed")
        st.selectbox("분", [f"{m:02d}" for m in range(0, 60, 10)], label_visibility="collapsed")
    st.checkbox("**야간 수신 동의** 21시-08시 사이에도 알림을 받을래요")
    ds.notice(
        "독서 루틴 만들기",
        "출퇴근길 40분, 잠들기 전 20분처럼 조금 더 쉽게 독서할 수 있도록.\n"
        "원하는 시간에 알림을 받아 독서 루틴을 만들어보세요.",
        icon="&#9719;",
    )
    st.write("")
    ds.bullets([
        "수신 동의는 관리 > 알림 설정에서 확인할 수 있습니다.",
        "알림은 설정한 요일, 시간에 맞춰 앱 푸시로 보내 드립니다.",
        "21시~08시로 설정한 경우, 야간 수신 동의를 꼭 체크해주세요.",
    ])
    with st.container(key="ds-cta"):
        st.button("확인", type="primary", width="stretch")


# --------------------------------------------------------------------------
def page_detail():
    ds.detail_hero(
        cover_html=ds.cover(alt="SAMPLE", width=200),
        pill_html=ds.glass_pill("이 책이 담긴 서재", "1.1만+"),
        badge_html=ds.badge("웹소설", "&#9636;"),
    )
    st.html(
        '<div class="ds-sheet" style="margin-top:-28px;position:relative">'
        '<div class="ds-overline" style="margin-bottom:8px">Original</div>'
        '<div class="ds-title-md" style="margin-bottom:8px">[독점] 샘플 작품 제목</div>'
        '<div class="ds-body-lg" style="font-weight:700;color:var(--text-secondary);margin-bottom:20px">작가명 &#8250;</div>'
        '</div>'
    )
    ds.meta(5.0, ["연재", "로맨스", "2026.10.28"])
    st.write("")
    ds.chips(["# 직진남", "# 가상시대물", "# 다정녀", "+ 9개"])


# --------------------------------------------------------------------------
{"guide": page_guide, "routine": page_routine, "detail": page_detail}.get(tab, page_guide)()
ds.tabbar(TABS, active=tab)
