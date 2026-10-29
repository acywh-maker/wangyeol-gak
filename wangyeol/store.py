"""저장소 (PRD 11장). 행은 시트 한 줄과 같은 dict이며, 위치(position)처럼 구조가 있는 값은 JSON 문자열로 넣는다.

백엔드 (위에서부터 먼저 찾은 것):
- KV_REST_API_URL + KV_REST_API_TOKEN (또는 UPSTASH_REDIS_REST_*) → Upstash Redis (wangyeol/redis_store.py, Vercel 연동)
- SHEET_ID + GCP_SERVICE_ACCOUNT_JSON → 구글 시트 (wangyeol/sheets.py)
- 없으면 로컬 JSON 파일 (개발·테스트용, data/store.json 또는 WG_STORE)
요청마다 reset_cache()를 부르면, 그 요청 동안은 한 번 읽은 데이터를 다시 쓴다 (시트 API 호출 절약).
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from pathlib import Path

from . import config

TABLES = ("users", "progress", "completions", "lines", "predictions", "gifts", "events")
_LOCK = threading.RLock()
# Vercel은 /tmp만 쓸 수 있다 (재시작하면 지워짐 — 실제 운영은 구글 시트)
_DEFAULT_JSON = Path("/tmp/wangyeol-store.json") if os.environ.get("VERCEL") else config.ROOT / "data" / "store.json"
_PATH = Path(os.environ.get("WG_STORE", _DEFAULT_JSON))
_backend = None
_cache: dict | None = None


class JsonBackend:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> dict:
        if not self.path.exists():
            return {t: [] for t in TABLES}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        for t in TABLES:
            data.setdefault(t, [])
        return data

    def save(self, data: dict, table: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.path)

    def append(self, table: str, row: dict) -> None:
        self.save(_cache, table)


def set_backend(backend) -> None:
    """테스트용: 백엔드를 직접 지정."""
    global _backend, _cache
    _backend, _cache = backend, None


def set_path(path: str | Path) -> None:
    """테스트용: 로컬 JSON 저장 위치 변경."""
    set_backend(JsonBackend(Path(path)))


def backend():
    global _backend
    if _backend is None:
        sheet_id, sa = config.get("SHEET_ID"), config.get("GCP_SERVICE_ACCOUNT_JSON")
        kv_url = config.get("KV_REST_API_URL") or config.get("UPSTASH_REDIS_REST_URL")
        kv_token = config.get("KV_REST_API_TOKEN") or config.get("UPSTASH_REDIS_REST_TOKEN")
        if kv_url and kv_token:
            from .redis_store import RedisBackend
            _backend = RedisBackend.from_env(kv_url, kv_token)
        elif sheet_id and sa:
            from .sheets import SheetsBackend
            _backend = SheetsBackend.from_env(sheet_id, sa)
        else:
            _backend = JsonBackend(_PATH)
    return _backend


def reset_cache() -> None:
    """요청 시작마다 호출 — 다른 사용자가 쓴 최신 값을 다시 읽게 한다."""
    global _cache
    with _LOCK:
        _cache = None


def _load() -> dict:
    global _cache
    if _cache is None:
        _cache = backend().load()
    return _cache


def _save(data: dict, table: str, row: dict | None = None) -> None:
    """행 하나만 바뀌었으면 그 행만 저장할 수 있는 백엔드(Redis)는 행 단위로 저장한다."""
    b = backend()
    if row is not None and hasattr(b, "put"):
        b.put(table, row)
    else:
        b.save(data, table)


def _rows(table: str, **where) -> list[dict]:
    with _LOCK:
        return [r for r in _load()[table] if all(r.get(k) == v for k, v in where.items())]


def _upsert(table: str, keys: dict, values: dict) -> dict:
    with _LOCK:
        data = _load()
        for r in data[table]:
            if all(r.get(k) == v for k, v in keys.items()):
                r.update(values)
                _save(data, table, r)
                return r
        row = {**keys, **values}
        data[table].append(row)
        _save(data, table, row)
        return row


def _append(table: str, row: dict) -> dict:
    with _LOCK:
        data = _load()
        data[table].append(row)
        backend().append(table, row)
        return row


def table(name: str) -> list[dict]:
    """운영자 화면(CSV 내려받기·KPI)용 탭 전체."""
    with _LOCK:
        return list(_load()[name])


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
        row = {"user_id": user_id, "season_id": season_id, "ep_index": ep_index,
               "start_pos": pos_key(start), "end_pos": pos_key(end), "est_min": est_min, "completed_at": now}
        data["completions"].append(row)
        _save(data, "completions", row)
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
