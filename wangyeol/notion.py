"""노션 API 접근 (FR-002). 응답은 메모리에 30분 캐시(NFR-006). 서버리스에서는 인스턴스가 살아 있는 동안만 유지되고,
시즌 화면은 Vercel CDN 캐시(Cache-Control)가 한 번 더 받쳐 준다."""
from __future__ import annotations

import html
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import functools
import threading
import time

import requests

from . import config, parser

API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
CACHE_TTL = 60 * 30
OWNER_PROPERTY = "닉네임"
# 하위 블록을 따라 내려갈 블록 종류 (표·하위 페이지 등 미지원 블록은 내려가지 않음)
_NESTABLE = {
    "toggle", "bulleted_list_item", "numbered_list_item", "callout", "quote", "paragraph",
    "heading_1", "heading_2", "heading_3", "column_list", "column", "synced_block", "to_do",
}
_MAX_DEPTH = 3


class NotionError(Exception):
    pass


def ttl_cache(seconds: int):
    """인자별 결과를 seconds 동안 기억한다. 실패(예외)는 기억하지 않는다. fn.clear(*args)로 비운다."""
    def deco(fn):
        store: dict = {}
        lock = threading.Lock()

        @functools.wraps(fn)
        def wrapper(*args):
            now = time.time()
            with lock:
                hit = store.get(args)
                if hit and now - hit[0] < seconds:
                    return hit[1]
            value = fn(*args)
            with lock:
                store[args] = (now, value)
            return value

        def clear(*args):
            with lock:
                if args:
                    store.pop(args, None)
                else:
                    store.clear()

        wrapper.clear = clear
        return wrapper
    return deco


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {config.get('NOTION_TOKEN')}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    })
    return s


def _request(s: requests.Session, method: str, path: str, **kwargs) -> dict:
    try:
        r = s.request(method, f"{API}/{path}", timeout=20, **kwargs)
    except requests.RequestException as e:
        raise NotionError(str(e)) from e
    if r.status_code != 200:
        raise NotionError(f"{r.status_code}: {r.json().get('message', '') if r.content else ''}")
    return r.json()


def _children(s: requests.Session, block_id: str, depth: int = 0) -> list:
    blocks, cursor = [], None
    while True:
        params = {"page_size": 100, **({"start_cursor": cursor} if cursor else {})}
        data = _request(s, "GET", f"blocks/{block_id}/children", params=params)
        blocks += data["results"]
        if not data.get("has_more"):
            break
        cursor = data["next_cursor"]
    if depth < _MAX_DEPTH:
        for b in blocks:
            if b.get("has_children") and b["type"] in _NESTABLE:
                b["children"] = _children(s, b["id"], depth + 1)
    return blocks


def _normalize(name: str | None) -> str:
    return re.sub(r"\s+", "", name or "")


def _owner_of(page: dict) -> str | None:
    """'닉네임' 선택 속성 우선, 없으면 첫 번째 선택 속성. 비어 있으면 None(모두에게 공개)."""
    props = page.get("properties", {})
    prop = props.get(OWNER_PROPERTY)
    if not prop or prop.get("type") != "select":
        prop = next((p for p in props.values() if p.get("type") == "select"), None)
    sel = (prop or {}).get("select")
    return sel["name"] if sel else None


def _title_of(page: dict) -> str:
    for p in page.get("properties", {}).values():
        if p.get("type") == "title":
            return parser.plain(p["title"]).strip() or "제목 없음"
    return "제목 없음"


@ttl_cache(CACHE_TTL)
def list_seasons() -> list[dict]:
    """루트 페이지 안 첫 번째 인라인 데이터베이스의 행 목록."""
    s = _session()
    root = config.get("NOTION_ROOT_PAGE_ID")
    db = next((b["id"] for b in _children(s, root, _MAX_DEPTH) if b["type"] == "child_database"), None)
    if not db:
        raise NotionError("루트 페이지에 데이터베이스가 없어요")
    rows, cursor = [], None
    while True:
        body = {"page_size": 100, **({"start_cursor": cursor} if cursor else {})}
        data = _request(s, "POST", f"databases/{db}/query", json=body)
        rows += data["results"]
        if not data.get("has_more"):
            break
        cursor = data["next_cursor"]
    return [
        {"id": r["id"], "title": _title_of(r), "url": r["url"], "owner": _owner_of(r)}
        for r in rows if not r.get("archived") and not r.get("in_trash")
    ]


def seasons_for(nickname: str) -> list[dict]:
    me = _normalize(nickname)
    return [row for row in list_seasons() if row["owner"] is None or _normalize(row["owner"]) == me]


@ttl_cache(CACHE_TTL)
def _season_blocks(page_id: str) -> list:
    return _children(_session(), page_id)


@ttl_cache(60 * 60 * 24 * 7)
def youtube_info(video_id: str) -> dict | None:
    """유튜브 영상 길이(초)와 제목. watch 페이지를 읽는다(키 불필요). 실패하면 None."""
    try:
        r = requests.get(
            f"https://www.youtube.com/watch?v={video_id}", timeout=5,
            headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "ko-KR,ko;q=0.9"},
        )
    except requests.RequestException:
        return None
    length = re.search(r'"lengthSeconds":"(\d+)"', r.text)
    title = re.search(r'<meta name="title" content="([^"]*)"', r.text)
    if not length:
        return None
    return {"seconds": int(length.group(1)), "title": html.unescape(title.group(1)) if title else ""}


def _youtube_ids(blocks: list) -> set[str]:
    ids = set()
    for b in blocks:
        if b["type"] in ("video", "embed"):
            vid = parser.youtube_id(parser.media_url(b) or "")
            if vid:
                ids.add(vid)
        ids |= _youtube_ids(b.get("children", []))
    return ids


def load_season(row: dict) -> parser.Season:
    blocks = _season_blocks(row["id"])
    expiry = parser.earliest_expiry(blocks)
    # 이미지 URL이 곧 만료되면 캐시를 비우고 1회 재요청 (13장)
    if expiry and datetime.fromisoformat(expiry.replace("Z", "+00:00")) < datetime.now(timezone.utc) + timedelta(minutes=5):
        _season_blocks.clear(row["id"])
        blocks = _season_blocks(row["id"])
    ids = sorted(_youtube_ids(blocks))
    with ThreadPoolExecutor(max_workers=8) as pool:
        infos = dict(zip(ids, pool.map(youtube_info, ids)))
    return parser.parse_season(row["id"], row["title"], row["url"], row["owner"], blocks, infos.get)


def clear_cache() -> None:
    list_seasons.clear()
    _season_blocks.clear()
