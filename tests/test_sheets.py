"""구글 시트 백엔드 — 가짜 시트로 읽기/쓰기, 타입 복원, 수식 차단(RAW) 확인."""
from wangyeol import auth, sheets, store


class FakeWorksheet:
    def __init__(self, title):
        self.title, self.values, self.calls = title, [], []

    def update(self, values, range_name, value_input_option):
        self.calls.append(value_input_option)
        self.values = [list(map(str, r)) for r in values]

    def append_row(self, row, value_input_option):
        self.calls.append(value_input_option)
        self.values.append(list(map(str, row)))


class FakeSpreadsheet:
    def __init__(self):
        self.tabs = {}

    def worksheets(self):
        return list(self.tabs.values())

    def add_worksheet(self, title, rows, cols):
        self.tabs[title] = FakeWorksheet(title)
        return self.tabs[title]

    def worksheet(self, title):
        return self.tabs[title]

    def values_batch_get(self, ranges):
        return {"valueRanges": [{"values": self.tabs[r.split("!")[0]].values} for r in ranges]}


NOW = "2026-10-29T21:00:00+09:00"


def test_sheets_roundtrip_types_and_raw():
    fake = FakeSpreadsheet()
    store.set_backend(sheets.SheetsBackend(fake))
    assert set(fake.tabs) == set(sheets.SCHEMA)  # 탭과 머리글 자동 생성

    user, _, _ = auth.enter("시트", "1357", NOW)
    store.add_completion(user["user_id"], "s1", 1, (0, 0), (3, 0), 10, NOW)
    store.save_prediction(user["user_id"], "s1", 1, 1, True, NOW)
    store.save_line(user["user_id"], "s1", 1, "=HYPERLINK(\"x\")", NOW)
    store.log_event(NOW, user["user_id"], "ep_complete", "s1", 1, {"est_min": 10})

    store.reset_cache()  # 다음 요청처럼 시트에서 다시 읽기
    assert store.completed_indexes(user["user_id"], "s1") == {1}  # int로 복원
    p = store.get_prediction(user["user_id"], "s1", 1)
    assert p["choice"] == 1 and p["is_correct"] is True
    assert store.get_line(user["user_id"], "s1", 1).startswith("=HYPERLINK")  # 글자 그대로
    assert all(c == "RAW" for ws in fake.tabs.values() for c in ws.calls)  # 수식으로 실행 안 됨
    assert len(fake.tabs["events"].values) == 2  # 머리글 + 한 줄 덧붙임
    assert auth.enter("시트", "0000", NOW)[1] == "PIN이 맞지 않아요"
