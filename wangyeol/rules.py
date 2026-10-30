"""비즈니스 규칙 (PRD 10장). 시간은 모두 한국 시간(BR-001). 순수 함수만 둔다."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))  # 한국은 서머타임이 없어 고정 오프셋으로 충분
ARRIVAL_HOUR = 6  # BR-002 기본값
RETURN_DAYS = 3  # BR-003 기본값


def now_kst(offset: timedelta = timedelta()) -> datetime:
    return datetime.now(KST) + offset


def parse_ts(ts: str | None) -> datetime | None:
    return datetime.fromisoformat(ts).astimezone(KST) if ts else None


def arrival_after(completed_at: datetime) -> datetime:
    """BR-002: 완료한 다음 날 06:00."""
    day = completed_at.astimezone(KST).date() + timedelta(days=1)
    return datetime(day.year, day.month, day.day, ARRIVAL_HOUR, tzinfo=KST)


def remain_text(now: datetime, arrival: datetime) -> str:
    """도착까지 남은 시간 (v02 사용자 지정, 모든 화면): '14시간 30분 남음', 1시간 미만 '30분 남음'.
    매일 같은 시간을 알려 주는 정보형 — 초 단위 카운트다운은 없음(7장 1번)."""
    mins = max(1, math.ceil((arrival - now).total_seconds() / 60))
    h, m = divmod(mins, 60)
    return f"{h}시간 {m}분 남음" if h else f"{m}분 남음"


def clock_text(t: datetime) -> str:
    """'오전 6시', '오후 9시 30분'"""
    h12 = t.hour % 12 or 12
    return f"{'오전' if t.hour < 12 else '오후'} {h12}시" + (f" {t.minute}분" if t.minute else "")


def day_text(now: datetime, t: datetime) -> str:
    days = (t.date() - now.date()).days
    return {0: "오늘", 1: "내일"}.get(days, f"{t.month}월 {t.day}일")


def arrival_text(now: datetime, arrival: datetime) -> str:
    """시즌 홈 회차 목록: '내일 오전 6시 도착 · 14시간 30분 남음'"""
    return f"{day_text(now, arrival)} {clock_text(arrival)} 도착 · {remain_text(now, arrival)}"


def arrival_sentence(now: datetime, arrival: datetime, ep_no: int) -> str:
    """S5 다음 화 안내: '내일 오전 6시에 2화가 도착해요 · 14시간 30분 남음'"""
    return f"{day_text(now, arrival)} {clock_text(arrival)}에 {ep_no}화가 도착해요 · {remain_text(now, arrival)}"


def season_status(started: bool, completed: int, total: int, current_ep: int,
                  last_completed_at: datetime | None, now: datetime) -> tuple[str, str]:
    """S2 배지. (kind, 문구) kind = new | done | arrived | waiting"""
    if not started:
        return "new", "새 시즌"
    if completed >= total or current_ep > total:
        return "done", "완결"
    if last_completed_at is None:
        return "arrived", "오늘의 화 도착"
    arrival = arrival_after(last_completed_at)
    if now >= arrival:
        return "arrived", "오늘의 화 도착"
    return "waiting", remain_text(now, arrival)


def gift_points(total: int) -> list[int]:
    """BR-005: 9화 이하 1개 / 10~29화 2개 / 30화 이상 3개. 마지막 = 완결 선물."""
    if total <= 9:
        return [max(1, total)]
    if total <= 29:
        return [math.ceil(total / 2), total]
    return [math.ceil(total / 3), math.ceil(total * 2 / 3), total]


def next_gift(points: list[int], done_index: int) -> tuple[int, int, str] | None:
    """방금 끝낸 회차 다음의 선물 지점. (지점, 남은 회차, 'mid'|'final') / 없으면 None."""
    for p in points:
        if p > done_index:
            return p, p - done_index, "final" if p == points[-1] else "mid"
    return None


def days_since(last_completed_at: datetime, now: datetime) -> int:
    """BR-003: 한국 시간 날짜 차이."""
    return (now.astimezone(KST).date() - last_completed_at.astimezone(KST).date()).days
