"""Upstash Redis 백엔드 — 가짜 Redis로 행 단위 저장과 동시 저장 안전성 확인."""
from wangyeol import auth, store
from wangyeol.redis_store import RedisBackend


class FakeRedis:
    def __init__(self):
        self.h, self.l, self.calls = {}, {}, []

    def pipeline(self, cmds):
        out = []
        for c in cmds:
            op, key, *args = c
            self.calls.append(op)
            if op == "HSET":
                self.h.setdefault(key, {})[args[0]] = args[1]; out.append(1)
            elif op == "HGETALL":
                out.append([x for kv in self.h.get(key, {}).items() for x in kv])
            elif op == "RPUSH":
                self.l.setdefault(key, []).append(args[0]); out.append(len(self.l[key]))
            elif op == "LRANGE":
                out.append(list(self.l.get(key, [])))
            elif op == "DEL":
                self.h.pop(key, None); out.append(1)
        return out


NOW = "2026-10-29T21:00:00+09:00"


def test_redis_roundtrip_and_row_level_writes():
    fake = FakeRedis()
    store.set_backend(RedisBackend(fake.pipeline))
    user, _, _ = auth.enter("레디스", "2468", NOW)
    store.add_completion(user["user_id"], "s1", 1, (0, 0), (3, 0), 10, NOW)
    store.save_prediction(user["user_id"], "s1", 1, 0, True, NOW)
    store.log_event(NOW, user["user_id"], "ep_complete", "s1", 1)
    assert "DEL" not in fake.calls  # 탭 전체 다시 쓰기 없음 (행 단위)

    # 다른 요청(다른 사용자)이 그 사이에 저장해도 서로 덮어쓰지 않는다
    other = RedisBackend(fake.pipeline)
    store.set_backend(other)
    u2, _, _ = auth.enter("다른사람", "1111", NOW)
    store.add_completion(u2["user_id"], "s1", 1, (0, 0), (3, 0), 10, NOW)

    store.reset_cache()
    assert store.completed_indexes(user["user_id"], "s1") == {1}
    assert store.completed_indexes(u2["user_id"], "s1") == {1}
    assert store.get_prediction(user["user_id"], "s1", 1)["is_correct"] is True
    assert len(store.table("events")) == 1
    assert auth.enter("레디스", "0000", NOW)[1] == "PIN이 맞지 않아요"
