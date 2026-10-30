"""tokens.json → tokens.css 변수 영역 + .streamlit/config.toml 테마.

사용법:  python scripts/build_tokens.py
토큰 값은 tokens.json에서만 고친다. tokens.css에서 GENERATED 표시 사이는 손으로 고치지 않는다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKENS = ROOT / "tokens.json"
CSS = ROOT / "tokens.css"
CONFIG = ROOT / ".streamlit" / "config.toml"
START, END = "/* GENERATED:START (scripts/build_tokens.py) */", "/* GENERATED:END */"
LAYOUT_NAMES = {"gutter-desktop": "gutter", "gutter-mobile": None, "content-max": "content-max",
                "header-height": "header-h", "cta-height": "cta-h", "reading-max": "reading-max"}


def tokens_of(node: dict, path: tuple = ()):
    """($type이 있는 잎 토큰의) (경로, 토큰) 목록."""
    for k, v in node.items():
        if k.startswith("$") or not isinstance(v, dict):
            continue
        if "$value" in v:
            yield path + (k,), v
        else:
            yield from tokens_of(v, path + (k,))


def var_name(path: tuple) -> str | None:
    head = path[0]
    if head == "color":
        return "--" + "-".join(path[1:])  # gray-0, brand-400, focus, alpha-line-10
    if head == "semantic":
        return f"--{path[1]}-{path[2]}"  # bg-default, text-primary, status-arrived-bg
    if head == "font":
        return "--font-base" if path[1] == "family" else f"--fw-{path[2]}"
    if head in ("space", "radius", "shadow"):
        return f"--{head}-{path[1]}"
    if head == "motion":
        return f"--dur-{path[2]}" if path[1] == "duration" else f"--ease-{path[2]}"
    if head == "layout":
        name = LAYOUT_NAMES.get(path[1], path[1])
        return f"--{name}" if name else None
    return None


def css_value(tok: dict) -> str:
    v, t = tok["$value"], tok.get("$type")
    if isinstance(v, str) and v.startswith("{"):
        return f"var({var_name(tuple(v.strip('{}').split('.')))})"
    if t == "fontFamily":
        return ", ".join(f'"{f}"' if " " in f else f for f in v)
    if t == "cubicBezier":
        return f"cubic-bezier({', '.join(str(x) for x in v)})"
    if t == "color" and isinstance(v, str) and len(v) == 9:  # #RRGGBBAA → rgba (구형 브라우저 대비)
        r, g, b, a = (int(v[i:i + 2], 16) for i in (1, 3, 5, 7))
        return f"rgba({r},{g},{b},{a / 255:.2f})"
    return str(v)


def resolve(data: dict, tok: dict):
    """참조를 따라가 실제 값 (config.toml용)."""
    v = tok["$value"]
    while isinstance(v, str) and v.startswith("{"):
        node = data
        for part in v.strip("{}").split("."):
            node = node[part]
        v = node["$value"]
    return v


def build_css(data: dict) -> str:
    lines = [":root {"]
    group = None
    for path, tok in tokens_of(data):
        if path[0] in ("typography", "breakpoint", "mobile", "dark"):
            continue
        name = var_name(path)
        if not name:
            continue
        g = path[:2] if path[0] in ("color", "semantic") else path[:1]
        if g != group:
            lines.append(f"  /* {'.'.join(g)} */")
            group = g
        lines.append(f"  {name}: {css_value(tok)};")
    lines.append("  /* typography */")
    for name, tok in data["typography"].items():
        if name.startswith("$"):
            continue
        v = tok["$value"]
        lines.append(f"  --fs-{name}: {v['fontSize']}; --lh-{name}: {v['lineHeight']};"
                     + (f" --ls-{name}: {v['letterSpacing']};" if "letterSpacing" in v else ""))
    lines.append("}")
    dark = data.get("dark")
    if dark:
        # 다크(기본 테마): 앱이 .wg-theme-dark 표시를 넣으면 body 아래 전체가 이 값을 물려받는다
        lines.append("body:has(.wg-theme-dark) {")
        for path, tok in tokens_of(dark):
            lines.append(f"  {var_name(path)}: {css_value(tok)};")
        lines.append("  color-scheme: dark;")
        lines.append("}")
    mobile = {k: t for k, t in data.get("mobile", {}).items() if not k.startswith("$")}
    if mobile:
        lines.append("@media (max-width: 599px) {\n  :root {")
        lines += [f"    --{k}: {t['$value']};" for k, t in mobile.items()]
        lines.append("  }\n}")
    return "\n".join(lines)


def build_config(data: dict) -> str:
    def c(*path):
        node = data
        for p in path:
            node = node[p]
        return resolve(data, node)

    typo = data["typography"]
    fam = c("font", "family", "base")
    heading = [typo[n]["$value"]["fontSize"] for n in ("display", "title-lg", "title-md", "title-sm", "body-lg", "body-md")]
    semibold = data["font"]["weight"]["semibold"]["$value"]  # h5·h6는 본문 크기라 굵기로 제목임을 구분
    weights = [typo[n]["$value"]["fontWeight"] for n in ("display", "title-lg", "title-md", "title-sm")] + [semibold, semibold]
    pretendard = "https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css"
    return f"""# 자동 생성 파일 — scripts/build_tokens.py 가 tokens.json으로 만든다. 직접 고치지 말 것.

[theme]
base = "light"
primaryColor = "{c('semantic', 'action', 'primary')}"
backgroundColor = "{c('semantic', 'bg', 'default')}"
secondaryBackgroundColor = "{c('semantic', 'bg', 'surface')}"
textColor = "{c('semantic', 'text', 'primary')}"
linkColor = "{c('semantic', 'text', 'primary')}"
linkUnderline = false
borderColor = "{c('semantic', 'line', 'default')}"
dataframeBorderColor = "{c('semantic', 'line', 'default')}"
dataframeHeaderBackgroundColor = "{c('semantic', 'bg', 'subtle')}"
showWidgetBorder = true
font = "'{fam[0]}':{pretendard}, -apple-system, 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif"
headingFont = "'{fam[0]}', -apple-system, 'Apple SD Gothic Neo', sans-serif"
baseFontSize = {int(typo['body-md']['$value']['fontSize'].removesuffix('px'))}
headingFontSizes = {json.dumps(heading)}
headingFontWeights = {json.dumps(weights)}
baseRadius = "{c('radius', 'sm')}"
buttonRadius = "{c('radius', 'md')}"

[theme.sidebar]
backgroundColor = "{c('semantic', 'bg', 'subtle')}"

[client]
toolbarMode = "viewer"

[server]
"""


def main() -> None:
    data = json.loads(TOKENS.read_text(encoding="utf-8"))
    css = CSS.read_text(encoding="utf-8")
    block = f"{START}\n{build_css(data)}\n{END}"
    if START in css:
        css = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, css, flags=re.S)
    else:
        raise SystemExit("tokens.css에 GENERATED 표시가 없어요")
    CSS.write_text(css, encoding="utf-8")
    CONFIG.write_text(build_config(data), encoding="utf-8")
    print(f"tokens.css, {CONFIG.relative_to(ROOT)} 갱신")


if __name__ == "__main__":
    main()
