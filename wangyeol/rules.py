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


def wait_text(now: datetime, arrival: datetime) -> str:
    """7장 1번: 1시간 이상 'n시간 후', 1시간 미만 'n분 후'. 초 단위 없음."""
    sec = (arrival - now).total_seconds()
    if sec >= 3600:
        return f"{int(sec // 3600)}시간 후"
    return f"{max(1, math.ceil(sec / 60))}분 후"


def arrival_text(now: datetime, arrival: datetime) -> str:
    """S5·시즌 홈: '내일 06:00 도착 · 14시간 후'"""
    days = (arrival.date() - now.date()).days
    day = {0: "오늘", 1: "내일"}.get(days, f"{arrival.month}월 {arrival.day}일")
    return f"{day} {arrival:%H:%M} 도착 · {wait_text(now, arrival)}"


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
    return "waiting", f"{wait_text(now, arrival)} 도착"


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
