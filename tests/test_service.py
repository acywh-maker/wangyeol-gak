from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from wangyeol import rules, service, store


@pytest.fixture(autouse=True)
def tmp_store(tmp_path):
    store.set_path(tmp_path / "store.json")


NOW = datetime(2026, 11, 1, 9, 0, tzinfo=rules.KST)


def ep(i):
    return SimpleNamespace(index=i, start=(i - 1, 0.0), end=(i, 0.0), minutes=10)


def state(total, done=(), current_ep=1, last=None, progress=None, lines=None):
    """노션 없이 화면 판단만 확인하는 시즌 상태."""
    s = service.SeasonState({"id": "s1"}, None, progress if progress is not None else {"restart_count": 0},
                            [ep(i) for i in range(1, total + 1)], set(done), lines=lines or {})
    s.current_ep, s.last_completed_at = current_ep, last
    s.status = rules.season_status(True, len(s.done), total, current_ep, last, NOW)
    return s


def test_away_days_from_three_days():
    assert state(13, {1, 2}, 3, NOW - timedelta(days=2)).away_days(NOW) == 0
    assert state(13, {1, 2}, 3, NOW - timedelta(days=4)).away_days(NOW) == 4
    assert state(13, current_ep=1).away_days(NOW) == 0  # 아직 한 화도 안 봄
    assert state(3, {1, 2, 3}, 4, NOW - timedelta(days=9)).away_days(NOW) == 0  # 완결


def test_report_only_for_finished_seasons_of_ten_or_more_with_a_line():
    line = {3: "한 줄"}
    assert state(10, range(1, 11), 11, NOW, lines=line).has_report
    assert not state(10, range(1, 11), 11, NOW).has_report  # 한 줄이 없음
    assert not state(9, range(1, 10), 10, NOW, lines=line).has_report
    assert not state(13, range(1, 13), 13, NOW, lines=line).has_report  # 마지막 화 전


def test_restart_keeps_records_and_rewatch_moves_position():
    for i in (1, 2, 3):
        store.add_completion("u", "s1", i, (i - 1, 0), (i, 0), 10, NOW.isoformat())
    store.save_progress("u", "s1", current_ep=4, restart_count=0)
    s = state(13, {1, 2, 3}, 4, NOW - timedelta(days=4))
    service.restart("u", s)
    p = store.get_progress("u", "s1")
    assert p["current_ep"] == 1 and p["restart_count"] == 1
    assert store.completed_indexes("u", "s1") == {1, 2, 3}  # 기록은 그대로

    s = state(13, {1, 2, 3}, 1, NOW - timedelta(days=4), progress=p)
    assert service.complete("u", s, ep(1), NOW) is False  # 새 완료는 아님
    assert store.get_progress("u", "s1")["current_ep"] == 2  # 그래도 다음 화로
    assert len(store._rows("completions")) == 3


def test_rewatching_older_episode_does_not_move_position():
    store.add_completion("u", "s1", 1, (0, 0), (1, 0), 10, NOW.isoformat())
    store.save_progress("u", "s1", current_ep=2)
    assert service.complete("u", state(13, {1}, 2, NOW), ep(1), NOW) is False
    assert store.get_progress("u", "s1")["current_ep"] == 2
