"""노션 블록을 Streamlit 화면으로 그린다 (FR-004 5번 본문)."""
from __future__ import annotations

import html
import re

import streamlit as st

from .parser import fmt_clock, media_url, plain, rich_text_of

_LIST_TYPES = {"bulleted_list_item", "numbered_list_item"}
_MD_SPECIAL = re.compile(r"([\\`*_\[\]<>#~|])")


def _escape(text: str) -> str:
    return _MD_SPECIAL.sub(r"\\\1", text)


def md(rich_text: list | None) -> str:
    """노션 rich_text → 마크다운 문자열 (굵게·기울임·취소선·코드·링크).

    강조는 `**` 대신 HTML 태그를 쓴다. `**"인용"**를`처럼 닫는 기호 뒤에 한글 조사가 붙으면
    마크다운이 굵게 처리하지 않기 때문. 따라서 결과는 unsafe_allow_html=True로 그려야 한다.
    """
    out = []
    for rt in rich_text or []:
        text = rt.get("plain_text", "")
        if not text:
            continue
        a = rt.get("annotations", {})
        body = _escape(html.escape(text, quote=False))
        if a.get("code"):
            body = f"<code>{body}</code>"
        if a.get("bold"):
            body = f"<strong>{body}</strong>"
        if a.get("italic"):
            body = f"<em>{body}</em>"
        if a.get("strikethrough"):
            body = f"<s>{body}</s>"
        href = rt.get("href") or ""
        if href.startswith(("http://", "https://", "mailto:")):
            body = f'<a href="{html.escape(href)}" target="_blank">{body}</a>'
        out.append(body)
    return "".join(out).replace("\n", "  \n")


def show(text: str) -> None:
    """md() 결과를 그린다."""
    st.markdown(text, unsafe_allow_html=True)


def _list_markdown(items: list, indent: int = 0) -> tuple[str, list]:
    """연속된 목록 블록을 하나의 마크다운으로. 목록 안의 이미지 등은 따로 돌려준다."""
    lines, leftovers = [], []
    num = 0
    pad = " " * indent
    for b in items:
        if b["type"] == "numbered_list_item":
            num += 1
            marker = f"{num}."
        else:
            marker = "-"
        lines.append(f"{pad}{marker} {md(rich_text_of(b)) or '&nbsp;'}")
        child_pad = indent + len(marker) + 1
        run: list = []
        for c in b.get("children", []) + [None]:
            if c is not None and c["type"] in _LIST_TYPES:
                run.append(c)
                continue
            if run:
                sub, extra = _list_markdown(run, child_pad)
                lines.append(sub)
                leftovers += extra
                run = []
            if c is None:
                break
            if c["type"] == "paragraph":
                lines.append(" " * child_pad + md(rich_text_of(c)))
            else:
                leftovers.append(c)
    return "\n".join(lines), leftovers


def render_blocks(blocks: list) -> None:
    i = 0
    while i < len(blocks):
        b = blocks[i]
        if b["type"] in _LIST_TYPES:
            run = []
            # 글머리와 번호 목록이 섞이면 번호가 이어지지 않도록 같은 종류끼리 묶는다
            while i < len(blocks) and blocks[i]["type"] == b["type"]:
                run.append(blocks[i])
                i += 1
            text, leftovers = _list_markdown(run)
            show(text)
            render_blocks(leftovers)
            continue
        render_block(b)
        i += 1


def render_block(b: dict) -> None:
    t = b["type"]
    data = b.get(t, {})
    children = b.get("children", [])

    if t == "paragraph":
        text = md(rich_text_of(b))
        if text.strip():
            show(text)
        render_blocks(children)
    elif t in ("heading_1", "heading_2", "heading_3"):
        level = {"heading_1": "###", "heading_2": "###", "heading_3": "####"}[t]
        if data.get("is_toggleable"):
            with st.expander(plain(rich_text_of(b)) or " "):
                render_blocks(children)
        else:
            show(f"{level} {md(rich_text_of(b))}")
    elif t == "quote":
        body = md(rich_text_of(b)).replace("  \n", "  \n> ")
        show(f"> {body}")
        render_blocks(children)
    elif t == "callout":
        icon = data.get("icon") or {}
        emoji = icon.get("emoji", "") if icon.get("type") == "emoji" else ""
        with st.container(border=True):
            show(f"{emoji} {md(rich_text_of(b))}".strip())
            render_blocks(children)
    elif t == "to_do":
        mark = "☑" if data.get("checked") else "☐"
        show(f"{mark} {md(rich_text_of(b))}")
        render_blocks(children)
    elif t == "toggle":
        with st.expander(plain(rich_text_of(b)) or " "):
            render_blocks(children)
    elif t == "divider":
        st.divider()
    elif t == "image":
        url = media_url(b)
        if url:
            st.image(url, caption=plain(data.get("caption")) or None, width="stretch")
    elif t in ("video", "embed"):
        yt = b.get("_yt")
        url = media_url(b)
        if yt:
            start, end = yt["range"] or (0, None)
            st.video(f"https://www.youtube.com/watch?v={yt['id']}", start_time=start, end_time=end)
        elif t == "video" and url:
            st.video(url)
        elif url:
            st.markdown(f"🔗 [{_escape(plain(data.get('caption')) or url)}]({url})")
    elif t == "bookmark":
        url = data.get("url")
        if url:
            st.markdown(f"🔗 [{_escape(plain(data.get('caption')) or url)}]({url})")
    elif t in ("column_list", "column", "synced_block"):
        render_blocks(children)
    # 그 외 블록(표, 코드, 하위 페이지 등)은 건너뜀 (FR-004)


