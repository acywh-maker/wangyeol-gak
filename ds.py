"""완결각 디자인 시스템 도우미.

Usage:
    import ds
    ds.apply()                       # 페이지마다 맨 위에서 1번 (tokens.css + components.css)
    ds.chips(["# 마케팅", "+ 3개"])
    with st.container(key="ds-cta"):  # 모바일에서 하단 고정 primary 바
        st.button("확인", type="primary", width="stretch")

토큰 값은 tokens.json에서 고치고 `python scripts/build_tokens.py`를 실행한다.
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

import streamlit as st

_HERE = Path(__file__).parent
CSS_PATHS = (_HERE / "tokens.css", _HERE / "components.css")
TOKENS_PATH = _HERE / "tokens.json"


# --------------------------------------------------------------------------
# setup
# --------------------------------------------------------------------------
def apply() -> None:
    """tokens.css + components.css를 페이지에 넣는다 (매 실행 맨 위에서 1번)."""
    css = "\n".join(p.read_text(encoding="utf-8") for p in CSS_PATHS)
    st.html(f"<style>{css}</style>")


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


def card(inner_html: str) -> None:
    _render(f'<div class="ds-card">{inner_html}</div>')


def notice(title: str, body: str, icon: str = "") -> None:
    icon_html = f'<div style="font-size:24px">{icon}</div>' if icon else ""
    _render(f'<div class="ds-notice">{icon_html}<p class="ds-notice__title">{escape(title)}</p>'
            f'<p class="ds-notice__body">{escape(body).replace(chr(10), "<br>")}</p></div>')


def bullets(items: list[str]) -> None:
    inner = "".join(f"<li>{escape(i)}</li>" for i in items)
    _render(f'<ul class="ds-bullets">{inner}</ul>')
