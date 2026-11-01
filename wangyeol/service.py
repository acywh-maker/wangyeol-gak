"""화면이 쓰는 시즌 상태 계산과 사용자 행동 처리 (UI 없음)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from . import notion, planner, rules, store
from .parser import Season
from .planner import Episode

DEFAULT_MINUTES = 10  # S6를 건너뛰었을 때 (기본값)
COMEBACK_DAYS = 3  # BR-003: 마지막 완료 후 며칠이면 S3 복귀 선택 (기본값)
REPORT_MIN_EPISODES = 10  # S7 완결 리포트는 10화 이상 시즌을 완결하고 한 줄을 남겼을 때만 (사용자 확정)


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
    lines: dict[int, str] = field(default_factory=dict)  # 오늘의 한 줄 {회차: 글}

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

    def away_days(self, now: datetime) -> int:
        """S3 표시 조건(FR-008): 보는 중인 시즌의 마지막 완료 후 3일 이상이면 그 날 수, 아니면 0."""
        if not self.started or self.finished or self.last_completed_at is None:
            return 0
        days = rules.days_since(self.last_completed_at, now)
        return days if days >= COMEBACK_DAYS else 0

    @property
    def has_report(self) -> bool:
        return self.finished and self.total >= REPORT_MIN_EPISODES and any(i <= self.total for i in self.lines)


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
    state.lines = store.all_lines(user_id, row["id"])
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
    if not new and ep.index != state.current_ep:
        return False
    # 이미 끝낸 회차라도 지금 볼 차례면('1화부터 다시 보기' 뒤) 기록은 그대로 두고 진행 위치만 다음 화로
    current = max(state.current_ep, ep.index + 1)
    store.save_progress(user_id, state.row["id"], current_ep=current, last_completed_ep=ep.index,
                        last_end_pos=store.pos_key(ep.end), last_completed_at=ts)
    if not new:
        return False
    store.log_event(ts, user_id, "ep_complete", state.row["id"], ep.index, {"est_min": ep.minutes})
    if len(state.done | {ep.index}) >= state.total:
        store.log_event(ts, user_id, "season_complete", state.row["id"], ep.index)
    return True


def restart(user_id: str, state: SeasonState) -> None:
    """S3 '1화부터 다시 보기': 진행 위치만 1화로. 완료·한 줄·예측·선물 기록은 지우지 않는다 (FR-008)."""
    store.save_progress(user_id, state.row["id"], current_ep=1,
                        restart_count=(state.progress or {}).get("restart_count", 0) + 1)


def most_recent(user_id: str, states: list[SeasonState]) -> SeasonState | None:
    """서재 하단 '이어보기' 대상: 가장 최근에 본(또는 시작한) 완결 전 시즌."""
    by_id = {p["season_id"]: p for p in store.all_progress(user_id)}
    live = [s for s in states if s.started and not s.finished]
    if not live:
        return None
    return max(live, key=lambda s: by_id[s.row["id"]].get("last_completed_at") or by_id[s.row["id"]].get("started_at") or "")


def library_order(user_id: str, states: list[SeasonState]) -> list[SeasonState]:
    """S2 카드 순서 (v02): 보는 중(최근에 본 것 위, 이어보기 대상이 맨 위) → 새 시즌(노션 순서)
    → 완결(먼저 끝낸 것 위, 본 순서대로)."""
    by_id = {p["season_id"]: p for p in store.all_progress(user_id)}

    def seen(s: SeasonState) -> str:
        p = by_id.get(s.row["id"], {})
        return p.get("last_completed_at") or p.get("started_at") or ""

    live = sorted((s for s in states if s.started and not s.finished), key=seen, reverse=True)
    new = [s for s in states if not s.started]
    done = sorted((s for s in states if s.finished), key=seen)
    return live + new + done
