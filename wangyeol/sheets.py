"""구글 시트 저장 백엔드 (PRD 11장 탭 구조).

- 읽기: 요청마다 전체 탭을 batch 1회로 읽는다 (store가 요청 동안 캐시).
- 쓰기: 바뀐 탭만 통째로 다시 쓴다. events 탭은 계속 늘어나므로 한 줄씩 덧붙인다.
- 값은 RAW로 쓴다 — 사용자가 쓴 한 줄이 '='로 시작해도 수식으로 실행되지 않게.
"""
from __future__ import annotations

import json

# 탭별 컬럼과 타입 (시트는 모두 문자열로 돌려주므로 읽을 때 되돌린다)
SCHEMA: dict[str, list[tuple[str, type]]] = {
    "users": [("user_id", str), ("nickname", str), ("pin_hash", str), ("salt", str), ("created_at", str),
              ("login_token_hash", str), ("theme", str)],
    "progress": [("user_id", str), ("season_id", str), ("minutes", int), ("plan", str), ("current_ep", int),
                 ("last_completed_ep", int), ("last_end_pos", str), ("last_completed_at", str), ("started_at", str),
                 ("restart_count", int)],
    "completions": [("user_id", str), ("season_id", str), ("ep_index", int), ("start_pos", str), ("end_pos", str),
                    ("est_min", int), ("completed_at", str)],
    "lines": [("user_id", str), ("season_id", str), ("ep_index", int), ("text", str), ("updated_at", str)],
    "predictions": [("user_id", str), ("season_id", str), ("ep_index", int), ("choice", int), ("is_correct", bool),
                    ("created_at", str)],
    "gifts": [("user_id", str), ("season_id", str), ("ep_index", int), ("kind", str), ("letter_text", str),
              ("gift_item", str), ("created_at", str), ("delivered_at", str)],
    "events": [("ts", str), ("user_id", str), ("event", str), ("season_id", str), ("ep_index", int), ("meta", str)],
}


def _decode(value: str, kind: type):
    if kind is int:
        return int(value) if str(value).strip() not in ("", "None") else None
    if kind is bool:
        return str(value).strip().upper() in ("TRUE", "1")
    return "" if value is None else str(value)


def _encode(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return value


class SheetsBackend:
    def __init__(self, spreadsheet):
        """spreadsheet: gspread Spreadsheet (테스트에서는 같은 메서드를 가진 가짜 객체)."""
        self.sh = spreadsheet
        self._ensure_tabs()

    @classmethod
    def from_env(cls, sheet_id: str, service_account_json: str) -> "SheetsBackend":
        import gspread
        client = gspread.service_account_from_dict(json.loads(service_account_json))
        return cls(client.open_by_key(sheet_id))

    def _ensure_tabs(self) -> None:
        existing = {ws.title for ws in self.sh.worksheets()}
        for table, cols in SCHEMA.items():
            if table not in existing:
                ws = self.sh.add_worksheet(title=table, rows=100, cols=len(cols))
                ws.update(values=[[c for c, _ in cols]], range_name="A1", value_input_option="RAW")

    def load(self) -> dict:
        tables = list(SCHEMA)
        res = self.sh.values_batch_get([f"{t}!A:Z" for t in tables])
        data = {}
        for table, block in zip(tables, res.get("valueRanges", [])):
            values = block.get("values", [])
            header = values[0] if values else [c for c, _ in SCHEMA[table]]
            types = dict(SCHEMA[table])
            rows = []
            for raw in values[1:]:
                raw = raw + [""] * (len(header) - len(raw))
                rows.append({h: _decode(v, types.get(h, str)) for h, v in zip(header, raw)})
            data[table] = rows
        return data

    def save(self, data: dict, table: str) -> None:
        cols = [c for c, _ in SCHEMA[table]]
        ws = self.sh.worksheet(table)
        values = [cols] + [[_encode(r.get(c)) for c in cols] for r in data[table]]
        ws.update(values=values, range_name="A1", value_input_option="RAW")

    def append(self, table: str, row: dict) -> None:
        cols = [c for c, _ in SCHEMA[table]]
        self.sh.worksheet(table).append_row([_encode(row.get(c)) for c in cols], value_input_option="RAW")
