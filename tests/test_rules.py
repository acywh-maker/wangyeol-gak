from datetime import datetime

from wangyeol import rules
from wangyeol.rules import KST


def t(m, d, h, mi=0):
    return datetime(2026, m, d, h, mi, tzinfo=KST)


def test_arrival_next_day_6am():
    assert rules.arrival_after(t(10, 29, 21)) == t(10, 30, 6)
    assert rules.arrival_after(t(10, 30, 1)) == t(10, 31, 6)  # 새벽 1시에 끝내도 다음 날 06:00


def test_wait_text_hours_then_minutes():
    assert rules.wait_text(t(10, 29, 16), t(10, 30, 6)) == "14시간 후"
    assert rules.wait_text(t(10, 30, 5, 1), t(10, 30, 6)) == "59분 후"
    assert rules.wait_text(t(10, 30, 5, 59, ), t(10, 30, 6)) == "1분 후"


def test_arrival_text():
    assert rules.arrival_text(t(10, 29, 16), t(10, 30, 6)) == "내일 06:00 도착 · 14시간 후"
    assert rules.arrival_text(t(10, 30, 2), t(10, 30, 6)) == "오늘 06:00 도착 · 4시간 후"


def test_season_status():
    now = t(10, 29, 22)
    assert rules.season_status(False, 0, 10, 1, None, now) == ("new", "새 시즌")
    assert rules.season_status(True, 0, 10, 1, None, now) == ("arrived", "오늘의 화 도착")
    assert rules.season_status(True, 3, 10, 4, t(10, 29, 21), now) == ("waiting", "8시간 후 도착")
    assert rules.season_status(True, 3, 10, 4, t(10, 29, 21), t(10, 30, 6)) == ("arrived", "오늘의 화 도착")
    assert rules.season_status(True, 10, 10, 11, t(10, 29, 21), now) == ("done", "완결")


def test_gift_points():
    assert rules.gift_points(1) == [1]
    assert rules.gift_points(9) == [9]
    assert rules.gift_points(10) == [5, 10]
    assert rules.gift_points(11) == [6, 11]
    assert rules.gift_points(29) == [15, 29]
    assert rules.gift_points(30) == [10, 20, 30]
    assert rules.gift_points(31) == [11, 21, 31]


def test_next_gift():
    assert rules.next_gift([5, 10], 4) == (5, 1, "mid")
    assert rules.next_gift([5, 10], 5) == (10, 5, "final")
    assert rules.next_gift([5, 10], 10) is None


def test_days_since_calendar():
    assert rules.days_since(t(10, 25, 23), t(10, 29, 1)) == 4
