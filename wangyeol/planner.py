"""가용시간에 맞춰 조각을 회차로 묶는다 (BR-009).

규칙 (사용자 확정: 시간 우선 + 제목 보조, 비율·최소값은 기본값/내 가정):
- 허용 범위 = 가용시간 T의 85%~115%.
- 글: 허용 범위 안의 제목 경계 중 T에 가장 가까운 곳 → 없으면 허용 범위 안 아무 경계 중 T에 가장 가까운 곳
  → 그것도 없으면 115%를 넘기 직전 경계. 회차가 비어 있으면 넘치더라도 한 조각은 넣는다.
- 영상·강의: 115% 안에 들어가면 통째로. 아니면 남은 시간 r ≥ 5분이고 남는 부분도 ≥ 5분일 때 r만큼 자른다.
  그 외에는 그 앞에서 끊는다(회차가 비어 있으면 통째로).
- 진행 위치는 (조각 번호, 조각 안에서 지난 초). 가용시간을 바꾸면 마지막 완료 위치부터 다시 나눈다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .parser import Prediction, Season, Unit

LOW, HIGH = 0.85, 1.15
MIN_PIECE_SEC = 5 * 60
TAIL_MERGE = 0.25
SHORT_EPISODE = 0.5

Position = tuple[int, float]  # (unit index, offset seconds)


@dataclass
class Segment:
    unit: int
    start: float  # 조각 안 시작 초
    end: float  # 조각 안 끝 초

    @property
    def seconds(self) -> float:
        return self.end - self.start


@dataclass
class Episode:
    index: int
    start: Position
    end: Position
    segments: list[Segment] = field(default_factory=list)
    seconds: float = 0
    title: str = ""
    summary_unit: int | None = None  # 1분 요약으로 쓸 콜아웃 조각
    prediction: Prediction | None = None

    @property
    def minutes(self) -> int:
        return max(1, round(self.seconds / 60))


def _next_episode(units: list[Unit], target: float, start: Position) -> tuple[list[Segment], Position]:
    lo, hi = target * LOW, target * HIGH
    segs: list[Segment] = []
    acc = 0.0
    candidates: list[tuple[float, int, bool, int]] = []  # (누적 시간, 조각 번호, 제목 경계?, segs 길이)
    i, off = start

    def cut_at_best() -> Position:
        """허용 범위 안 경계 중 제목 우선, T에 가장 가까운 곳으로 되돌아가 끊는다."""
        in_window = [c for c in candidates if lo <= c[0] <= hi]
        pool = [c for c in in_window if c[2]] or in_window
        if pool:
            best = min(pool, key=lambda c: abs(c[0] - target))
        else:
            best = candidates[-1]  # 115%를 넘기 직전 경계
        del segs[best[3]:]
        return (best[1], 0.0)

    while i < len(units):
        u = units[i]
        rem = u.seconds - off
        if segs and off == 0:
            candidates.append((acc, i, u.heading, len(segs)))

        if u.splittable:
            if acc + rem <= hi:
                segs.append(Segment(i, off, u.seconds))
                acc += rem
                i, off = i + 1, 0.0
                continue
            r = target - acc
            short = acc < target * SHORT_EPISODE
            if short:
                # 회차가 절반도 안 찼으면 영상을 최소 5분은 잘라 넣는다 (1분짜리 회차 방지, 내 가정)
                r = max(r, MIN_PIECE_SEC)
            if r >= MIN_PIECE_SEC and rem - r >= MIN_PIECE_SEC:
                segs.append(Segment(i, off, off + r))
                return segs, (i, off + r)
            if not segs or short:
                segs.append(Segment(i, off, u.seconds))
                return segs, (i + 1, 0.0)
            return segs, (i, off)

        if acc + rem <= hi or not segs:
            segs.append(Segment(i, 0.0, u.seconds))
            acc += rem
            i += 1
            if acc > hi:  # 빈 회차에 넣은 아주 긴 조각 하나
                return segs, (i, 0.0)
            continue
        return segs, cut_at_best()

    return segs, (len(units), 0.0)


def plan(season: Season, minutes: int, start: Position = (0, 0.0), first_index: int = 1) -> list[Episode]:
    """start 위치부터 끝까지 회차 목록. first_index는 이어 붙일 회차 번호."""
    units = season.units
    target = max(1, minutes) * 60
    raw: list[tuple[Position, Position, list[Segment]]] = []
    pos = start
    while pos[0] < len(units):
        segs, end = _next_episode(units, target, pos)
        if not segs:
            break
        raw.append((pos, end, segs))
        pos = end
    # 끝에 한두 문장만 남은 회차는 앞 회차에 붙인다 (기본값/내 가정: T의 25% 미만)
    if (len(raw) >= 2 and sum(s.seconds for s in raw[-1][2]) < target * TAIL_MERGE
            and all(units[s.unit].kind == "text" for s in raw[-1][2])):
        (s0, _, a), (_, e1, b) = raw[-2], raw[-1]
        raw[-2:] = [(s0, e1, a + b)]

    # 영상·강의가 여러 회차에 걸치면 "(1/3)"처럼 몇 번째 조각인지 붙인다
    pieces: dict[int, list[int]] = {}
    for k, (_, _, segs) in enumerate(raw):
        for sg in segs:
            if units[sg.unit].splittable:
                pieces.setdefault(sg.unit, []).append(k)

    episodes: list[Episode] = []
    context = _heading_before(units, start[0])
    for k, (pos, end, segs) in enumerate(raw):
        ep = Episode(first_index + len(episodes), pos, end, segs, sum(s.seconds for s in segs))
        ep.title, context = _title(units, segs, context, ep.index)
        first_media = next((sg.unit for sg in segs if units[sg.unit].splittable and units[sg.unit].title == ep.title), None)
        if first_media is not None and start[0] == first_media and start[1] > 0:
            ep.title += " (이어서)"  # 앞 조각은 이미 지난 회차라 전체 개수를 알 수 없음
        elif first_media is not None and len(pieces[first_media]) > 1:
            ep.title += f" ({pieces[first_media].index(k) + 1}/{len(pieces[first_media])})"
        ep.summary_unit = next((s.unit for s in segs if units[s.unit].is_callout), None)
        preds = [units[s.unit].prediction for s in segs if units[s.unit].prediction and s.end >= units[s.unit].seconds]
        ep.prediction = preds[-1] if preds else None
        episodes.append(ep)
    if episodes:
        episodes[-1].prediction = None  # 마지막 화는 공개할 다음 화가 없으므로 숨김
    return episodes


def _heading_before(units: list[Unit], idx: int) -> str:
    for u in reversed(units[:idx]):
        if u.heading:
            return u.title
    return ""


def _title(units: list[Unit], segs: list[Segment], context: str, index: int) -> tuple[str, str]:
    """회차 제목: 첫 제목 → 첫 강의·영상 이름 → (앞 제목) 이어서 → 'n화'. 다음 회차용 문맥도 돌려준다."""
    headings = [units[s.unit].title for s in segs if units[s.unit].heading and units[s.unit].title]
    new_context = headings[-1] if headings else context
    if headings:
        return headings[0], new_context
    lecture = next((units[s.unit].title for s in segs if units[s.unit].splittable and units[s.unit].title), "")
    if lecture:
        return lecture, new_context
    if context:
        return f"{context} (이어서)", new_context
    return f"{index}화", new_context


def episode_count(season: Season, minutes: int) -> int:
    return len(plan(season, minutes))
