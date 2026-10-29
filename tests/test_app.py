"""Flask 화면 흐름: 가입 → 서재 → 목표 → 시즌 홈 → 회차 → 예측·한 줄 → 완료, 테마 저장."""
import pytest

import app as webapp
from wangyeol import notion, parser, store

from helpers import blk, para_minutes, rt

ROW = {"id": "s1", "title": "테스트 시즌", "url": "https://notion.so/s1", "owner": None}


@pytest.fixture
def client(tmp_path, monkeypatch):
    store.set_path(tmp_path / "store.json")
    blocks = [
        blk("heading_2", "1. 시작"), blk("callout", "요약 문장"), para_minutes(9),
        blk("quote", "다음은?"), blk("bulleted_list_item", rt("A", True)), blk("bulleted_list_item", "B"),
        blk("heading_2", "2. 다음"), para_minutes(9),
        blk("heading_2", "3. 끝"), para_minutes(9),
    ]
    season = parser.parse_season("s1", ROW["title"], ROW["url"], None, blocks)
    monkeypatch.setattr(notion, "seasons_for", lambda nick: [ROW])
    monkeypatch.setattr(notion, "load_season", lambda row: season)
    webapp.app.config["TESTING"] = True
    return webapp.app.test_client()


def signup(c, nick="테스터", pin="1234"):
    return c.post("/enter", data={"nickname": nick, "pin": pin})


def test_requires_login(client):
    assert client.get("/").headers["Location"].endswith("/enter")


def test_full_flow(client):
    r = signup(client)
    assert r.status_code == 302 and "wg_login" in r.headers.get("Set-Cookie", "")
    page = client.get("/").get_data(as_text=True)
    assert "테스터님의 서재" in page and "새 시즌" in page

    # 처음 들어가면 S6
    assert client.get("/s/s1").headers["Location"].endswith("/s/s1/goal")
    assert "선물도 골라봐요" in client.get("/s/s1/goal").get_data(as_text=True)
    r = client.post("/s/s1/goal", data={"action": "save", "minutes": "10", "final_kind": "letter_final", "letter_final": "축하해"})
    assert r.headers["Location"].endswith("/s/s1")
    home = client.get("/s/s1").get_data(as_text=True)
    assert "하루 10분 · 0/3화" in home and "첫 화 보기" in home

    ep = client.get("/s/s1/ep/1").get_data(as_text=True)
    assert "1. 시작" in ep and "요약 문장" in ep and "다음 화에서 공개" in ep
    client.post("/s/s1/ep/1/predict", data={"choice": "0"}, headers={"X-Requested-With": "fetch"})
    r = client.post("/s/s1/ep/1/done", data={"line": "재밌다"})
    assert "/s/s1/done/1" in r.headers["Location"]
    client.post("/s/s1/ep/1/done", data={"line": "재밌다"})  # 연타
    uid = store.get_user("테스터")["user_id"]
    assert store.completed_indexes(uid, "s1") == {1}
    assert store.get_line(uid, "s1", 1) == "재밌다"
    assert "오늘 몫 끝!" in client.get("/s/s1/done/1").get_data(as_text=True)

    # 다음 화 맨 위에 지난 화 예측 결과
    ep2 = client.get("/s/s1/ep/2").get_data(as_text=True)
    assert "A를 골랐어요 → 정답이에요!" in ep2 and "재밌다" in ep2
    # 마지막 화에는 예측 없음
    assert "다음 화에서 공개" not in client.get("/s/s1/ep/3").get_data(as_text=True)


def test_wrong_pin_and_theme(client):
    signup(client)
    client.post("/logout")
    r = client.post("/enter", data={"nickname": "테스터", "pin": "9999"})
    assert "PIN이 맞지 않아요" in r.get_data(as_text=True)
    signup(client)
    assert 'data-theme="dark"' in client.get("/").get_data(as_text=True)  # 다크 기본
    client.post("/theme", data={"next": "/"})
    assert 'data-theme="light"' in client.get("/").get_data(as_text=True)


def test_text_is_escaped(client):
    signup(client, nick="<b>해커</b>")
    page = client.get("/").get_data(as_text=True)
    assert "<b>해커</b>" not in page and "&lt;b&gt;해커&lt;/b&gt;" in page
