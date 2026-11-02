import pytest

from wangyeol import notion


class FakeResponse:
    def __init__(self, status, headers=None):
        self.status_code, self.headers, self.content = status, headers or {}, b"{}"

    def json(self):
        return {"ok": True} if self.status_code == 200 else {"message": "rate limited"}


class FakeSession:
    def __init__(self, statuses):
        self.statuses, self.calls = list(statuses), 0

    def request(self, *a, **k):
        self.calls += 1
        return FakeResponse(self.statuses.pop(0), {"Retry-After": "0"})


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(notion.time, "sleep", lambda s: None)


def test_429_retries_then_succeeds():
    s = FakeSession([429, 429, 200])
    assert notion._request(s, "GET", "x") == {"ok": True}
    assert s.calls == 3


def test_429_gives_up_after_three_retries():
    s = FakeSession([429] * 4)
    with pytest.raises(notion.NotionError, match="429"):
        notion._request(s, "GET", "x")
    assert s.calls == 4
