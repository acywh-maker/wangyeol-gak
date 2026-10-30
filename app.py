"""완결각 — Streamlit 진입점.

흐름: S1 입장 → S2 서재 → (S6 목표·선물·가용시간) → S2-b 시즌 홈 → S4 회차 → S5 완료 → (S5-b/S5-c 선물)
카카오페이지 레퍼런스에서 가져온 것: 시즌 홈의 회차 목록, 하단 고정 '이어보기 · n화', 뷰어식 회차 첫머리.
"""
from datetime import timedelta
from html import escape

import streamlit as st

import ds
from wangyeol import auth, notion, rules, service, store, text
from wangyeol.render import md, render_segment, show

st.set_page_config(page_title="완결각", page_icon="📖", layout="centered")
ds.apply()

LOAD_ERROR = "노트를 불러오지 못했어요. 잠시 후 다시 시도해 주세요"
MINUTE_CHOICES = [5, 10, 20, 30, 60]
SAVE_HINT = "'이대로 약속하기'를 누르면 저장돼요"
GIFT_ITEMS = {  # FR-010: 일반 상품명 + (예시), 가격 없음
    "커피": ["아메리카노 (예시)", "카페라테 (예시)", "바닐라라테 (예시)", "콜드브루 (예시)"],
    "디저트": ["조각 케이크 (예시)", "마카롱 세트 (예시)", "쿠키 세트 (예시)", "크로플 (예시)"],
}

ss = st.session_state
ss.setdefault("screen", "library")
ss.setdefault("time_offset_h", 0)
DEV = bool(st.secrets.get("DEV_MODE")) and st.query_params.get("dev") == "1"
if not DEV:
    st.html('<style>header[data-testid="stHeader"] { display: none; }</style>')


def now():
    return rules.now_kst(timedelta(hours=ss.time_offset_h))


def go(screen: str, **kw) -> None:
    ss.screen = screen
    ss.update(kw)
    st.rerun()


def log(event: str, season_id: str = "", ep_index: int | None = None, meta: dict | None = None) -> None:
    store.log_event(now().isoformat(), ss.user["user_id"], event, season_id, ep_index, meta)


def load_error(e: Exception) -> None:
    st.error(LOAD_ERROR)
    if DEV:
        st.caption(f"개발용 상세: {e}")
    if st.button("다시 시도"):
        notion.clear_cache()
        st.rerun()


DEFAULT_THEME = "dark"  # FR-015: 다크가 기본


def theme() -> str:
    return (ss.get("user") or {}).get("theme") or DEFAULT_THEME


def theme_toggle() -> None:
    """라이트/다크 전환. 사용자별로 저장된다."""
    dark = theme() == "dark"
    if st.button("☀️ 라이트 모드" if dark else "🌙 다크 모드", type="tertiary", key="theme-toggle"):
        new = "light" if dark else "dark"
        store.set_theme(ss.user["user_id"], new)
        ss.user = {**ss.user, "theme": new}
        log("theme_change", meta={"theme": new})
        st.rerun()


def top_bar(back_label: str | None = None, back_screen: str | None = None) -> None:
    """화면 맨 위: 왼쪽 뒤로 가기, 오른쪽 테마 토글."""
    with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center", key="wg-topbar"):
        if back_label:
            if st.button(f"‹ {back_label}", type="tertiary", key=f"back-{back_screen}"):
                go(back_screen)
        else:
            st.html("<span></span>")
        theme_toggle()


def back(label: str, screen: str) -> None:
    if st.button(f"‹ {label}", type="tertiary", key=f"back-{screen}"):
        go(screen)


def badge(kind: str, label: str) -> str:
    return f'<span class="wg-badge wg-badge--{kind}">{escape(label)}</span>'


def state_for(season_id: str) -> service.SeasonState | None:
    row = next((r for r in notion.seasons_for(ss.user["nickname"]) if r["id"] == season_id), None)
    return service.load_state(ss.user["user_id"], row, now()) if row else None


def enter_season(state: service.SeasonState) -> None:
    """시즌 진입 판단: 처음이면 S6, 아니면 시즌 홈. (3일 이상 쉬었을 때 S3는 Day 3)"""
    if not state.started:
        log("gift_setup_view", state.row["id"])
        go("goal", season_id=state.row["id"], goal_edit=False)
    log("season_view", state.row["id"])
    go("home", season_id=state.row["id"])


def open_episode(state: service.SeasonState, index: int) -> None:
    go("episode", season_id=state.row["id"], ep_index=index)


