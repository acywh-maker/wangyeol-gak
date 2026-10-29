import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("build_tokens", ROOT / "scripts" / "build_tokens.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def test_generated_files_up_to_date():
    """tokens.json을 고치고 생성 스크립트를 안 돌렸으면 실패."""
    data = json.loads((ROOT / "tokens.json").read_text(encoding="utf-8"))
    css = (ROOT / "tokens.css").read_text(encoding="utf-8")
    block = css.split(build.START, 1)[1].split(build.END, 1)[0].strip()
    assert block == build.build_css(data).strip()
    assert (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8") == build.build_config(data)


def test_components_use_only_semantic_tokens():
    css = (ROOT / "components.css").read_text(encoding="utf-8")
    body = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    assert not re.search(r"var\(--(gray|brand)-", body)


def test_every_var_used_is_defined():
    defined = set(re.findall(r"(--[\w-]+):", (ROOT / "tokens.css").read_text(encoding="utf-8")))
    for f in ("tokens.css", "components.css"):
        used = set(re.findall(r"var\((--[\w-]+)\)", (ROOT / f).read_text(encoding="utf-8")))
        assert used <= defined, f"{f}: 정의 안 된 변수 {sorted(used - defined)}"


def test_dark_overrides_only_existing_tokens():
    """다크는 라이트에 있는 의미 토큰만 덮어쓴다 (새 이름을 몰래 만들지 않게)."""
    data = json.loads((ROOT / "tokens.json").read_text(encoding="utf-8"))
    light = {path for path, _ in build.tokens_of(data["semantic"])}
    dark = {path for path, _ in build.tokens_of(data["dark"]["semantic"])}
    assert dark and dark <= light, sorted(dark - light)
