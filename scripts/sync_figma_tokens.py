"""피그마 변수 → tokens.json (되돌리기).

피그마 '완결각 Primitives / Semantic / Size' 변수 값을 {이름: 값} JSON으로 받아 tokens.json에 반영한다.
값 형식: "#RRGGBB"(색), 숫자(간격·라운드), "->다른/변수"(별칭).  예) {"brand/400": "#4A8CF2", "status/arrived-bg": "->action/primary"}

사용법:
  python scripts/sync_figma_tokens.py figma_vars.json --check   # 차이만 보여 줌
  python scripts/sync_figma_tokens.py figma_vars.json           # tokens.json 갱신 + build_tokens 실행

피그마에서 값을 읽어 이 JSON을 만드는 일은 Claude가 Figma MCP(use_figma)로 한다 (README '피그마 연동').
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKENS = ROOT / "tokens.json"
PRIMITIVE_GROUPS = {"gray", "brand"}
SEMANTIC_GROUPS = {"bg", "text", "line", "action", "status"}


def token_path(figma_name: str) -> tuple[str, ...]:
    parts = figma_name.split("/")
    if parts == ["focus"]:
        return ("color", "focus")
    group, name = parts
    if group in PRIMITIVE_GROUPS:
        return ("color", group, name)
    if group in SEMANTIC_GROUPS:
        return ("semantic", group, name)
    if group in ("space", "radius"):
        return (group, name)
    raise ValueError(f"모르는 피그마 변수: {figma_name}")


def token_value(figma_value) -> str:
    if isinstance(figma_value, (int, float)):
        n = int(figma_value) if float(figma_value).is_integer() else figma_value
        return f"{n}px"
    if figma_value.startswith("->"):
        return "{" + ".".join(token_path(figma_value[2:])) + "}"
    return figma_value.upper()


def diff(tokens: dict, figma: dict) -> list[tuple[tuple, str, str]]:
    changes = []
    for name, value in figma.items():
        path = token_path(name)
        node = tokens
        for p in path:
            node = node[p]
        new = token_value(value)
        if str(node["$value"]).upper() != new.upper():
            changes.append((path, node["$value"], new))
    return changes


def main() -> None:
    src, check = Path(sys.argv[1]), "--check" in sys.argv
    tokens = json.loads(TOKENS.read_text(encoding="utf-8"))
    figma = json.loads(src.read_text(encoding="utf-8"))
    changes = diff(tokens, figma)
    for path, old, new in changes:
        print(f"{'.'.join(path)}: {old} → {new}")
    print(f"차이 {len(changes)}개")
    if check or not changes:
        return
    for path, _, new in changes:
        node = tokens
        for p in path:
            node = node[p]
        node["$value"] = new
    TOKENS.write_text(json.dumps(tokens, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_tokens.py")], check=True)


if __name__ == "__main__":
    main()
