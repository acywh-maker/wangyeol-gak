"""설정값: 환경변수(배포 = Vercel 환경변수) → 없으면 프로젝트 루트의 .env(로컬 개발)."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()


def get(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def dev_mode() -> bool:
    return get("DEV_MODE") in ("1", "true", "True")