# ---------- S1 입장 ----------

def entry() -> None:
    st.html('<div class="wg-hero"><div class="wg-hero__title">완결각</div>'
            '<div class="wg-hero__sub">쌓아 둔 노트를 웹소설처럼 하루 한 화씩</div></div>')
    # 폼: 입력값과 버튼이 한 번에 제출되도록 (모바일에서 마지막 입력이 누락되지 않게)
    with st.form("entry", border=False):
        with st.container(key="wg-fields"):
            nickname = st.text_input("닉네임 (2~12자)", max_chars=12)
            pin = st.text_input("PIN 4자리", type="password", max_chars=4)
        st.caption("처음이면 자동으로 가입돼요")
        with st.container(key="ds-cta"):
            submit = st.form_submit_button("시작하기", type="primary", width="stretch")
    if submit:
        err = auth.validate(nickname.strip(), pin)
        user = None
        if not err:
            user, err, is_new = auth.enter(nickname, pin, now().isoformat())
        if err:
            st.error(err)
            return
        ss.user = user
        ss.pending_cookie = auth.issue_token(user["user_id"])
        log("signup" if is_new else "login")
        go("library")


# ---------- S2 내 서재 ----------

def library() -> None:
    try:
        rows = notion.seasons_for(ss.user["nickname"])
        states = [service.load_state(ss.user["user_id"], r, now()) for r in rows]
    except notion.NotionError as e:
        load_error(e)
        return
    top_bar()
    st.html(f'<div class="wg-title">{escape(ss.user["nickname"])}님의 서재</div>'
            f'<div class="wg-stat">지금까지 끝낸 회차 {store.total_completed(ss.user["user_id"])}개</div>')
    if not states:
        st.info("아직 서재에 시즌이 없어요.")
    for s in states:
        kind, label = s.status
        progress = f"{len(s.done)}/{s.total}화" if s.started else f"{s.total}화"
        with st.container(key=f"wg-card-{s.row['id']}"):
            done_cls = " wg-card--done" if kind == "done" else ""
            st.html(f'<div class="wg-card-title{done_cls}">{escape(s.row["title"])}</div>'
                    f'<div class="wg-card-meta">{badge(kind, label)}<span>{progress}</span></div>')
            if st.button(s.row["title"], key=f"open-{s.row['id']}", width="stretch"):
                enter_season(s)

    if st.button("로그아웃", type="tertiary"):
        auth.logout(ss.user["user_id"])
        ss.clear()
        ss.pending_cookie = ""
        st.rerun()

    recent = service.most_recent(ss.user["user_id"], states)
    if recent and recent.next_ep:
        with st.container(key="ds-cta"):
            title = recent.row["title"] if len(recent.row["title"]) <= 14 else recent.row["title"][:13] + "…"
            if st.button(f"이어보기 · {title} {recent.current_ep}화", type="primary", width="stretch"):
                open_episode(recent, recent.current_ep)


# ---------- S2-b 시즌 홈 ----------

def home() -> None:
    try:
        s = state_for(ss.get("season_id", ""))
    except notion.NotionError as e:
        load_error(e)
        return
    if not s:
        go("library")
    top_bar("서재", "library")
    if ss.get("flash"):
        st.toast(ss.pop("flash"), icon="✉️")
    st.html(f'<div class="wg-title">{escape(s.row["title"])}</div>'
            f'<div class="wg-meta">하루 {s.minutes}분 · {len(s.done)}/{s.total}화</div>')
    if st.button("목표·선물 바꾸기 ›", type="tertiary", key="goal-edit"):
        go("goal", goal_edit=True)

    t = now()
    gifts = {p: ("완결 선물" if p == s.points[-1] else "중간 선물") for p in s.points}
    for ep in s.episodes:
        done = ep.index in s.done
        tags = []
        if done:
            tags.append(badge("done-ep", "✓ 끝냄"))
        elif ep.index == s.current_ep and not s.finished:
            if s.is_arrived(t):
                tags.append(badge("arrived", "오늘의 화 도착"))
            else:
                tags.append(badge("waiting", rules.arrival_text(t, s.arrival())))
        if ep.index in gifts:
            tags.append(badge("gift", f"🎁 {gifts[ep.index]}"))
        cls = "wg-ep wg-ep--done" if done else ("wg-ep wg-ep--current" if ep.index == s.current_ep else "wg-ep")
        with st.container(key=f"wg-row-{ep.index}"):
            st.html(f'<div class="{cls}"><div class="wg-ep__no">{ep.index}화 · 약 {ep.minutes}분</div>'
                    f'<div class="wg-ep__title">{escape(ep.title)}</div>'
                    f'<div class="wg-ep__tags">{"".join(tags)}</div></div>')
            if st.button(f"{ep.index}화 {ep.title}", key=f"ep-{ep.index}", width="stretch"):
                open_episode(s, ep.index)

    if not s.finished and s.next_ep:
        with st.container(key="ds-cta"):
            label = "첫 화 보기" if not s.done else f"이어보기 · {s.current_ep}화"
            if st.button(label, type="primary", width="stretch"):
                open_episode(s, s.current_ep)


