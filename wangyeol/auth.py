"""입장(FR-001): PIN 해시, 로그인 유지 토큰, 쿠키."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets

import streamlit as st

from . import store

COOKIE = "wg_login"
COOKIE_DAYS = 30
_NICK_RE = re.compile(r"^[^,]{2,12}$")


def validate(nickname: str, pin: str) -> str | None:
    """문제가 있으면 안내 문구, 없으면 None."""
    if not _NICK_RE.match(nickname or ""):
        return "닉네임은 2~12자로, 쉼표 없이 써 주세요"
    if not re.fullmatch(r"\d{4}", pin or ""):
        return "PIN은 숫자 4자리예요"
    return None


def _hash_pin(pin: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt), 100_000).hex()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def enter(nickname: str, pin: str, now: str) -> tuple[dict | None, str | None, bool]:
    """(사용자, 오류 문구, 새로 가입했는지). 같은 닉네임 + PIN 불일치면 새 계정을 만들지 않는다."""
    nickname = nickname.strip()
    user = store.get_user(nickname)
    if user:
        if not hmac.compare_digest(_hash_pin(pin, user["salt"]), user["pin_hash"]):
            return None, "PIN이 맞지 않아요", False
        return user, None, False
    salt = secrets.token_hex(16)
    return store.create_user(nickname, _hash_pin(pin, salt), salt, now), None, True


def issue_token(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    store.set_login_token(user_id, _hash_token(token))
    return token


def user_from_cookie() -> dict | None:
    try:
        token = st.context.cookies.get(COOKIE)
    except Exception:  # 테스트 환경 등 쿠키를 읽을 수 없으면 PIN 입력으로
        return None
    return store.get_user_by_token_hash(_hash_token(token)) if isinstance(token, str) and token else None


def write_cookie(token: str | None) -> None:
    """브라우저 쿠키 저장/삭제. st.iframe의 HTML은 앱과 같은 출처라 document.cookie가 앱에 적용된다.
    넣는 값은 앱이 만든 토큰뿐이다(사용자 입력 아님)."""
    value = json.dumps(token or "")
    age = COOKIE_DAYS * 86400 if token else 0
    with st.container(key="wg-cookie"):
        st.iframe(
            f"<script>document.cookie = '{COOKIE}=' + encodeURIComponent({value}) + "
            f"'; max-age={age}; path=/; SameSite=Lax';</script>",
            height=1,
        )


def logout(user_id: str) -> None:
    store.set_login_token(user_id, "")
