"""완결각 — Flask 웹앱 (Vercel 배포용).

흐름: S1 입장 → S2 서재 → (S6 목표·선물·가용시간 → S6-b) → S2-b 시즌 홈 → S4 회차 → S5 완료 → (S5-b/S5-c 선물)
로컬 실행:  python app.py   (http://localhost:8510)
"""
from __future__ import annotations

import csv
import hmac
import io
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from functools import wraps

from flask import Flask, abort, g, jsonify, redirect, render_template, request, session, url_for
from markupsafe import Markup

from wangyeol import auth, config, notion, rules, service, store, text
from wangyeol.render import rich, segment_html

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = config.get("SECRET_KEY") or "dev-only-secret"
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=not config.dev_mode())

COOKIE = auth.COOKIE
DEFAULT_THEME = "dark"  # FR-015
MINUTE_CHOICES = [5, 10, 20, 30, 60]
GIFT_ITEMS = {  # FR-010: 일반 상품명 + (예시), 가격 없음
    "커피": ["아메리카노 (예시)", "카페라테 (예시)", "바닐라라테 (예시)", "콜드브루 (예시)"],
    "디저트": ["조각 케이크 (예시)", "마카롱 세트 (예시)", "쿠키 세트 (예시)", "크로플 (예시)"],
}
STATUS_ORDER = {"arrived": 0, "waiting": 1, "new": 2, "done": 3}  # 서재: 오늘 볼 시즌이 맨 위 (1순위)


# ---------- 공통 ----------

@app.before_request
def load_user():
    store.reset_cache()
    g.user = auth.user_from_token(request.cookies.get(COOKIE))


@app.context_processor
def inject():
    theme = (g.get("user") or {}).get("theme") or DEFAULT_THEME
    return {"theme": theme, "user": g.get("user"), "dev": config.dev_mode(), "now": now()}


def now():
    offset = session.get("time_offset_h", 0) if config.dev_mode() else 0
    return rules.now_kst(timedelta(hours=offset))


def log(event: str, season_id: str = "", ep_index: int | None = None, meta: dict | None = None) -> None:
    if g.get("user"):
        store.log_event(now().isoformat(), g.user["user_id"], event, season_id, ep_index, meta)


def login_required(view):
    @wraps(view)
    def wrapper(*a, **kw):
        if not g.user:
            return redirect(url_for("enter"))
        return view(*a, **kw)
    return wrapper


def safe_next(default: str = "/") -> str:
    nxt = request.form.get("next") or request.args.get("next") or default
    return nxt if nxt.startswith("/") and not nxt.startswith("//") else default


def rows_for_user() -> list[dict]:
    return notion.seasons_for(g.user["nickname"])


def state_for(season_id: str) -> service.SeasonState:
    row = next((r for r in rows_for_user() if r["id"] == season_id), None)
    if not row:
        abort(404)
    return service.load_state(g.user["user_id"], row, now())


def episode_or_404(s: service.SeasonState, n: int):
    if not s.episodes:
        abort(404)
    return s.episodes[max(1, min(n, s.total)) - 1]  # 회차가 줄면 마지막 회차로 보정 (13장)


@app.errorhandler(notion.NotionError)
def notion_failed(e):
    return render_template("error.html", detail=str(e) if config.dev_mode() else ""), 503


@app.template_filter("eul")
def eul_filter(word):
    return text.eul(word)


# ---------- S1 입장 ----------

@app.route("/enter", methods=["GET", "POST"])
def enter():
    error, nickname = None, ""
    if request.method == "POST":
        nickname, pin = request.form.get("nickname", "").strip(), request.form.get("pin", "")
        error = auth.validate(nickname, pin)
        if not error:
            user, error, is_new = auth.enter(nickname, pin, now().isoformat())
            if user:
                g.user = user
                log("signup" if is_new else "login")
                resp = redirect(url_for("library"))
                resp.set_cookie(COOKIE, auth.issue_token(user["user_id"]), max_age=auth.COOKIE_DAYS * 86400,
                                httponly=True, samesite="Lax", secure=not config.dev_mode())
                return resp
    return render_template("entry.html", error=error, nickname=nickname)


@app.post("/logout")
@login_required
def logout():
    auth.logout(g.user["user_id"])
    resp = redirect(url_for("enter"))
    resp.delete_cookie(COOKIE)
    return resp