# ---------- S6 목표와 선물 / S6-b 선물 고르기 ----------

def goal() -> None:
    try:
        s = state_for(ss.get("season_id", ""))
    except notion.NotionError as e:
        load_error(e)
        return
    if not s:
        go("library")
    uid, sid = ss.user["user_id"], s.row["id"]
    draft = ss.setdefault("goal_draft", {})
    if draft.get("season_id") != sid:
        saved = store.get_gifts(uid, sid)
        final = next((g for g in saved.values() if g["kind"] in ("gifticon", "letter_final")), None)
        draft.clear()
        draft.update(season_id=sid, minutes=s.minutes, final_kind=(final or {}).get("kind", ""),
                     gift_item=(final or {}).get("gift_item", ""),
                     letters={k: g["letter_text"] for k, g in saved.items() if g.get("letter_text")})

    if ss.get("goal_edit"):
        back("시즌 홈", "home")
    st.html(f'<div class="wg-title">목표를 정하고, 해낸 나에게 줄<br>선물도 준비해요{ds.icon("fantasybook", "wg-icon--deco")}</div>')

    st.html('<div class="wg-label">하루에 얼마나 볼까요?</div>')
    # v02: 직접 입력 없앰. 예전에 직접 입력한 값(예: 25분)이면 아무 칩도 선택되지 않은 채 그 값을 유지
    options = [f"{m}분" for m in MINUTE_CHOICES]
    current = f"{draft['minutes']}분" if draft["minutes"] in MINUTE_CHOICES else None
    pick = st.pills("하루 가용시간", options, default=current, label_visibility="collapsed", key="goal-minutes")
    if pick:
        draft["minutes"] = int(pick.removesuffix("분"))

    total, points = service.preview(s.season, draft["minutes"])
    # 하루 한 화라서 완결까지 걸리는 날 = 화 수
    st.html(f'<div class="wg-goal"><div class="wg-label">목표</div>'
            f'<div class="wg-goal__main">{escape(s.row["title"])}</div>'
            f'<div class="wg-meta">총 {total}화 · 하루 {draft["minutes"]}분 · {total}일 뒤 완결</div></div>')

    for p in points[:-1]:
        st.html(f'<div class="wg-label">중간 선물 · {p}화</div>')
        draft["letters"][p] = st.text_area(f"{p}화까지 온 나에게 편지 쓰기", value=draft["letters"].get(p, ""),
                                           max_chars=500, key=f"letter-{p}", label_visibility="collapsed",
                                           placeholder=f"{p}화까지 온 나에게 편지 쓰기…")
        st.caption(SAVE_HINT)

    last = points[-1]
    st.html('<div class="wg-label">완결하는 날 받을 선물</div>')
    # 아이콘은 components.css에서 버튼 key로 붙인다. 고른 쪽은 메인색(primary)
    with st.container(horizontal=True, key="ds-row-final"):
        for kind, label in (("letter_final", "나에게 편지 쓰기"), ("gifticon", "기프티콘 고르기")):
            picked = "primary" if draft["final_kind"] == kind else "secondary"
            if st.button(label, key=f"final-{kind}", type=picked, width="stretch"):
                draft["final_kind"] = kind
                if kind == "gifticon":
                    go("gift")
                st.rerun()
    if draft["final_kind"] == "gifticon" and draft["gift_item"]:
        st.caption(f"고른 선물: {draft['gift_item']} · 결제 기능은 아직 준비 중이에요")
    if draft["final_kind"]:  # 편지만 보내기 / 기프티콘에 편지 동봉(선택)
        with_gift = draft["final_kind"] == "gifticon"
        if with_gift:
            st.html('<div class="wg-label">편지도 함께 쓰기 (선택)</div>')
        draft["letters"][last] = st.text_area("완결한 나에게 편지 쓰기", value=draft["letters"].get(last, ""),
                                              max_chars=500, key=f"letter-{last}", label_visibility="collapsed",
                                              placeholder="완결한 나에게 편지 쓰기…")
        st.caption(SAVE_HINT)

    # 처음: 저장 없이 시작(10분) / 수정 중: 바꾸지 않고 시즌 홈으로
    if st.button("다음에 정할게요", type="tertiary", key="later"):
        if not ss.get("goal_edit"):
            service.start_or_update(uid, s, service.DEFAULT_MINUTES, now())
            log("gift_skip", sid)
        ss.pop("goal_draft", None)
        go("home")

    with st.container(key="ds-cta"):
        if st.button("이대로 약속하기", type="primary", width="stretch", key="promise"):
            service.start_or_update(uid, s, draft["minutes"], now())
            ts = now().isoformat()
            for p in points[:-1]:
                if draft["letters"].get(p, "").strip():
                    store.save_gift(uid, sid, p, "letter", letter_text=draft["letters"][p].strip(), now=ts)
            final_letter = draft["letters"].get(last, "").strip()
            if draft["final_kind"] == "letter_final":
                store.save_gift(uid, sid, last, "letter_final", letter_text=final_letter, now=ts)
            elif draft["final_kind"] == "gifticon":
                store.save_gift(uid, sid, last, "gifticon", letter_text=final_letter, gift_item=draft["gift_item"], now=ts)
            log("gift_set", sid, meta={"minutes": draft["minutes"], "final": draft["final_kind"]})
            wrote = any(draft["letters"].get(p, "").strip() for p in points[:-1]) or (draft["final_kind"] and final_letter)
            ss.pop("goal_draft", None)
            go("home", flash="편지를 저장했어요" if wrote else "")


