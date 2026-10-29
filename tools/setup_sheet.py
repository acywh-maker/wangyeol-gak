"""구글 시트 연결 도우미 — 서비스 계정 키(JSON)와 시트 주소를 .env에 넣고 연결을 확인한다.

사용법 (키 내용을 채팅에 붙이지 않아도 된다):
  python tools/setup_sheet.py "C:/Users/user/Downloads/키파일.json" "https://docs.google.com/spreadsheets/d/.../edit"

하는 일:
  1. 키 파일을 읽어 .env의 GCP_SERVICE_ACCOUNT_JSON(한 줄), SHEET_ID를 채운다 (값은 화면에 출력하지 않음)
  2. 시트를 열어 7개 탭(users, progress, …)과 머리글을 만든다
  3. 서비스 계정 이메일을 보여 준다 — 시트가 이 이메일에 공유되지 않았으면 알려 준다
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / ".env"


def sheet_id_from(url_or_id: str) -> str:
    m = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]+)", url_or_id)
    return m.group(1) if m else url_or_id.strip()


def write_env(values: dict) -> None:
    lines = ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []
    seen = set()
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key in values:
            lines[i] = f"{key}={values[key]}"
            seen.add(key)
    lines += [f"{k}={v}" for k, v in values.items() if k not in seen]
    ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    key_path, sheet = Path(sys.argv[1].strip('"')), sys.argv[2]
    try:
        key = json.loads(key_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        sys.exit(f"키 파일을 읽지 못했어요: {e}")
    if key.get("type") != "service_account" or "client_email" not in key:
        sys.exit("서비스 계정 키(JSON)가 아니에요. 구글 클라우드 → 서비스 계정 → 키 → JSON으로 받은 파일인지 확인해 주세요.")
    if ROOT in key_path.resolve().parents:
        print("⚠ 키 파일이 프로젝트 폴더 안에 있어요. git에 올라가지 않게 다운로드 폴더 등 바깥에 두세요.")

    sid = sheet_id_from(sheet)
    write_env({"SHEET_ID": sid, "GCP_SERVICE_ACCOUNT_JSON": json.dumps(key, separators=(",", ":"))})
    print(f"✓ .env에 SHEET_ID와 서비스 계정 키를 저장했어요 (.env는 git에 올라가지 않아요)")
    print(f"  서비스 계정 이메일: {key['client_email']}")

    sys.path.insert(0, str(ROOT))
    try:
        from wangyeol.sheets import SCHEMA, SheetsBackend
        backend = SheetsBackend.from_env(sid, json.dumps(key))
        tabs = [ws.title for ws in backend.sh.worksheets()]
    except Exception as e:  # 권한·API 미사용 등
        msg = str(e)
        if "403" in msg or "PERMISSION" in msg.upper():
            sys.exit(f"✗ 시트를 열 권한이 없어요. 시트 [공유]에 위 이메일을 '편집자'로 추가했는지, "
                     f"구글 클라우드에서 'Google Sheets API'를 사용 설정했는지 확인해 주세요.\n  ({msg[:200]})")
        if "404" in msg:
            sys.exit(f"✗ 시트를 찾지 못했어요. 시트 주소를 다시 확인해 주세요. ({msg[:200]})")
        sys.exit(f"✗ 연결 실패: {msg[:300]}")
    missing = [t for t in SCHEMA if t not in tabs]
    print(f"✓ 시트 연결 성공 — 탭: {', '.join(t for t in tabs if t in SCHEMA)}" + (f" (없는 탭: {missing})" if missing else ""))
    print("  이제 앱을 다시 시작하면 구글 시트에 저장돼요.")


if __name__ == "__main__":
    main()
