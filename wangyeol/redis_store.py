"""Upstash Redis 저장 백엔드 (Vercel 마켓플레이스 연동). REST API라 추가 패키지가 필요 없다.

- 탭마다 해시 1개(wg:<탭>), 행마다 필드 1개(키 = 그 행을 구분하는 값들). 행 단위로 저장해서
  두 사람이 동시에 저장해도 서로의 기록을 덮어쓰지 않는다.
- events는 계속 늘어나는 목록(wg:events)에 한 줄씩 덧붙인다.
- 연결 정보: Vercel이 넣어 주는 KV_REST_API_URL/KV_REST_API_TOKEN
  (또는 UPSTASH_REDIS_REST_URL/UPSTASH_REDIS_REST_TOKEN)
"""
from __future__ import annotations

import json
from typing import Callable

import requests

PREFIX = "wg:"
# 행을 구분하는 컬럼 (store.py의 upsert 키와 같다)
ROW_KEYS = {
    "users": ("user_id",),
    "progress": ("user_id", "season_id"),
    "completions": ("user_id", "season_id", "ep_index"),
    "lines": ("user_id", "season_id", "ep_index"),
    "predictions": ("user_id", "season_id", "ep_index"),
    "gifts": ("user_id", "season_id", "ep_index"),
}
LIST_TABLES = ("events",)


def row_key(table: str, row: dict) -> str:
    return "|".join(str(row.get(c, "")) for c in ROW_KEYS[table])


class RedisBackend:
    def __init__(self, pipeline: Callable[[list[list]], list]):
        """pipeline: [[명령, 인자…], …] → 결과 목록. (테스트에서는 가짜 함수)"""
        self.pipeline = pipeline

    @classmethod
    def from_env(cls, url: str, token: str) -> "RedisBackend":
        session = requests.Session()
        session.headers["Authorization"] = f"Bearer {token}"

        def pipeline(commands: list[list]) -> list:
            r = session.post(f"{url.rstrip('/')}/pipeline", json=commands, timeout=10)
            r.raise_for_status()
            out = []
            for item in r.json():
                if "error" in item:
                    raise RuntimeError(item["error"])
                out.append(item.get("result"))
            return out

        return cls(pipeline)

    def load(self) -> dict:
        tables = list(ROW_KEYS)
        cmds = [["HGETALL", PREFIX + t] for t in tables] + [["LRANGE", PREFIX + t, 0, -1] for t in LIST_TABLES]
        results = self.pipeline(cmds)
        data = {}
        for t, res in zip(tables, results[:len(tables)]):
            # HGETALL 결과: [필드, 값, 필드, 값, …]
            values = (res or [])[1::2]
            data[t] = [json.loads(v) for v in values]
        for t, res in zip(LIST_TABLES, results[len(tables):]):
            data[t] = [json.loads(v) for v in (res or [])]
        return data

    def put(self, table: str, row: dict) -> None:
        self.pipeline([["HSET", PREFIX + table, row_key(table, row), json.dumps(row, ensure_ascii=False)]])

    def save(self, data: dict, table: str) -> None:
        """행 단위 저장이 안 되는 경로(예비): 탭 전체를 다시 쓴다."""
        if table in LIST_TABLES:
            return
        cmds = [["DEL", PREFIX + table]]
        for row in data[table]:
            cmds.append(["HSET", PREFIX + table, row_key(table, row), json.dumps(row, ensure_ascii=False)])
        self.pipeline(cmds)

    def append(self, table: str, row: dict) -> None:
        if table not in LIST_TABLES:  # users처럼 새 행을 덧붙이는 탭도 해시에 행으로 저장
            return self.put(table, row)
        self.pipeline([["RPUSH", PREFIX + table, json.dumps(row, ensure_ascii=False)]])
