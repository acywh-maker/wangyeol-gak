"""화면이 쓰는 시즌 상태 계산과 사용자 행동 처리 (UI 없음)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from . import notion, planner, rules, store
from .parser import Season
from .planner import Episode

DEFAULT_MINUTES = 10  # S6를 건너뛰었을 때 (기본값)


@dataclass
class SeasonState:
    row: dict
    season: Season
    progress: dict | None
    episodes: list[Episode]
    done: set[int] = field(default_factory=set)
    current_ep: int = 1
    last_completed_at: datetime | None = None
    status: tuple[str, str] = ("new", "새 시즌")
    points: list[int] = field(default_factory=list)

    @property
    def started(self) -> bool:
        return self.progress is not None

    @property
    def minutes(self) -> int:
        return (self.progress or {}).get("minutes") or DEFAULT_MINUTES

    @property
    def total(self) -> int:
        return len(self.episodes)

    @property
    def finished(self) -> bool:
        return self.status[0] == "done"

    @property
    def next_ep(self) -> Episode | None:
        """이어보기 대상."""
        return self.episodes[self.current_ep - 1] if self.current_ep <= self.total else None

    def arrival(self) -> datetime | None:
        """현재 회차의 도착 시각 (첫 화이거나 완결이면 None)."""
        if self.last_completed_at is None or self.finished:
            return None
        return rules.arrival_after(self.last_completed_at)

    def is_arrived(self, now: datetime) -> bool:
        arr = self.arrival()
        return arr is None or now >= arr


def load_state(user_id: str, row: dict, now: datetime) -> SeasonState:
    season = notion.load_season(row)
    progress = store.get_progress(user_id, row["id"])
    done = store.completed_indexes(user_id, row["id"])

    if progress:
        starts = progress["plan"]
        if not planner.starts_valid(season, starts):
            # 노션에서 내용이 바뀜 → 끝낸 회차까지 유지하고 다시 나눔 (13장)
            keep = min(max(done, default=0), len([p for p in starts if p[0] < len(season.units)]))
            starts = planner.replan(season, progress["minutes"], [p for p in starts if p[0] < len(season.units)], keep)
            store.save_progress(user_id, row["id"], plan=starts)
        episodes = planner.episodes_from_starts(season, starts)
    else:
        episodes = planner.plan(season, DEFAULT_MINUTES)

    state = SeasonState(row, season, progress, episodes, done)
    if progress:
        state.current_ep = max(1, min(progress.get("current_ep") or 1, len(episodes) + 1))
        state.last_completed_at = rules.parse_ts(progress.get("last_completed_at"))
    state.points = rules.gift_points(len(episodes))
    state.status = rules.season_status(state.started, len(done & set(range(1, len(episodes) + 1))),
                                       len(episodes), state.current_ep, state.last_completed_at, now)
    return state


def preview(season: Season, minutes: int) -> tuple[int, list[int]]:
    """S6: 가용시간을 고르면 바로 보여 줄 회차 수와 선물 지점."""
    n = len(planner.plan(season, minutes))
    return n, rules.gift_points(n)


def start_or_update(user_id: str, state: SeasonState, minutes: int, now: datetime) -> None:
    """S6 저장. 처음이면 전체를 나누고, 이미 진행 중이면 끝낸 회차까지 유지하고 다시 나눈다."""
    if state.progress and state.progress.get("minutes") == minutes:
        return
    if state.progress:
        keep = max(state.done, default=0)
        starts = planner.replan(state.season, minutes, [e.start for e in state.episodes], keep)
        store.save_progress(user_id, state.row["id"], minutes=minutes, plan=starts)
    else:
        starts = [e.start for e in planner.plan(state.season, minutes)]
        store.save_progress(user_id, state.row["id"], minutes=minutes, plan=starts, current_ep=1,
                            last_completed_ep=0, last_end_pos="", last_completed_at="",
                            restart_count=0, started_at=now.isoformat())


def complete(user_id: str, state: SeasonState, ep: Episode, now: datetime) -> bool:
    """'다 봤어요'. 새로 끝낸 회차면 True (연타·다시 보기는 False)."""
    ts = now.isoformat()
    new = store.add_completion(user_id, state.row["id"], ep.index, ep.start, ep.end, ep.minutes, ts)
    if not new:
        return False
    current = max(state.current_ep, ep.index + 1)
    store.save_progress(user_id, state.row["id"], current_ep=current, last_completed_ep=ep.index,
                        last_end_pos=store.pos_key(ep.end), last_completed_at=ts)
    store.log_event(ts, user_id, "ep_complete", state.row["id"], ep.index, {"est_min": ep.minutes})
    if len(state.done | {ep.index}) >= state.total:
        store.log_event(ts, user_id, "season_complete", state.row["id"], ep.index)
    return True


def most_recent(user_id: str, states: list[SeasonState]) -> SeasonState | None:
    """서재 하단 '이어보기' 대상: 가장 최근에 본(또는 시작한) 완결 전 시즌."""
    by_id = {p["season_id"]: p for p in store.all_progress(user_id)}
    live = [s for s in states if s.started and not s.finished]
    if not live:
        return None
    return max(live, key=lambda s: by_id[s.row["id"]].get("last_completed_at") or by_id[s.row["id"]].get("started_at") or "")
