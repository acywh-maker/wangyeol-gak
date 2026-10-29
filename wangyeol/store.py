"""저장소 (PRD 11장). 구글 시트 연결 전까지 로컬 JSON 파일에 같은 탭 구조로 저장한다.

나중에 구글 시트로 바꿀 때는 이 모듈의 _load/_save(또는 각 함수)만 교체하면 된다.
행은 시트 한 줄과 같은 dict이며, 위치(position)처럼 구조가 있는 값은 JSON 문자열로 넣는다.
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from pathlib import Path

TABLES = ("users", "progress", "completions", "lines", "predictions", "gifts", "events")
_LOCK = threading.Lock()
_PATH = Path(os.environ.get("WG_STORE", Path(__file__).resolve().parent.parent / "data" / "store.json"))


def set_path(path: str | Path) -> None:
    """테스트용 저장 위치 변경."""
    global _PATH
    _PATH = Path(path)


def _load() -> dict:
    if not _PATH.exists():
        return {t: [] for t in TABLES}
    data = json.loads(_PATH.read_text(encoding="utf-8"))
    for t in TABLES:
        data.setdefault(t, [])
    return data


def _save(data: dict) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(_PATH)


def _rows(table: str, **where) -> list[dict]:
    with _LOCK:
        return [r for r in _load()[table] if all(r.get(k) == v for k, v in where.items())]


def _upsert(table: str, keys: dict, values: dict) -> dict:
    with _LOCK:
        data = _load()
        for r in data[table]:
            if all(r.get(k) == v for k, v in keys.items()):
                r.update(values)
                _save(data)
                return r
        row = {**keys, **values}
        data[table].append(row)
        _save(data)
        return row


def _append(table: str, row: dict) -> dict:
    with _LOCK:
        data = _load()
        data[table].append(row)
        _save(data)
        return row


def pos_key(pos) -> str:
    """위치를 행의 키로 쓰기 위한 문자열 (예: '3:660.0')."""
    return f"{int(pos[0])}:{float(pos[1])}"


# ---------- users ----------

def get_user(nickname: str) -> dict | None:
    rows = _rows("users", nickname=nickname)
    return rows[0] if rows else None


def get_user_by_id(user_id: str) -> dict | None:
    rows = _rows("users", user_id=user_id)
    return rows[0] if rows else None


def create_user(nickname: str, pin_hash: str, salt: str, now: str) -> dict:
    return _append("users", {"user_id": uuid.uuid4().hex[:12], "nickname": nickname, "pin_hash": pin_hash,
                             "salt": salt, "created_at": now, "login_token_hash": "", "theme": "dark"})


def set_login_token(user_id: str, token_hash: str) -> None:
    _upsert("users", {"user_id": user_id}, {"login_token_hash": token_hash})


def get_user_by_token_hash(token_hash: str) -> dict | None:
    if not token_hash:
        return None
    rows = _rows("users", login_token_hash=token_hash)
    return rows[0] if rows else None


def set_theme(user_id: str, theme: str) -> None:
    _upsert("users", {"user_id": user_id}, {"theme": theme})


# ---------- progress ----------

def get_progress(user_id: str, season_id: str) -> dict | None:
    rows = _rows("progress", user_id=user_id, season_id=season_id)
    if not rows:
        return None
    row = dict(rows[0])
    row["plan"] = json.loads(row.get("plan") or "[]")
    return row


def save_progress(user_id: str, season_id: str, **values) -> None:
    if "plan" in values:
        values["plan"] = json.dumps([list(p) for p in values["plan"]])
    _upsert("progress", {"user_id": user_id, "season_id": season_id}, values)


def all_progress(user_id: str) -> list[dict]:
    return _rows("progress", user_id=user_id)


# ---------- completions ----------

def completed_indexes(user_id: str, season_id: str) -> set[int]:
    return {r["ep_index"] for r in _rows("completions", user_id=user_id, season_id=season_id)}


def total_completed(user_id: str) -> int:
    """누적 = (시즌, 회차) 중복 제외."""
    return len({(r["season_id"], r["ep_index"]) for r in _rows("completions", user_id=user_id)})


def add_completion(user_id: str, season_id: str, ep_index: int, start, end, est_min: int, now: str) -> bool:
    """완료 기록. 이미 있으면(연타·다시 보기) False."""
    with _LOCK:
        data = _load()
        if any(r["user_id"] == user_id and r["season_id"] == season_id and r["ep_index"] == ep_index
               for r in data["completions"]):
            return False
        data["completions"].append({"user_id": user_id, "season_id": season_id, "ep_index": ep_index,
                                    "start_pos": pos_key(start), "end_pos": pos_key(end),
                                    "est_min": est_min, "completed_at": now})
        _save(data)
        return True


# ---------- lines / predictions ----------

def get_line(user_id: str, season_id: str, ep_index: int) -> str:
    rows = _rows("lines", user_id=user_id, season_id=season_id, ep_index=ep_index)
    return rows[0]["text"] if rows else ""


def all_lines(user_id: str, season_id: str) -> dict[int, str]:
    return {r["ep_index"]: r["text"] for r in _rows("lines", user_id=user_id, season_id=season_id) if r["text"]}


def save_line(user_id: str, season_id: str, ep_index: int, text: str, now: str) -> None:
    _upsert("lines", {"user_id": user_id, "season_id": season_id, "ep_index": ep_index},
            {"text": text, "updated_at": now})


def get_prediction(user_id: str, season_id: str, ep_index: int) -> dict | None:
    rows = _rows("predictions", user_id=user_id, season_id=season_id, ep_index=ep_index)
    return rows[0] if rows else None


def save_prediction(user_id: str, season_id: str, ep_index: int, choice: int, is_correct: bool, now: str) -> None:
    """회차당 마지막 선택 1개 (다시 고르면 덮어씀)."""
    _upsert("predictions", {"user_id": user_id, "season_id": season_id, "ep_index": ep_index},
            {"choice": choice, "is_correct": is_correct, "created_at": now})


# ---------- gifts ----------

def get_gifts(user_id: str, season_id: str) -> dict[int, dict]:
    return {r["ep_index"]: r for r in _rows("gifts", user_id=user_id, season_id=season_id)}


def save_gift(user_id: str, season_id: str, ep_index: int, kind: str, letter_text: str = "",
              gift_item: str = "", now: str = "") -> None:
    _upsert("gifts", {"user_id": user_id, "season_id": season_id, "ep_index": ep_index},
            {"kind": kind, "letter_text": letter_text, "gift_item": gift_item, "created_at": now,
             "delivered_at": ""})


def mark_gift_delivered(user_id: str, season_id: str, ep_index: int, now: str) -> bool:
    """처음 도착 처리면 True."""
    rows = _rows("gifts", user_id=user_id, season_id=season_id, ep_index=ep_index)
    if not rows or rows[0].get("delivered_at"):
        return False
    _upsert("gifts", {"user_id": user_id, "season_id": season_id, "ep_index": ep_index}, {"delivered_at": now})
    return True


# ---------- events ----------

def log_event(ts: str, user_id: str, event: str, season_id: str = "", ep_index: int | None = None,
              meta: dict | None = None) -> None:
    """FR-012: 기록 실패가 화면을 막으면 안 된다 (이벤트는 버려도 됨)."""
    try:
        _append("events", {"ts": ts, "user_id": user_id, "event": event, "season_id": season_id,
                           "ep_index": ep_index, "meta": json.dumps(meta or {}, ensure_ascii=False)})
    except Exception:
        pass