def gift() -> None:
    draft = ss.get("goal_draft") or {}
    back("목표와 선물", "goal")
    st.html('<div class="wg-title">완결 선물 고르기</div>')
    tab = st.pills("종류", list(GIFT_ITEMS), default="커피", label_visibility="collapsed", key="gift-tab") or "커피"
    items = GIFT_ITEMS[tab]
    for row in (items[:2], items[2:]):
        with st.container(horizontal=True, key=f"ds-row-gift-{row[0]}"):
            for item in row:
                picked = draft.get("gift_item") == item  # 고른 상품: 이미지 테두리 + 버튼 메인색
                with st.container(key=f"wg-gift-{item}"):
                    st.html(f'<div class="wg-gift__img{" wg-gift__img--picked" if picked else ""}"></div>')
                    if st.button(item, key=f"pick-{item}", type="primary" if picked else "secondary", width="stretch"):
                        draft["gift_item"] = item
                        log("gift_select", draft.get("season_id", ""), meta={"item": item})
                        ss.gift_picked = item
                        st.rerun()
    if ss.get("gift_picked"):
        total, points = service.preview(state_for(draft["season_id"]).season, draft.get("minutes", service.DEFAULT_MINUTES))
        st.html(f'<div class="wg-notice"><div class="wg-notice__title">선물이 선택됐어요</div>'
                f'<div>{escape(ss.gift_picked)} · {points[-1]}화 완결 때 도착해요. '
                f'결제 기능은 아직 준비 중이에요. 관심 가져 주셔서 고마워요!</div></div>')
        with st.container(key="ds-cta"):  # 다른 화면처럼 하단 바
            if st.button("확인", type="primary", width="stretch"):
                ss.pop("gift_picked")
                go("goal")


# ---------- S4 회차 ----------