def render_segment(units: list, seg) -> None:
    """회차의 한 구간. 영상·강의는 이번 회차에 볼 범위만, 글은 블록 그대로."""
    u = units[seg.unit]
    partial = seg.start > 0 or seg.end < u.seconds
    if u.kind == "video":
        base = (u.youtube["range"] or (0, None))[0]
        start, end = base + seg.start, base + seg.end
        if partial:
            label = f"{'처음' if seg.start == 0 else fmt_clock(start)} ~ {'끝' if seg.end >= u.seconds else fmt_clock(end)}"
            st.html(f'<div class="wg-range">▶ 이번 화 구간 {label}</div>')
        whole_end = u.youtube["range"] is None and seg.end >= u.seconds
        st.video(f"https://www.youtube.com/watch?v={u.youtube['id']}", start_time=int(start),
                 end_time=None if whole_end else int(end))
    elif u.kind == "lecture":
        if partial:
            span = f"{'처음' if seg.start == 0 else fmt_clock(seg.start)} ~ {'끝' if seg.end >= u.seconds else fmt_clock(seg.end) + ' 지점까지'}"
        else:
            span = f"전체 {fmt_clock(u.seconds)}"
        st.html(
            f'<div class="wg-lecture"><div class="wg-lecture__title">{html.escape(u.title)}</div>'
            f'<div class="wg-lecture__span">{span}</div></div>'
        )
    else:
        render_blocks(u.blocks)


APP_CSS = """
<style>
/* 완결각 전용 규칙 (tokens.css 뒤에 덧붙임). 읽기 앱이라 본문 폭과 글자 크기를 키운다 */
[data-testid="stMainBlockContainer"] { max-width: 720px; }
/* tokens.css의 '.stApp * { font-family }'가 아이콘 글꼴까지 덮어써서 아이콘 이름이 글자로 보이는 문제 복구 */
[data-testid="stIconMaterial"], .material-symbols-rounded { font-family: "Material Symbols Rounded" !important; }
.stMarkdown p, .stMarkdown li { font-size: var(--fs-body-lg); line-height: 1.7; color: var(--text-primary); }
.stMarkdown, .stMarkdown p, .stMarkdown li { overflow-wrap: anywhere; word-break: keep-all; }
.stMarkdown a { word-break: break-all; }
.stMarkdown blockquote { border-left: 3px solid var(--line-strong); color: var(--text-secondary); }
img, iframe, video { max-width: 100%; }

.wg-title { font-size: var(--fs-title-lg); line-height: var(--lh-title-lg); font-weight: 700; color: var(--text-strong); margin: var(--space-2) 0 var(--space-4); }
.wg-meta { font-size: var(--fs-caption); line-height: var(--lh-caption); color: var(--text-tertiary); }
.wg-label { font-size: var(--fs-caption); font-weight: 600; color: var(--text-tertiary); margin-bottom: var(--space-2); }

[class*="st-key-wg-card"] {
  background: var(--bg-default); border-radius: var(--radius-xl); box-shadow: var(--shadow-card);
  padding: var(--space-7);
}
.wg-card-title {
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
  font-size: var(--fs-title-sm); line-height: var(--lh-title-sm); font-weight: 700; color: var(--text-strong);
}
[class*="st-key-wg-summary"] { background: var(--bg-notice); border-radius: var(--radius-md); padding: var(--space-6); }
[class*="st-key-wg-box"] { border: 1px solid var(--line-default); border-radius: var(--radius-md); padding: var(--space-6); }

.wg-lecture { border: 1px solid var(--line-default); border-radius: var(--radius-md); padding: var(--space-5) var(--space-6); margin: var(--space-2) 0; }
.wg-lecture__title { font-size: var(--fs-body-lg); font-weight: 600; color: var(--text-primary); }
.wg-lecture__span { font-size: var(--fs-body-md); color: var(--text-tertiary); margin-top: var(--space-2); }
.wg-range { font-size: var(--fs-body-md); font-weight: 600; color: var(--text-secondary); margin-bottom: var(--space-2); }
</style>
"""