@app.post("/theme")
@login_required
def toggle_theme():
    new = "light" if (g.user.get("theme") or DEFAULT_THEME) == "dark" else "dark"
    store.set_theme(g.user["user_id"], new)
    log("theme_change", meta={"theme": new})
    return redirect(safe_next())


# ---------- S2 서재 ----------

@app.get("/")
@login_required
def library():
    rows = rows_for_user()
    uid, t = g.user["user_id"], now()  # 작업 스레드에서는 요청 정보(g, session)를 못 보므로 미리 꺼낸다
    store._load()  # 저장소도 요청 캐시에 미리 채워 둔다
    with ThreadPoolExecutor(max_workers=6) as pool:  # 시즌별 노션 읽기를 동시에
        states = list(pool.map(lambda r: service.load_state(uid, r, t), rows))
    states.sort(key=lambda s: STATUS_ORDER.get(s.status[0], 9))
    recent = service.most_recent(g.user["user_id"], states)
    return render_template("library.html", states=states, recent=recent,
                           total_done=store.total_completed(g.user["user_id"]))


# ---------- S2-b 시즌 홈 ----------

@app.get("/s/<sid>")
@login_required
def season_home(sid):
    s = state_for(sid)
    if not s.started:  # 처음이면 목표·선물부터 (S6)
        log("gift_setup_view", sid)
        return redirect(url_for("goal", sid=sid))
    log("season_view", sid)
    t = now()
    gifts = {p: ("완결 선물" if p == s.points[-1] else "중간 선물") for p in s.points}
    nxt = rules.next_gift(s.points, max(s.done, default=0))
    return render_template("home.html", s=s, gifts=gifts, next_gift=nxt, arrived=s.is_arrived(t),
                           arrival_text=rules.arrival_text(t, s.arrival()) if s.arrival() else "")


# ---------- S6 목표와 선물 / S6-b 선물 고르기 ----------

@app.get("/s/<sid>/goal")
@login_required
def goal(sid):
    s = state_for(sid)
    saved = store.get_gifts(g.user["user_id"], sid)
    final = next((x for x in saved.values() if x["kind"] in ("gifticon", "letter_final")), None)
    previews = {m: service.preview(s.season, m) for m in MINUTE_CHOICES}
    if s.minutes not in previews:
        previews[s.minutes] = service.preview(s.season, s.minutes)
    letters = {k: x["letter_text"] for k, x in saved.items() if x["kind"] in ("letter", "letter_final")}
    return render_template("goal.html", s=s, choices=MINUTE_CHOICES, minutes=s.minutes,
                           previews={m: {"total": t, "points": p} for m, (t, p) in previews.items()},
                           letters=letters, final_kind=(final or {}).get("kind", ""),
                           gift_item=(final or {}).get("gift_item", ""), editing=s.started)


@app.get("/s/<sid>/preview")
@login_required
def preview(sid):
    minutes = max(5, min(180, request.args.get("minutes", type=int) or service.DEFAULT_MINUTES))
    total, points = service.preview(state_for(sid).season, minutes)
    return jsonify(total=total, points=points)


@app.post("/s/<sid>/goal")
@login_required
def save_goal(sid):
    s = state_for(sid)
    uid, ts = g.user["user_id"], now().isoformat()
    if request.form.get("action") == "skip":  # "다음에 정할게요"
        if not s.started:
            service.start_or_update(uid, s, service.DEFAULT_MINUTES, now())
            log("gift_skip", sid)
        return redirect(url_for("season_home", sid=sid))
    minutes = max(5, min(180, request.form.get("minutes", type=int) or service.DEFAULT_MINUTES))
    service.start_or_update(uid, s, minutes, now())
    _, points = service.preview(s.season, minutes)
    for p in points[:-1]:
        letter = request.form.get(f"letter_{p}", "").strip()[:500]
        if letter:
            store.save_gift(uid, sid, p, "letter", letter_text=letter, now=ts)
    final_kind = request.form.get("final_kind", "")
    if final_kind == "letter_final":
        store.save_gift(uid, sid, points[-1], "letter_final",
                        letter_text=request.form.get("letter_final", "").strip()[:500], now=ts)
    log("gift_set", sid, meta={"minutes": minutes, "final": final_kind})
    if final_kind == "gifticon":
        return redirect(url_for("gift", sid=sid))
    return redirect(url_for("season_home", sid=sid))


