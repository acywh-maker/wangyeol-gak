"""design/tokens.json → static/tokens.css 변수 영역.

사용법:  python design/build_tokens.py
토큰 값은 tokens.json에서만 고친다. tokens.css에서 GENERATED 표시 사이는 손으로 고치지 않는다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKENS = ROOT / "design" / "tokens.json"
CSS = ROOT / "static" / "tokens.css"
START, END = "/* GENERATED:START (design/build_tokens.py) */", "/* GENERATED:END */"
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
        # 다크(기본 테마): <html data-theme="dark">일 때 이 값으로 덮어쓴다
        lines.append(':root[data-theme="dark"] {')
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


def main() -> None:
    data = json.loads(TOKENS.read_text(encoding="utf-8"))
    css = CSS.read_text(encoding="utf-8")
    block = f"{START}\n{build_css(data)}\n{END}"
    if START in css:
        css = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, css, flags=re.S)
    else:
        raise SystemExit("tokens.css에 GENERATED 표시가 없어요")
    CSS.write_text(css, encoding="utf-8")
    print("static/tokens.css 갱신")


if __name__ == "__main__":
    main()
