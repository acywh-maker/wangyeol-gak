"""노션 블록 → 시즌 조각(Unit) 목록 (PRD 6장, FR-003).

회차는 여기서 정하지 않는다. 조각 목록을 만들어 두면 planner가 사용자의 가용시간에 맞춰 회차로 묶는다.
이 모듈은 Streamlit·네트워크에 의존하지 않는 순수 함수만 둔다.
입력 블록은 노션 API 응답 그대로이며, 하위 블록은 block["children"]에 채워져 있다고 가정한다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import parse_qs, urlparse

ANSWER_MARK = "(정답)"

# 읽기 시간 추정 — 기본값(내 가정): 웹소설 1화 5,000자 ≈ 10분
HANGUL_PER_MIN = 500
WORDS_PER_MIN = 200
IMAGE_SEC = 12
UNKNOWN_VIDEO_SEC = 10 * 60

_TIME = r"(\d{1,2}:\d{2}(?::\d{2})?)"
_RANGE_RE = re.compile(_TIME + r"\s*[-–—~]\s*" + _TIME)
_PAREN_DURATION_RE = re.compile(r"\(\s*" + _TIME + r"\s*\)")
_KO_DURATION_RE = re.compile(r"(?:(\d+)\s*시간)?\s*(?:(\d+)\s*분)?\s*(?:(\d+)\s*초)?")
_HEADINGS = {"heading_1", "heading_2", "heading_3"}
_LECTURE_TYPES = {"to_do", "bulleted_list_item", "numbered_list_item"}


@dataclass
class Prediction:
    question: str
    choices: list[str]
    answer_index: int

    @property
    def answer(self) -> str:
        return self.choices[self.answer_index]


@dataclass
class Unit:
    """회차를 나누는 최소 단위. 최상위 블록 1개(+ 붙어 있는 예측 묶음)."""
    kind: str  # "text" | "video" | "lecture"
    blocks: list
    seconds: float
    title: str = ""  # 제목 블록 / 강의 이름
    heading: bool = False  # 제목1~3으로 시작 → 허용 범위 안에서 우선 경계
    is_callout: bool = False
    youtube: dict | None = None  # {"id", "range": (start, end) | None}
    prediction: Prediction | None = None

    @property
    def splittable(self) -> bool:
        return self.kind in ("video", "lecture")


@dataclass
class Season:
    id: str
    title: str
    url: str
    owner: str | None
    units: list[Unit] = field(default_factory=list)

    @property
    def total_seconds(self) -> float:
        return sum(u.seconds for u in self.units)

    def block_url(self, block_id: str | None) -> str:
        return f"{self.url}#{block_id.replace('-', '')}" if block_id else self.url


# ---------- rich text ----------

def plain(rich_text: list | None) -> str:
    return "".join(rt.get("plain_text", "") for rt in rich_text or [])


def rich_text_of(block: dict) -> list:
    data = block.get(block["type"], {})
    return (data.get("rich_text", []) or []) if isinstance(data, dict) else []


def block_text(block: dict) -> str:
    """블록과 하위 블록의 글자 전체 (읽기 시간 추정용)."""
    data = block.get(block["type"], {})
    parts = [plain(rich_text_of(block))]
    if isinstance(data, dict) and data.get("caption"):
        parts.append(plain(data["caption"]))
    parts += [block_text(c) for c in block.get("children", [])]
    return " ".join(p for p in parts if p)


# ---------- 시간 ----------

def _seconds(t: str) -> int:
    total = 0
    for part in t.split(":"):
        total = total * 60 + int(part)
    return total


def parse_range(text: str) -> tuple[int, int] | None:
    """'12:30-17:45' → (750, 1065). 형식이 틀리거나 끝이 시작보다 앞이면 None(전체 재생)."""
    m = _RANGE_RE.search(text or "")
    if not m:
        return None
    start, end = _seconds(m.group(1)), _seconds(m.group(2))
    return (start, end) if end > start else None


def parse_duration(text: str) -> int | None:
    """'(14:10)', '29분 17초', '1시간 33분 16초', '29분 17초+27분 28초'(합산) → 초. 없으면 None."""
    text = text or ""
    found = [_seconds(m.group(1)) for m in _PAREN_DURATION_RE.finditer(text)]
    if found:  # '(14:10)' 표기가 있으면 그것만 쓴다 ("약 50분" 같은 메모와 이중 계산 방지)
        return sum(found)
    for m in _KO_DURATION_RE.finditer(text):
        h, mi, s = m.groups()
        if h or mi or s:
            found.append(int(h or 0) * 3600 + int(mi or 0) * 60 + int(s or 0))
    total = sum(found)
    return total or None


def reading_seconds(text: str) -> float:
    hangul = len(re.findall(r"[가-힣]", text))
    words = len(re.findall(r"[A-Za-z]+", text))
    return hangul / HANGUL_PER_MIN * 60 + words / WORDS_PER_MIN * 60


def fmt_clock(sec: float) -> str:
    sec = int(round(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ---------- 유튜브 ----------

def youtube_id(url: str) -> str | None:
    try:
        u = urlparse(url)
    except ValueError:
        return None
    host = (u.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    if host == "youtu.be":
        vid = u.path.lstrip("/").split("/")[0]
    elif host in ("youtube.com", "youtube-nocookie.com"):
        if u.path == "/watch":
            vid = parse_qs(u.query).get("v", [""])[0]
        else:
            parts = u.path.strip("/").split("/")
            vid = parts[1] if len(parts) >= 2 and parts[0] in ("embed", "shorts", "live", "v") else ""
    else:
        return None
    return vid if re.fullmatch(r"[\w-]{10,20}", vid or "") else None


def media_url(block: dict) -> str | None:
    data = block.get(block["type"], {})
    if "url" in data:  # embed, bookmark
        return data["url"]
    kind = data.get("type")
    return (data.get(kind) or {}).get("url") if kind else None


def _is_range_note(block: dict | None) -> bool:
    return bool(block) and block["type"] == "paragraph" and plain(rich_text_of(block)).strip().startswith("▶")


def _video_info(block: dict, note: dict | None, video_info) -> dict | None:
    """유튜브 영상/임베드면 {"id", "range", "seconds", "title"}. 길이: 구간 → 자동 → (14:10) → 10분."""
    if block["type"] not in ("video", "embed"):
        return None
    vid = youtube_id(media_url(block) or "")
    if not vid:
        return None
    caption = plain(block[block["type"]].get("caption"))
    rng = parse_range(caption) or (parse_range(plain(rich_text_of(note))) if note else None)
    meta = video_info(vid) or {}
    if rng:
        seconds = rng[1] - rng[0]
    else:
        seconds = meta.get("seconds") or parse_duration(caption) or UNKNOWN_VIDEO_SEC
    title = re.sub(_RANGE_RE.pattern + "|" + _PAREN_DURATION_RE.pattern, "", caption).strip() or meta.get("title", "")
    return {"id": vid, "range": rng, "seconds": seconds, "title": title}


def _annotate_nested(blocks: list, video_info) -> tuple[list, float]:
    """하위 블록 안의 영상에 _yt 표시를 붙이고, 그 영상 시간 합계를 돌려준다(자르지 않음)."""
    out, video_sec = [], 0.0
    i = 0
    while i < len(blocks):
        b = blocks[i]
        nxt = blocks[i + 1] if i + 1 < len(blocks) else None
        info = _video_info(b, nxt if _is_range_note(nxt) else None, video_info)
        if info:
            b = {**b, "_yt": {"id": info["id"], "range": info["range"]}}
            video_sec += info["seconds"]
            if _is_range_note(nxt):
                i += 1
        if b.get("children"):
            kids, sec = _annotate_nested(b["children"], video_info)
            b = {**b, "children": kids}
            video_sec += sec
        out.append(b)
        i += 1
    return out, video_sec


# ---------- 예측 선택 ----------

def _is_answer(item: dict) -> bool:
    rt = rich_text_of(item)
    if plain(rt).rstrip().endswith(ANSWER_MARK):
        return True
    return any(r.get("annotations", {}).get("bold") and r.get("plain_text", "").strip() for r in rt)


def _choice_text(item: dict) -> str:
    return plain(rich_text_of(item)).strip().removesuffix(ANSWER_MARK).strip()


def prediction_at(blocks: list, i: int) -> Prediction | None:
    """blocks[i]가 인용이고 바로 아래 글머리가 정확히 2개, 정답이 1개면 예측."""
    if blocks[i]["type"] != "quote":
        return None
    items = []
    for b in blocks[i + 1:]:
        if b["type"] != "bulleted_list_item":
            break
        items.append(b)
    if len(items) != 2:
        return None
    answers = [k for k, it in enumerate(items) if _is_answer(it)]
    question = plain(rich_text_of(blocks[i])).strip()
    if len(answers) != 1 or not question:
        return None
    return Prediction(question, [_choice_text(it) for it in items], answers[0])


# ---------- 조각 만들기 ----------

def _heading_text(block: dict) -> str:
    return plain(rich_text_of(block)).strip()


_FLATTEN = {"paragraph", "bulleted_list_item", "numbered_list_item", "to_do", "quote", "callout",
            "heading_1", "heading_2", "heading_3", "column_list", "column", "synced_block"}


def _lecture_seconds(block: dict) -> int | None:
    """할 일 항목은 '29분 17초' 같은 한글 표기도 길이로 읽는다.
    일반 목록은 '(14:10)' 표기만 — 본문 속 "하루 3분" 같은 말을 강의로 오인하지 않게."""
    t = block["type"]
    if t not in _LECTURE_TYPES or block.get("children"):
        return None
    text = plain(rich_text_of(block))
    if t == "to_do":
        return parse_duration(text)
    return sum(_seconds(m) for m in _PAREN_DURATION_RE.findall(text)) or None


def _has_media(blocks: list) -> bool:
    for b in blocks:
        if b["type"] in ("video", "embed") and youtube_id(media_url(b) or ""):
            return True
        if _lecture_seconds(b):
            return True
        if b["type"] in _FLATTEN and _has_media(b.get("children", [])):
            return True
    return False


def build_units(blocks: list, video_info: Callable[[str], dict | None] = lambda _id: None) -> list[Unit]:
    units: list[Unit] = []
    i = 0
    while i < len(blocks):
        b = blocks[i]
        t = b["type"]

        pred = prediction_at(blocks, i)
        if pred:
            # 예측 묶음은 앞 조각에 붙여 절대 쪼개지 않는다
            if units:
                units[-1].prediction = pred
            else:
                units.append(Unit("text", [], 0, prediction=pred))
            i += 3
            continue

        nxt = blocks[i + 1] if i + 1 < len(blocks) else None
        note = nxt if _is_range_note(nxt) else None
        info = _video_info(b, note, video_info)
        if info:
            units.append(Unit("video", [b], info["seconds"], title=info["title"],
                              youtube={"id": info["id"], "range": info["range"]}))
            i += 2 if note else 1
            continue

        sec = _lecture_seconds(b)
        if sec:
            units.append(Unit("lecture", [b], sec, title=plain(rich_text_of(b)).strip()))
            i += 1
            continue

        if t in _FLATTEN and _has_media(b.get("children", [])):
            # 목록·문단 안쪽의 영상/강의는 꺼내서 각각 자를 수 있는 조각으로 만든다 (토글은 제외)
            parent = {k: v for k, v in b.items() if k != "children"}
            if plain(rich_text_of(parent)).strip():
                units.append(Unit("text", [parent], reading_seconds(block_text(parent)),
                                  title=_heading_text(parent) if t in _HEADINGS else "", heading=t in _HEADINGS))
            units += build_units(b["children"], video_info)
            i += 1
            continue

        annotated, video_sec = _annotate_nested([b], video_info)
        b = annotated[0]
        sec = reading_seconds(block_text(b)) + video_sec
        if t == "image":
            sec += IMAGE_SEC
        units.append(Unit(
            "text", [b], sec,
            title=_heading_text(b) if t in _HEADINGS else "",
            heading=t in _HEADINGS,
            is_callout=t == "callout",
        ))
        i += 1
    return units


def parse_season(page_id: str, title: str, url: str, owner: str | None, blocks: list,
                 video_info: Callable[[str], dict | None] = lambda _id: None) -> Season:
    return Season(page_id, title, url, owner, build_units(blocks, video_info))


def earliest_expiry(blocks: list) -> str | None:
    """노션 업로드 파일 URL 중 가장 빨리 만료되는 시각(ISO). 만료 시 재요청 판단용."""
    found = []

    def walk(bs):
        for b in bs:
            data = b.get(b["type"], {})
            if isinstance(data, dict) and data.get("type") == "file":
                exp = data.get("file", {}).get("expiry_time")
                if exp:
                    found.append(exp)
            walk(b.get("children", []))

    walk(blocks)
    return min(found) if found else None
