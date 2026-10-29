import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("sync", ROOT / "design" / "sync_figma_tokens.py")
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


def test_name_and_value_mapping():
    assert sync.token_path("brand/400") == ("color", "brand", "400")
    assert sync.token_path("status/arrived-bg") == ("semantic", "status", "arrived-bg")
    assert sync.token_path("radius/md") == ("radius", "md")
    assert sync.token_value("->action/primary") == "{semantic.action.primary}"
    assert sync.token_value("->gray/0") == "{color.gray.0}"
    assert sync.token_value(12) == "12px"
    assert sync.token_value("#4a8cf2") == "#4A8CF2"


def test_diff_detects_only_changes():
    tokens = json.loads((ROOT / "design" / "tokens.json").read_text(encoding="utf-8"))
    same = {"brand/400": tokens["color"]["brand"]["400"]["$value"], "action/primary": "->brand/400", "space/6": 16}
    assert sync.diff(tokens, same) == []
    changed = sync.diff(tokens, {"brand/400": "#4A8CF2"})
    assert changed == [(("color", "brand", "400"), tokens["color"]["brand"]["400"]["$value"], "#4A8CF2")]
