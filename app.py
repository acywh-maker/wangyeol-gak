"""완결각 — Streamlit 진입점.

Day 1 범위: 노션 시즌 목록(S2) + 가용시간에 맞춘 자동 회차 분할 + 회차 화면(S4).
입장(S1)·저장·S6(가용시간 고르기)은 Day 2에 붙인다. 그 전까지는 secrets의 DEV_NICKNAME으로 서재를 열고,
가용시간은 개발용 사이드바에서 고른다.
"""
from html import escape

import streamlit as st

import ds
from wangyeol import notion, planner, text
from wangyeol.render import APP_CSS, md, render_segment, show

st.set_page_config(page_title="완결각", page_icon="📖", layout="centered")
ds.apply()
st.html(APP_CSS)

LOAD_ERROR = "노트를 불러오지 못했어요. 잠시 후 다시 시도해 주세요"
DEFAULT_MINUTES = 10  # S6를 건너뛰었을 때 (기본값)
MINUTE_CHOICES = [5, 10, 20, 30, 55, 60]

ss = st.session_state
ss.setdefault("screen", "library")
ss.setdefault("nickname", st.secrets.get("DEV_NICKNAME", "돋이"))
ss.setdefault("minutes", DEFAULT_MINUTES)  # Day 2: 시즌별로 저장소에서
ss.setdefault("predictions", {})  # (season_id, ep) -> choice index (Day 2에 저장소로 이동)
DEV = bool(st.secrets.get("DEV_MODE"))


def go(screen: str, **kw) -> None:
    ss.screen = screen
    ss.update(kw)
    st.rerun()


def load_error(e: Exception) -> None:
    st.error(LOAD_ERROR)
    if DEV:
        st.caption(f"개발용 상세: {e}")
    if st.button("다시 시도"):
        notion.clear_cache()
        st.rerun()


def find_row(season_id: str) -> dict | None:
    return next((r for r in notion.seasons_for(ss.nickname) if r["id"] == season_id), None)


def dev_sidebar() -> None:
    if not DEV:
        return
    with st.sidebar:
        st.caption("개발용 · S6 전까지 임시")
        pick = st.selectbox("하루 가용시간(분)", MINUTE_CHOICES, index=MINUTE_CHOICES.index(ss.minutes))
        if pick != ss.minutes:
            ss.minutes = pick
            ss.ep_index = 1
            st.rerun()


# ---------- S2 내 서재 ----------

def library() -> None:
    st.html(f'<div class="wg-title">{escape(ss.nickname)}님의 서재</div>')
    try:
        rows = notion.seasons_for(ss.nickname)
    except notion.NotionError as e:
        load_error(e)
        return
    if not rows:
        st.info("아직 서재에 시즌이 없어요.")
        return
    for row in rows:
        with st.container(key=f"wg-card-{row['id']}"):
            st.html(f'<div class="wg-card-title">{escape(row["title"])}</div>')
            try:
                season = notion.load_season(row)
                n = len(planner.plan(season, ss.minutes))
                st.html(f'<div class="wg-meta">약 {round(season.total_seconds / 60)}분 분량 · '
                        f'하루 {ss.minutes}분이면 {n}화</div>')
            except notion.NotionError:
                pass
            if st.button("열기", key=f"open-{row['id']}", width="stretch"):
                go("episode", season_id=row["id"], ep_index=1)


# ---------- S4 회차 ----------

def prediction_card(season_id: str, ep) -> None:
    pred = ep.prediction
    key = (season_id, ep.index)
    chosen = ss.predictions.get(key)
    with st.container(key=f"wg-box-pred-{ep.index}"):
        st.html('<div class="wg-label">다음 화에서 공개 · 예측해 보세요</div>')
        show(f"<strong>{md([{'plain_text': pred.question}])}</strong>")
        # 7장 8번: 두 선택지는 같은 크기·같은 스타일. ds-row: 모바일에서도 한 줄
        with st.container(horizontal=True, key=f"ds-row-pred-{ep.index}"):
            for i, choice in enumerate(pred.choices):
                label = f"✓ {choice}" if chosen == i else choice
                if st.button(label, key=f"pred-{season_id}-{ep.index}-{i}", width="stretch"):
                    ss.predictions[key] = i
                    st.rerun()


