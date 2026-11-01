"""로컬 확인용 계정 3개를 만든다 (data/store.json, 배포 저장소에는 쓰지 않음).

    python scripts/seed_review_users.py

시즌은 '논리의 기초'(모두에게 공개) 하루 20분 = 13화, 선물 지점 7화(중간)·13화(완결).
- 점검복귀: 3화까지 보고 4일 쉼 → 시즌을 열면 S3 복귀 선택
- 점검중간선물: 6화까지 봄 → 7화를 다 보면 S5 → S5-b 중간 선물(편지)
- 점검완결: 12화까지 봄 → 13화를 다 보면 S5 → S5-c 완결 선물 → S7 완결 리포트
다시 실행하면 이 세 계정만 지우고 새로 만든다.
"""
import sys
import warnings
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore")

from wangyeol import auth, notion, planner, rules, store  # noqa: E402

PIN = "1357"  # 로컬 확인용
SEASON_TITLE = "논리의 기초"
MINUTES = 20
LINES = {1: "전제가 참이어도 결론이 거짓일 수 있다.", 2: "타당성과 건전성은 다르다.",
         3: "반례 하나로 충분하다.", 5: "숨은 전제부터 찾자.", 9: "조건문은 거꾸로 읽으면 안 된다.",
         12: "논리는 결국 말의 정리다."}
ACCOUNTS = {"점검복귀": 3, "점검중간선물": 6, "점검완결": 12}  # 닉네임: 끝낸 회차


def wipe(nicknames: set[str]) -> None:
    data = store._load()
    ids = {u["user_id"] for u in data["users"] if u["nickname"] in nicknames}
    for table in store.TABLES:
        data[table] = [r for r in data[table] if r.get("user_id") not in ids]
    store._save(data)


def main() -> None:
    row = next(r for r in notion.list_seasons() if r["title"] == SEASON_TITLE)
    episodes = planner.plan(notion.load_season(row), MINUTES)
    total, sid = len(episodes), row["id"]
    mid, final = rules.gift_points(total)
    now = rules.now_kst()
    wipe(set(ACCOUNTS))

    for nick, done in ACCOUNTS.items():
        user, err, _ = auth.enter(nick, PIN, (now - timedelta(days=20)).isoformat())
        assert user, err
        uid = user["user_id"]
        # 마지막 완료: 복귀 계정은 4일 전, 나머지는 어제 밤 → 오늘 다음 화 도착
        last_day = now - timedelta(days=4 if nick == "점검복귀" else 1)
        for ep in episodes[:done]:
            at = (last_day - timedelta(days=done - ep.index)).replace(hour=21, minute=0, second=0, microsecond=0)
            store.add_completion(uid, sid, ep.index, ep.start, ep.end, ep.minutes, at.isoformat())
            if ep.index in LINES:
                store.save_line(uid, sid, ep.index, LINES[ep.index], at.isoformat())
        started = (last_day - timedelta(days=done)).isoformat()
        store.save_progress(uid, sid, minutes=MINUTES, plan=[e.start for e in episodes], current_ep=done + 1,
                            last_completed_ep=done, last_end_pos=store.pos_key(episodes[done - 1].end),
                            last_completed_at=last_day.replace(hour=21, minute=0, second=0, microsecond=0).isoformat(),
                            restart_count=0, started_at=started)
        store.save_gift(uid, sid, mid, "letter", now=started,
                        letter_text=f"{mid}화까지 온 나에게. 바빴을 텐데 여기까지 왔네. 남은 것도 천천히 가 보자.")
        store.save_gift(uid, sid, final, "gifticon", gift_item="아메리카노 (예시)", now=started,
                        letter_text="끝까지 온 나에게. 수고했어, 커피 한 잔 하자.")
        if done >= mid:  # 이미 지나온 중간 선물은 받은 것으로
            store.mark_gift_delivered(uid, sid, mid, now.isoformat())
        print(f"{nick}: {done}/{total}화 완료")


if __name__ == "__main__":
    main()