@app.route("/s/<sid>/gift", methods=["GET", "POST"])
@login_required
def gift(sid):
    s = state_for(sid)
    tab = request.args.get("tab", "커피")
    tab = tab if tab in GIFT_ITEMS else "커피"
    picked = None
    if request.method == "POST":
        item = request.form.get("item", "")
        if item in sum(GIFT_ITEMS.values(), []):
            store.save_gift(g.user["user_id"], sid, s.points[-1], "gifticon", gift_item=item, now=now().isoformat())
            log("gift_select", sid, meta={"item": item})
            picked = item
    return render_template("gift.html", s=s, tabs=list(GIFT_ITEMS), tab=tab, items=GIFT_ITEMS[tab], picked=picked)


# ---------- S4 회차 ----------

@app.get("/s/<sid>/ep/<int:n>")
@login_required
def episode(sid, n):
    s = state_for(sid)
    ep = episode_or_404(s, n)
    uid, units = g.user["user_id"], s.season.units
    opened = set(session.get("opened", []))
    key = f"{sid}:{ep.index}"
    if key not in opened:  # 이벤트는 세션당 한 번
        log("ep_open", sid, ep.index, {"est_min": ep.minutes})
        if ep.index > s.current_ep or (ep.index == s.current_ep and not s.is_arrived(now())):
            log("early_open", sid, ep.index)
        session["opened"] = list(opened | {key})[-200:]

    prev_result, prev_line = None, ""
    if ep.index > 1:
        prev = s.episodes[ep.index - 2].prediction
        saved = store.get_prediction(uid, sid, ep.index - 1)
        if prev and saved and saved.get("choice") is not None:
            picked = prev.choices[saved["choice"]]
            prev_result = (f"{text.eul(picked)} 골랐어요 → "
                           + ("정답이에요!" if saved["choice"] == prev.answer_index else f"정답은 {text.ieosseoyo(prev.answer)}"))
        prev_line = store.get_line(uid, sid, ep.index - 1)

    summary = rich(units[ep.summary_unit].blocks[0]["callout"]["rich_text"]) if ep.summary_unit is not None else ""
    body = "".join(segment_html(units, seg) for seg in ep.segments if seg.unit != ep.summary_unit)
    saved_pred = store.get_prediction(uid, sid, ep.index) if ep.prediction else None
    first_blocks = units[ep.segments[0].unit].blocks
    return render_template("episode.html", s=s, ep=ep, prev_result=prev_result, prev_line=prev_line,
                           summary=Markup(summary), body=Markup(body),
                           chosen=(saved_pred or {}).get("choice"), line=store.get_line(uid, sid, ep.index),
                           notion_url=s.season.block_url(first_blocks[0]["id"] if first_blocks else None))


@app.post("/s/<sid>/ep/<int:n>/predict")
@login_required
def predict(sid, n):
    s = state_for(sid)
    ep = episode_or_404(s, n)
    choice = request.form.get("choice", type=int)
    if ep.prediction and choice in (0, 1):
        correct = choice == ep.prediction.answer_index
        store.save_prediction(g.user["user_id"], sid, ep.index, choice, correct, now().isoformat())
        log("prediction_submit", sid, ep.index, {"choice": ep.prediction.choices[choice], "is_correct": correct})
    if request.headers.get("X-Requested-With") == "fetch":
        return ("", 204)
    return redirect(url_for("episode", sid=sid, n=ep.index) + "#pred")


def _save_line(sid: str, index: int) -> None:
    if "line" not in request.form:
        return
    value = request.form.get("line", "").strip()[:200]
    if value != store.get_line(g.user["user_id"], sid, index):
        store.save_line(g.user["user_id"], sid, index, value, now().isoformat())
        if value:
            log("line_submit", sid, index)


@app.post("/s/<sid>/ep/<int:n>/line")
@login_required
def save_line(sid, n):
    _save_line(sid, episode_or_404(state_for(sid), n).index)
    if request.headers.get("X-Requested-With") == "fetch":
        return ("", 204)
    return redirect(url_for("episode", sid=sid, n=n))


