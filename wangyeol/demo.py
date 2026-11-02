"""시연·점검 계정: 시즌을 n화까지 본 상태를 만든다 (UI 없음).

- 시연 계정 '소설'(배포 사이트용): 앱이 켜질 때 계정을 만들어 두고, PIN으로 들어올 때마다
  '논리의 기초'를 3화까지 보고 4일 쉰 상태로 되돌린다 → 시즌을 열면 S3 복귀 선택("4일 만이네요").
- scripts/seed_review_users.py(로컬 점검 계정)도 같은 seed_season을 쓴다.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from . import auth, notion, planner, rules, store

PIN = "1357"  # 시연·점검용 (공개 저장소에 있음 — 실제 사용자 PIN 아님)
SEASON_TITLE = "논리의 기초"
MINUTES = 20
LINES = {1: "전제가 참이어도 결론이 거짓일 수 있다.", 2: "타당성과 건전성은 다르다.",
         3: "반례 하나로 충분하다.", 5: "숨은 전제부터 찾자.", 9: "조건문은 거꾸로 읽으면 안 된다.",
         12: "논리는 결국 말의 정리다."}
COMEBACK_NICK, COMEBACK_DONE, COMEBACK_AWAY = "소설", 3, 4  # 3화까지 보고 4일 쉼 (사용자 지정)


def season_row() -> dict:
    return next(r for r in notion.list_seasons() if r["title"] == SEASON_TITLE)


def seed_season(user_id: str, row: dict, done: int, away_days: int, now: datetime) -> None:
    """기록을 지우고, 하루 한 화씩 done화까지 본 뒤 away_days일 쉰 상태로 만든다(완료는 매일 밤 9시)."""
    episodes = planner.plan(notion.load_season(row), MINUTES)
    sid = row["id"]
    mid, final = rules.gift_points(len(episodes))
    store.clear_user_records(user_id)
    last_day = (now - timedelta(days=away_days)).replace(hour=21, minute=0, second=0, microsecond=0)
    for ep in episodes[:done]:
        at = last_day - timedelta(days=done - ep.index)
        store.add_completion(user_id, sid, ep.index, ep.start, ep.end, ep.minutes, at.isoformat())
        if ep.index in LINES:
            store.save_line(user_id, sid, ep.index, LINES[ep.index], at.isoformat())
    started = (last_day - timedelta(days=done)).isoformat()
    store.save_progress(user_id, sid, minutes=MINUTES, plan=[e.start for e in episodes], current_ep=done + 1,
                        last_completed_ep=done, last_end_pos=store.pos_key(episodes[done - 1].end),
                        last_completed_at=last_day.isoformat(), restart_count=0, started_at=started)
    store.save_gift(user_id, sid, mid, "letter", now=started,
                    letter_text=f"{mid}화까지 온 나에게. 바빴을 텐데 여기까지 왔네. 남은 것도 천천히 가 보자.")
    store.save_gift(user_id, sid, final, "gifticon", gift_item="아메리카노 (예시)", now=started,
                    letter_text="끝까지 온 나에게. 수고했어, 커피 한 잔 하자.")
    if done >= mid:  # 이미 지나온 중간 선물은 받은 것으로
        store.mark_gift_delivered(user_id, sid, mid, now.isoformat())


def ensure_comeback_user(now: datetime) -> None:
    """시연 계정이 없으면 만든다(배포 사이트는 Reboot하면 기록이 지워지므로 켜질 때마다 확인)."""
    if not store.get_user(COMEBACK_NICK):
        auth.enter(COMEBACK_NICK, PIN, now.isoformat())


def reset_comeback(user: dict, now: datetime) -> None:
    """시연 계정으로 PIN 입장할 때마다 '3화까지 보고 4일 쉰' 상태로 되돌린다(몇 번이고 같은 시연)."""
    if user["nickname"] == COMEBACK_NICK:
        seed_season(user["user_id"], season_row(), COMEBACK_DONE, COMEBACK_AWAY, now)