def episode() -> None:
    try:
        s = state_for(ss.get("season_id", ""))
    except notion.NotionError as e:
        load_error(e)
        return
    if not s or not s.episodes:
        go("library")
    uid, sid = ss.user["user_id"], s.row["id"]
    idx = max(1, min(ss.get("ep_index", 1), s.total))  # 회차가 줄면 마지막 회차로 보정 (13장)
    ep = s.episodes[idx - 1]
    units = s.season.units

    opened = ss.setdefault("opened", set())
    if (sid, idx) not in opened:
        opened.add((sid, idx))
        log("ep_open", sid, idx, {"est_min": ep.minutes})
        if idx > s.current_ep or (idx == s.current_ep and not s.is_arrived(now())):
            log("early_open", sid, idx)

    top_bar("시즌 홈", "home")

    # 1. 뷰어식 첫머리
    # v02: 위 = 회차·분량, 아래 = 시즌 제목 (사용자 지정)
    st.html(f'<div class="wg-viewer-head"><div class="wg-viewer-head__no">{idx}화 · 약 {ep.minutes}분</div>'
            f'<div class="wg-viewer-head__title">{escape(ep.title)}</div>'
            f'<div class="wg-viewer-head__min">{escape(s.row["title"])}</div></div>')

    # 2. 지난 화 예측 결과
    if idx > 1:
        prev = s.episodes[idx - 2].prediction
        saved = store.get_prediction(uid, sid, idx - 1)
        if prev and saved:
            picked = prev.choices[saved["choice"]]
            result = f"{text.eul(picked)} 골랐어요 → "
            result += "정답이에요!" if saved["choice"] == prev.answer_index else f"정답은 {text.ieosseoyo(prev.answer)}"
            with st.container(key=f"wg-box-result-{idx}"):
                st.html('<div class="wg-label">지난 화 예측 결과</div>')
                show(md([{"plain_text": result}]))
        # 3. 지난 화 내 한 줄 보기
        prev_line = store.get_line(uid, sid, idx - 1)
        if prev_line:
            with st.expander("지난 화 내 한 줄 보기"):
                st.write(prev_line)

    # 4. 1분 요약
    if ep.summary_unit is not None:
        with st.container(key=f"wg-summary-{idx}"):
            st.html('<div class="wg-label">1분 요약</div>')
            show(md(units[ep.summary_unit].blocks[0]["callout"]["rich_text"]))

    # 5. 본문
    for seg in ep.segments:
        if seg.unit != ep.summary_unit:
            render_segment(units, seg)

    # 6. 예측 선택 (마지막 화는 planner가 이미 숨김)
    if ep.prediction:
        pred = ep.prediction
        saved = store.get_prediction(uid, sid, idx)
        with st.container(key=f"wg-box-pred-{idx}"):
            st.html('<div class="wg-label">다음 화에서 공개 · 예측해 보세요</div>')
            show(f"<strong>{md([{'plain_text': pred.question}])}</strong>")
            with st.container(horizontal=True, key=f"ds-row-pred-{idx}"):  # 같은 크기·같은 스타일, 한 줄
                for i, choice in enumerate(pred.choices):
                    mark = "✓ " if saved and saved["choice"] == i else ""
                    if st.button(mark + choice, key=f"pred-{idx}-{i}", width="stretch"):
                        correct = i == pred.answer_index
                        store.save_prediction(uid, sid, idx, i, correct, now().isoformat())
                        log("prediction_submit", sid, idx, {"choice": choice, "is_correct": correct})
                        st.rerun()

    # 7. 오늘의 한 줄 (입력을 마치면 저장)
    def save_line():
        value = ss[f"line-{sid}-{idx}"].strip()
        store.save_line(uid, sid, idx, value, now().isoformat())
        if value:
            log("line_submit", sid, idx)

    st.text_area("오늘의 한 줄 (선택)", value=store.get_line(uid, sid, idx), max_chars=200,
                 key=f"line-{sid}-{idx}", height=80, on_change=save_line)

    # 8. 다 봤어요 — 본문 맨 아래에만 (하단 고정 바 사용 안 함)
    if st.button("다 봤어요", type="primary", width="stretch", key="done"):
        service.complete(uid, s, ep, now())
        ss.balloons_shown = False
        go("done", done_index=idx)

    # 9. 원문 링크
    first_blocks = units[ep.segments[0].unit].blocks
    with st.container(key="wg-source"):  # 본문(19)보다 작게, 키우기 전 크기 16
        st.markdown(f"[노션에서 원문 보기 ↗]({s.season.block_url(first_blocks[0]['id'] if first_blocks else None)})")

    if DEV:
        with st.sidebar:
            pick = st.selectbox("회차 이동", range(1, s.total + 1), index=idx - 1)
            if pick != idx:
                go("episode", ep_index=pick)


# ---------- S5 완료 / S5-b·S5-c 선물 도착 ----------