@app.post("/s/<sid>/ep/<int:n>/done")
@login_required
def complete(sid, n):
    s = state_for(sid)
    ep = episode_or_404(s, n)
    _save_line(sid, ep.index)
    new = service.complete(g.user["user_id"], s, ep, now())
    return redirect(url_for("done", sid=sid, n=ep.index, new=1 if new else None))


# ---------- S5 완료 / S5-b·S5-c 선물 도착 ----------

@app.get("/s/<sid>/done/<int:n>")
@login_required
def done(sid, n):
    s = state_for(sid)
    nxt = rules.next_gift(s.points, n)
    gift_here = store.get_gifts(g.user["user_id"], sid).get(n) if n in s.points else None
    arr = s.arrival()
    return render_template("done.html", s=s, n=n, next_gift=nxt, gift_here=gift_here,
                           arrival=rules.arrival_text(now(), arr) if arr else "",
                           total_done=store.total_completed(g.user["user_id"]), celebrate=request.args.get("new") == "1")


@app.get("/s/<sid>/gift-arrived/<int:n>")
@login_required
def gift_arrived(sid, n):
    s = state_for(sid)
    gft = store.get_gifts(g.user["user_id"], sid).get(n)
    if not gft:
        return redirect(url_for("library"))
    if store.mark_gift_delivered(g.user["user_id"], sid, n, now().isoformat()):
        log("gift_delivered", sid, n, {"kind": gft["kind"]})
    written = rules.parse_ts(gft.get("created_at"))
    return render_template("gift_arrived.html", s=s, n=n, gift=gft,
                           written=f"{written.month}월 {written.day}일" if written else "")


# ---------- 운영자 (FR-014 일부: 데이터 확인·CSV 내려받기) ----------

@app.route("/admin", methods=["GET", "POST"])
def admin():
    password = config.get("ADMIN_PASSWORD")
    if request.method == "POST":
        session["admin"] = bool(password) and hmac.compare_digest(request.form.get("password", "").encode(), password.encode())
        return redirect(url_for("admin"))
    if not session.get("admin"):
        return render_template("admin.html", authed=False)
    counts = {t: len(store.table(t)) for t in store.TABLES}
    return render_template("admin.html", authed=True, counts=counts)


@app.get("/admin/export/<table>.csv")
def admin_export(table):
    if not session.get("admin") or table not in store.TABLES:
        abort(404)
    rows = store.table(table)
    if table == "users":  # 비밀번호 해시·로그인 토큰은 내보내지 않는다
        rows = [{k: v for k, v in r.items() if k not in ("pin_hash", "salt", "login_token_hash")} for r in rows]
    cols = list(dict.fromkeys(k for r in rows for k in r))
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=cols)
    writer.writeheader()
    writer.writerows(rows)
    # 엑셀에서 한글이 깨지지 않게 BOM
    return app.response_class("﻿" + buf.getvalue(), mimetype="text/csv",
                              headers={"Content-Disposition": f"attachment; filename={table}.csv"})


# ---------- 개발용 ----------

@app.get("/dev/time")
def dev_time():
    if not config.dev_mode():
        abort(404)
    session["time_offset_h"] = request.args.get("h", type=int) or 0
    return redirect(safe_next())


@app.get("/healthz")
def healthz():
    """배포 점검용. 값은 절대 보여 주지 않고, 설정이 '있는지'와 연결 결과만 알려 준다."""
    keys = ["NOTION_TOKEN", "NOTION_ROOT_PAGE_ID", "SECRET_KEY", "ADMIN_PASSWORD", "KV_REST_API_URL",
            "KV_REST_API_TOKEN", "UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN", "SHEET_ID"]
    report = {"env": {k: bool(config.get(k)) for k in keys}}
    try:
        report["store"] = type(store.backend()).__name__
        store.reset_cache()
        store.table("users")
        report["store_ok"] = True
    except Exception as e:  # 연결 실패 이유만 (비밀값 없음)
        report["store_ok"] = f"{type(e).__name__}: {str(e)[:120]}"
    try:
        report["notion_seasons"] = len(notion.list_seasons())
    except notion.NotionError as e:
        report["notion_seasons"] = f"오류 {str(e)[:120]}"
    report["ok"] = report["store_ok"] is True and isinstance(report["notion_seasons"], int)
    return report


if __name__ == "__main__":
    app.run(port=8510, debug=config.dev_mode())
