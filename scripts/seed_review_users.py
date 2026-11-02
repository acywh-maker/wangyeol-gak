"""로컬 확인용 계정 3개를 만든다 (data/store.json, 배포 저장소에는 쓰지 않음).

    python scripts/seed_review_users.py

시즌은 '논리의 기초'(모두에게 공개) 하루 20분 = 13화, 선물 지점 7화(중간)·13화(완결).
- 점검복귀: 3화까지 보고 4일 쉼 → 시즌을 열면 S3 복귀 선택
- 점검중간선물: 6화까지 봄 → 7화를 다 보면 S5 → S5-b 중간 선물(편지)
- 점검완결: 12화까지 봄 → 13화를 다 보면 S5 → S5-c 완결 선물 → S7 완결 리포트
다시 실행하면 이 세 계정의 기록만 지우고 새로 만든다. 상태를 만드는 규칙은 wangyeol/demo.py (배포 시연 계정 '소설'과 같음).
"""
import sys
import warnings
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore")

from wangyeol import auth, demo, rules  # noqa: E402

ACCOUNTS = {"점검복귀": (3, 4), "점검중간선물": (6, 1), "점검완결": (12, 1)}  # 닉네임: (끝낸 회차, 쉰 날)


def main() -> None:
    row = demo.season_row()
    now = rules.now_kst()
    for nick, (done, away) in ACCOUNTS.items():
        user, err, _ = auth.enter(nick, demo.PIN, (now - timedelta(days=20)).isoformat())
        assert user, err
        demo.seed_season(user["user_id"], row, done, away, now)
        print(f"{nick}: {done}화 완료, {away}일 전 마지막")


if __name__ == "__main__":
    main()
