"""노션 블록 → HTML (FR-004 5번 본문). 모든 글자는 이스케이프하고, 링크는 http(s)·mailto만 허용한다."""
from __future__ import annotations

from html import escape

from .parser import fmt_clock, media_url, plain, rich_text_of

_LIST_TYPES = {"bulleted_list_item": "ul", "numbered_list_item": "ol"}


def _safe_href(href: str | None) -> str | None:
    return href if href and href.startswith(("http://", "https://", "mailto:")) else None


def rich(rich_text: list | None) -> str:
    """노션 rich_text → 인라인 HTML (굵게·기울임·취소선·코드·링크)."""
    out = []
    for rt in rich_text or []:
        text = rt.get("plain_text", "")
        if not text:
            continue
        a = rt.get("annotations", {})
        body = escape(text).replace("\n", "<br>")
        if a.get("code"):
            body = f"<code>{body}</code>"
        if a.get("bold"):
            body = f"<strong>{body}</strong>"
        if a.get("italic"):
            body = f"<em>{body}</em>"
        if a.get("strikethrough"):
            body = f"<s>{body}</s>"
        href = _safe_href(rt.get("href"))
        if href:
            body = f'<a href="{escape(href)}" target="_blank" rel="noopener">{body}</a>'
        out.append(body)
    return "".join(out)


def youtube_iframe(video_id: str, start: float = 0, end: float | None = None) -> str:
    params = ["rel=0", "playsinline=1"]
    if start:
        params.append(f"start={int(start)}")
    if end:
        params.append(f"end={int(end)}")
    src = f"https://www.youtube-nocookie.com/embed/{escape(video_id)}?{'&amp;'.join(params)}"
    return (f'<div class="video"><iframe src="{src}" title="YouTube" loading="lazy" '
            f'allow="encrypted-media; picture-in-picture" allowfullscreen></iframe></div>')


def blocks_html(blocks: list) -> str:
    parts, i = [], 0
    while i < len(blocks):
        b = blocks[i]
        tag = _LIST_TYPES.get(b["type"])
        if tag:
            run = []
            while i < len(blocks) and blocks[i]["type"] == b["type"]:
                run.append(blocks[i])
                i += 1
            items = "".join(f"<li>{rich(rich_text_of(x))}{blocks_html(x.get('children', []))}</li>" for x in run)
            parts.append(f"<{tag}>{items}</{tag}>")
            continue
        parts.append(block_html(b))
        i += 1
    return "".join(p for p in parts if p)


def block_html(b: dict) -> str:
    t = b["type"]
    data = b.get(t, {}) if isinstance(b.get(t), dict) else {}
    kids = blocks_html(b.get("children", []))
    text = rich(rich_text_of(b))

    if t == "paragraph":
        return (f"<p>{text}</p>" if text.strip() else "") + kids
    if t in ("heading_1", "heading_2", "heading_3"):
        tag = "h4" if t == "heading_3" else "h3"
        if data.get("is_toggleable"):
            return f"<details><summary>{text}</summary>{kids}</details>"
        return f"<{tag}>{text}</{tag}>"
    if t == "quote":
        return f"<blockquote>{text}{kids}</blockquote>"
    if t == "callout":
        icon = data.get("icon") or {}
        emoji = escape(icon.get("emoji", "")) if icon.get("type") == "emoji" else ""
        return f'<div class="callout">{f"<span>{emoji}</span>" if emoji else ""}<div>{text}{kids}</div></div>'
    if t == "to_do":
        return f"<p>{'☑' if data.get('checked') else '☐'} {text}</p>{kids}"
    if t == "toggle":
        return f"<details><summary>{text or ' '}</summary>{kids}</details>"
    if t == "divider":
        return "<hr>"
    if t == "image":
        url = media_url(b)
        if not url:
            return ""
        cap = escape(plain(data.get("caption")))
        return (f'<figure><img src="{escape(url)}" alt="{cap}" loading="lazy">'
                f'{f"<figcaption>{cap}</figcaption>" if cap else ""}</figure>')
    if t in ("video", "embed"):
        yt = b.get("_yt")
        if yt:
            start, end = yt["range"] or (0, None)
            return youtube_iframe(yt["id"], start, end)
        url = _safe_href(media_url(b))
        if t == "video" and url:
            return f'<video src="{escape(url)}" controls preload="metadata"></video>'
        if url:
            return f'<p><a href="{escape(url)}" target="_blank" rel="noopener">🔗 {escape(plain(data.get("caption")) or url)}</a></p>'
        return ""
    if t == "bookmark":
        url = _safe_href(data.get("url"))
        return f'<p><a href="{escape(url)}" target="_blank" rel="noopener">🔗 {escape(plain(data.get("caption")) or url)}</a></p>' if url else ""
    if t in ("column_list", "column", "synced_block"):
        return kids
    return ""  # 그 외 블록(표, 코드, 하위 페이지 등)은 건너뜀 (FR-004)


def segment_html(units: list, seg) -> str:
    """회차의 한 구간. 영상·강의는 이번 회차에 볼 범위만, 글은 블록 그대로."""
    u = units[seg.unit]
    if u.kind == "video":
        base = (u.youtube["range"] or (0, None))[0]
        whole_end = u.youtube["range"] is None and seg.end >= u.seconds
        return youtube_iframe(u.youtube["id"], base + seg.start, None if whole_end else base + seg.end)
    if u.kind == "lecture":
        partial = seg.start > 0 or seg.end < u.seconds
        if partial:
            span = (f"{'처음' if seg.start == 0 else fmt_clock(seg.start)} ~ "
                    f"{'끝' if seg.end >= u.seconds else fmt_clock(seg.end) + ' 지점까지'}")
        else:
            span = f"전체 {fmt_clock(u.seconds)}"
        return (f'<div class="lecture"><div class="lecture__title">{escape(u.title)}</div>'
                f'<div class="lecture__span">{span}</div></div>')
    return blocks_html(u.blocks)
