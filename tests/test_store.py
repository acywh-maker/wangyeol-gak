import pytest

from wangyeol import auth, store


@pytest.fixture(autouse=True)
def tmp_store(tmp_path):
    store.set_path(tmp_path / "store.json")


NOW = "2026-10-29T21:00:00+09:00"


def test_signup_then_login_and_wrong_pin():
    user, err, new = auth.enter("돋이", "1234", NOW)
    assert user and err is None and new
    again, err, new = auth.enter("돋이", "1234", NOW)
    assert again["user_id"] == user["user_id"] and not new
    bad, err, _ = auth.enter("돋이", "9999", NOW)
    assert bad is None and err == "PIN이 맞지 않아요"
    assert len(store._rows("users")) == 1  # 새 계정 안 만듦
    assert store.get_user("돋이")["pin_hash"] != "1234"  # 평문 저장 금지


def test_validate():
    assert auth.validate("돋", "1234")
    assert auth.validate("돋,이", "1234")
    assert auth.validate("돋이", "12a4")
    assert auth.validate("돋이", "1234") is None


def test_login_token_roundtrip():
    user, _, _ = auth.enter("민지", "0000", NOW)
    token = auth.issue_token(user["user_id"])
    assert store.get_user_by_token_hash(auth._hash_token(token))["nickname"] == "민지"
    auth.logout(user["user_id"])
    assert store.get_user_by_token_hash(auth._hash_token(token)) is None


def test_completion_once_and_unique_total():
    assert store.add_completion("u", "s1", 1, (0, 0), (3, 0), 10, NOW)
    assert not store.add_completion("u", "s1", 1, (0, 0), (3, 0), 10, NOW)  # 연타
    store.add_completion("u", "s2", 1, (0, 0), (2, 0), 10, NOW)
    assert store.total_completed("u") == 2
    assert store.completed_indexes("u", "s1") == {1}


def test_progress_plan_roundtrip_and_prediction_overwrite():
    store.save_progress("u", "s1", minutes=30, plan=[(0, 0.0), (3, 660.0)], current_ep=1)
    p = store.get_progress("u", "s1")
    assert p["minutes"] == 30 and p["plan"] == [[0, 0.0], [3, 660.0]]
    store.save_prediction("u", "s1", 1, 0, False, NOW)
    store.save_prediction("u", "s1", 1, 1, True, NOW)
    assert store.get_prediction("u", "s1", 1)["choice"] == 1
    assert len(store._rows("predictions")) == 1