def done() -> None:
    s = state_for(ss.get("season_id", ""))
    if not s:
        go("library")
    idx = ss.get("done_index", 1)
    if not ss.get("balloons_shown"):
        st.balloons()
        ss.balloons_shown = True
    last = idx >= s.total  # 마지막 화: 같은 S5를 완결용 문구로 (v02 B안, S7 대신)
    st.html(f'<div class="wg-done"><div class="wg-done__title">{"시즌 완결!" if last else "오늘의 에피소드를 다 봤어요!"}</div>'
            f'<div class="wg-meta">지금까지 {store.total_completed(ss.user["user_id"])}화 끝냈어요</div></div>')

    def steps(label: str, filled: int, cells: int) -> None:  # 한 화에 한 칸: [■■■□□□□□]
        row = "".join(f'<span class="wg-steps__cell{" is-done" if i < filled else ""}"></span>' for i in range(cells))
        st.html(f'<div class="wg-label">{label}</div><div class="wg-steps">{row}</div>')

    nxt = rules.next_gift(s.points, idx)
    if last:
        steps(f"{s.total}화를 모두 봤어요", s.total, s.total)
    elif nxt:
        point, left, kind = nxt
        steps(f"{left}화만 더 보면 {'중간' if kind == 'mid' else '완결'} 선물이에요", idx, point)

    gift = store.get_gifts(ss.user["user_id"], s.row["id"]).get(idx) if idx in s.points else None
    if gift:
        if st.button("선물 확인하기", type="primary", width="stretch", key="gift-open"):
            go("gift_arrived")
        return

    if idx < s.total:
        arr = s.arrival()
        text = rules.arrival_sentence(now(), arr, idx + 1) if arr else f"{idx + 1}화를 지금 볼 수 있어요"
        st.html(f'<div class="wg-box-plain"><div class="wg-label">다음 화</div><div>{text}</div></div>')
    with st.container(horizontal=True, key="ds-row-done"):
        if st.button("서재로", width="stretch"):
            go("library")
        if idx < s.total and st.button("미리 열기", width="stretch"):
            open_episode(s, idx + 1)


def gift_arrived() -> None:
    s = state_for(ss.get("season_id", ""))
    idx = ss.get("done_index", 1)
    uid, sid = ss.user["user_id"], s.row["id"]
    g = store.get_gifts(uid, sid).get(idx)
    nick = escape(ss.user["nickname"])
    if store.mark_gift_delivered(uid, sid, idx, now().isoformat()):
        log("gift_delivered", sid, idx, {"kind": g["kind"]})
    written = rules.parse_ts(g.get("created_at"))
    letter = (f'<div class="wg-letter"><div class="wg-label">{written.month}월 {written.day}일의 내가 쓴 편지</div>'
              f'<div>{escape(g.get("letter_text", "")).replace(chr(10), "<br>")}</div></div>') if written and g.get("letter_text") else ""
    if g["kind"] == "letter":
        st.html(f'<div class="wg-label">중간 선물 · {idx}화</div>'
                f'<div class="wg-title">나와의 약속을 지켜낸 {nick}님 선물이 도착했어요</div>{letter}')
    else:
        box = (f'<div class="wg-gift-box"><div class="wg-gift__img"></div><div>{escape(g.get("gift_item", ""))}</div>'
               f'<div class="wg-stamp">선물 도착</div></div>') if g["kind"] == "gifticon" else ""
        body = box + letter  # 기프티콘에 편지를 동봉했으면 둘 다
        st.html(f'<div class="wg-title">스스로 정한 목표를 끝까지 지킨 {nick}님.<br>정말 대단해요, 약속한 선물이에요.<br>축하드려요!</div>{body}')
    if st.button("서재로", type="primary", width="stretch", key="to-library"):  # S7 완결 리포트는 Day 3
        go("library")


# ---------- 개발용 ----------

def dev_sidebar() -> None:
    if not DEV:
        return
    with st.sidebar:
        st.caption("개발용 (?dev=1)")
        ss.time_offset_h = st.number_input("시간 이동(시간)", min_value=0, max_value=24 * 14, step=6,
                                           value=ss.time_offset_h)
        st.caption(f"지금(가상): {now():%m/%d %H:%M}")


# ---------- 라우팅 ----------

if "user" not in ss:
    cookie_user = auth.user_from_cookie()
    if cookie_user:
        ss.user = cookie_user
        log("login", meta={"via": "cookie"})
if "pending_cookie" in ss:
    auth.write_cookie(ss.pop("pending_cookie") or None)

if theme() == "dark":
    st.html('<div class="wg-theme-dark"></div>')
dev_sidebar()
if "user" not in ss:
    entry()
else:
    {"library": library, "home": home, "goal": goal, "gift": gift, "episode": episode,
     "done": done, "gift_arrived": gift_arrived}.get(ss.screen, library)()