def previous_prediction(season_id: str, episodes: list, ep) -> None:
    prev_key = (season_id, ep.index - 1)
    if ep.index < 2 or prev_key not in ss.predictions:
        return
    prev = episodes[ep.index - 2].prediction
    if not prev:
        return
    picked = prev.choices[ss.predictions[prev_key]]
    result = f"{text.eul(picked)} 골랐어요 → "
    result += "정답이에요!" if ss.predictions[prev_key] == prev.answer_index else f"정답은 {text.ieosseoyo(prev.answer)}"
    with st.container(key=f"wg-box-result-{ep.index}"):
        st.html('<div class="wg-label">지난 화 예측 결과</div>')
        show(md([{"plain_text": result}]))


def episode() -> None:
    row = find_row(ss.get("season_id", ""))
    if not row:
        go("library")
    try:
        with st.spinner("노트를 불러오는 중…"):
            season = notion.load_season(row)
    except notion.NotionError as e:
        load_error(e)
        return

    episodes = planner.plan(season, ss.minutes)
    if not episodes:
        st.info("이 노트에는 아직 볼 내용이 없어요.")
        return
    n = len(episodes)
    ss.ep_index = max(1, min(ss.get("ep_index", 1), n))  # 회차가 줄면 마지막 회차로 보정 (13장)
    ep = episodes[ss.ep_index - 1]
    units = season.units

    if st.button("← 서재", type="tertiary"):
        go("library")

    # 1. 시즌명 · n화 · 약 n분, 회차 제목
    st.html(f'<div class="wg-meta">{escape(season.title)} · {ep.index}화 · 약 {ep.minutes}분</div>'
            f'<div class="wg-title">{escape(ep.title)}</div>')

    # 2. 지난 화 예측 결과 / 3. 지난 화 내 한 줄 보기 — Day 2 (저장소 연결 후)
    previous_prediction(season.id, episodes, ep)

    # 4. 1분 요약 (회차 안 첫 콜아웃)
    if ep.summary_unit is not None:
        with st.container(key=f"wg-summary-{ep.index}"):
            st.html('<div class="wg-label">1분 요약</div>')
            show(md(units[ep.summary_unit].blocks[0]["callout"]["rich_text"]))

    # 5. 본문
    for seg in ep.segments:
        if seg.unit != ep.summary_unit:
            render_segment(units, seg)

    # 6. 예측 선택 (마지막 화는 planner가 이미 숨김)
    if ep.prediction:
        prediction_card(season.id, ep)

    # 7. 오늘의 한 줄
    st.text_area("오늘의 한 줄 (선택)", max_chars=200, key=f"line-{season.id}-{ep.index}", height=80)

    # 8. 다 봤어요 — 본문 맨 아래에만 (하단 고정 바 사용 안 함)
    if st.button("다 봤어요", type="primary", width="stretch"):
        st.balloons()
        st.success("오늘 몫 끝!")  # Day 2: 완료 기록·누적 회차·S5로 교체

    # 9. 원문 링크 (회차 첫 블록으로)
    first_blocks = units[ep.segments[0].unit].blocks
    st.markdown(f"[노션에서 원문 보기 ↗]({season.block_url(first_blocks[0]['id'] if first_blocks else None)})")

    if DEV:
        with st.sidebar:
            pick = st.selectbox("회차 이동", range(1, n + 1), index=ep.index - 1,
                                format_func=lambda i: f"{i}화 · 약 {episodes[i - 1].minutes}분 · {episodes[i - 1].title[:20]}")
            if pick != ep.index:
                go("episode", ep_index=pick)


dev_sidebar()
{"library": library, "episode": episode}[ss.screen]()
