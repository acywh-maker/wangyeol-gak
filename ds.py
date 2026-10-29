"""Design-system helpers for Streamlit.

Usage:
    import ds
    ds.apply()                       # once, at the top of every page
    ds.header("독서 루틴 알림 만들기", back="?")
    ds.chips(["# 판타지", "# 로맨스", "+ 9개"])
    with st.container(key="ds-cta"):  # becomes a fixed yellow bar on mobile
        st.button("확인", type="primary", width="stretch")
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

import streamlit as st

_HERE = Path(__file__).parent
CSS_PATH = _HERE / "tokens.css"
TOKENS_PATH = _HERE / "tokens.json"


# --------------------------------------------------------------------------
# setup
# --------------------------------------------------------------------------
def apply() -> None:
    """Inject tokens.css into the page (call once per page run)."""
    st.html(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>")


def tokens() -> dict:
    """Raw tokens.json as a dict (e.g. for chart colors)."""
    return json.loads(TOKENS_PATH.read_text(encoding="utf-8"))


def _render(markup: str) -> None:
    st.html(markup)


# --------------------------------------------------------------------------
# components
# --------------------------------------------------------------------------
def header(title: str, back: str | None = None) -> None:
    """Centered top bar with optional back link (href)."""
    back_html = f'<a href="{escape(back)}" target="_self" aria-label="뒤로">&#8249;</a>' if back is not None else ""
    _render(f'<div class="ds-header">{back_html}{escape(title)}</div>')


def overline(text: str) -> None:
    _render(f'<div class="ds-overline">{escape(text)}</div>')


def chips(items: list[str]) -> None:
    inner = "".join(f'<span class="ds-chip">{escape(i)}</span>' for i in items)
    _render(f'<div class="ds-chips">{inner}</div>')


def badge(label: str, icon: str = "&#9679;", kind: str = "default") -> str:
    """Category badge. kind: default | audio | chat. Returns HTML (compose inside hero)."""
    mod = f" ds-badge--{kind}" if kind != "default" else ""
    return (f'<div class="ds-badge{mod}"><span class="ds-badge__icon">{icon}</span>'
            f'{escape(label)}</div>')


def glass_pill(label: str, value: str) -> str:
    return f'<span class="ds-glass-pill">{escape(label)} <b>{escape(value)}</b></span>'


def meta(rating: float | None, items: list[str]) -> None:
    parts = []
    if rating is not None:
        parts.append(f'<span><span class="ds-meta__star">&#9733;</span> {rating:.1f}</span>')
    for it in items:
        parts.append(f'<span class="ds-meta__sep"></span><span>{escape(it)}</span>')
    _render(f'<div class="ds-meta">{"".join(parts)}</div>')


def cover(src: str | None = None, width: int = 200, alt: str = "") -> str:
    """Book cover. Without src, renders a neutral placeholder."""
    if src:
        body = f'<img src="{escape(src)}" alt="{escape(alt)}">'
    else:
        body = (f'<div style="aspect-ratio:2/3;background:linear-gradient(160deg,#3a3a3f,#77737a);'
                f'display:grid;place-items:center;color:#fff;font-weight:700">{escape(alt or "COVER")}</div>')
    return f'<div class="ds-cover" style="width:{width}px">{body}</div>'


def detail_hero(cover_html: str, pill_html: str = "", badge_html: str = "") -> None:
    """Blurred-background hero used on the content detail page."""
    _render(f'<div class="ds-hero">{pill_html}{cover_html}{badge_html}</div>')


def sheet(inner_html: str) -> None:
    """Bottom-sheet surface (top corners rounded). Place right after detail_hero."""
    _render(f'<div class="ds-sheet">{inner_html}</div>')


def card(inner_html: str) -> None:
    _render(f'<div class="ds-card">{inner_html}</div>')


def notice(title: str, body: str, icon: str = "") -> None:
    icon_html = f'<div style="font-size:24px">{icon}</div>' if icon else ""
    _render(f'<div class="ds-notice">{icon_html}<p class="ds-notice__title">{escape(title)}</p>'
            f'<p class="ds-notice__body">{escape(body).replace(chr(10), "<br>")}</p></div>')


def bullets(items: list[str]) -> None:
    inner = "".join(f"<li>{escape(i)}</li>" for i in items)
    _render(f'<ul class="ds-bullets">{inner}</ul>')


def tabbar(items: list[tuple[str, str, str]], active: str) -> None:
    """Mobile-only bottom navigation.

    items: [(key, label, icon_html), ...]. Links set ?tab=<key>;
    read it back with st.query_params.get("tab").
    """
    links = []
    for key, label, icon in items:
        cur = ' aria-current="page"' if key == active else ""
        links.append(f'<a href="?tab={escape(key)}" target="_self"{cur}><span>{icon}</span>{escape(label)}</a>')
    _render(f'<nav class="ds-tabbar">{"".join(links)}</nav>')
