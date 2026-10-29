from wangyeol import parser, planner

from helpers import blk, para_minutes, rt


def season(blocks, video_info=lambda _id: None):
    return parser.parse_season("p", "시즌", "https://notion.so/p", None, blocks, video_info)


def mmss(s):
    m, sec = s.split(":")
    return int(m) * 60 + int(sec)


def summary(eps, units):
    return [[(units[s.unit].title.split(".")[0], round(s.start / 60, 1), round(s.end / 60, 1)) for s in e.segments]
            for e in eps]


def test_reproduces_example_week1_at_55min():
    """노션 '가용시간 예시' Week 1을 하루 55분으로 재현."""
    lens = ["14:10", "18:27", "17:44", "66:00", "24:14", "32:00", "39:12", "65:00"]
    s = season([blk("to_do", f"{i}. 강의 ({t})") for i, t in enumerate(lens, start=1)])
    eps = planner.plan(s, 55)
    got = summary(eps, s.units)
    assert got[0] == [("1", 0, 14.2), ("2", 0, 18.4), ("3", 0, 17.7)]          # Day 1 약 50분
    assert got[1] == [("4", 0, 55.0)]                                          # Day 2 4강 1/2
    assert got[2] == [("4", 55.0, 66.0), ("5", 0, 24.2), ("6", 0, 19.8)]       # Day 3 잔여 11분 + 5강 + 6강 약 20분
    assert got[3] == [("6", 19.8, 32.0), ("7", 0, 39.2)]                       # Day 4 6강 잔여 + 7강
    assert got[4] == [("8", 0, 55.0)]                                          # Day 5 8강 1/2
    assert got[5] == [("8", 55.0, 65.0)]
    assert [e.minutes for e in eps[:5]] == [50, 55, 55, 51, 55]


def test_heading_preferred_inside_window():
    # T=10: 허용 8.5~11.5분. 제목 경계가 9분, 일반 경계가 10분 → 제목(9분)에서 끊음
    s = season([para_minutes(5), para_minutes(4), blk("heading_2", "다음 주제"), para_minutes(1), para_minutes(5)])
    eps = planner.plan(s, 10)
    assert [seg.unit for seg in eps[0].segments] == [0, 1]
    assert eps[1].title == "다음 주제"


def test_heading_outside_window_ignored():
    # 제목이 6분(범위 밖) → 무시하고 T에 가장 가까운 문단 경계(10분)
    s = season([para_minutes(6), blk("heading_2", "주제"), para_minutes(4), para_minutes(4), para_minutes(4)])
    eps = planner.plan(s, 10)
    assert round(eps[0].seconds / 60) == 10


def test_no_heading_closest_to_target():
    s = season([para_minutes(3)] * 10)
    eps = planner.plan(s, 10)
    # 3분씩: 9분은 범위(8.5~11.5) 안, 12분은 밖 → 9분마다 끊고 마지막 3분은 그대로(25% 이상)
    assert [round(e.seconds / 60) for e in eps] == [9, 9, 9, 3]


def test_long_single_block_alone():
    s = season([para_minutes(30), para_minutes(8)])
    eps = planner.plan(s, 10)
    assert [seg.unit for seg in eps[0].segments] == [0]


def test_tiny_tail_merged():
    s = season([para_minutes(5), para_minutes(5), blk("paragraph", "마무리 한 문장")])
    eps = planner.plan(s, 10)
    assert len(eps) == 1


def test_no_piece_shorter_than_5min():
    # 8분 채운 뒤 10분 강의: 남은 2분 < 5분 → 자르지 않고 다음 회차로
    s = season([para_minutes(8), blk("to_do", "강의 (10:00)")])
    eps = planner.plan(s, 10)
    assert [[(x.unit, x.start, x.end) for x in e.segments] for e in eps] == [[(0, 0, 480)], [(1, 0, 600)]]
    # 남는 부분이 5분 미만이면(13분 강의, 10분 회차 → 3분 남음) 통째로
    s = season([blk("to_do", "강의 (13:00)")])
    assert len(planner.plan(s, 10)) == 1


def test_replan_from_position_after_minutes_change():
    lens = ["14:10", "18:27", "17:44", "66:00"]
    s = season([blk("to_do", f"{i}. 강의 ({t})") for i, t in enumerate(lens, start=1)])
    first = planner.plan(s, 55)[0]  # 1~3강 완료
    rest = planner.plan(s, 20, start=first.end, first_index=2)
    assert rest[0].index == 2
    assert rest[0].segments[0].unit == 3 and rest[0].segments[0].end == 20 * 60


def test_prediction_on_episode_and_hidden_on_last():
    blocks = [
        para_minutes(9), blk("quote", "Q1?"), blk("bulleted_list_item", rt("A", True)), blk("bulleted_list_item", "B"),
        para_minutes(9), blk("quote", "Q2?"), blk("bulleted_list_item", "C"), blk("bulleted_list_item", rt("D", True)),
    ]
    eps = planner.plan(season(blocks), 10)
    assert len(eps) == 2
    assert eps[0].prediction.question == "Q1?"
    assert eps[1].prediction is None  # 마지막 화


def test_summary_and_continuation_title():
    s = season([blk("heading_2", "1. 목표"), blk("callout", "요약"), para_minutes(10), para_minutes(10)])
    eps = planner.plan(s, 10)
    assert eps[0].title == "1. 목표" and eps[0].summary_unit == 1
    assert eps[1].title == "1. 목표 (이어서)"


def test_short_text_before_long_video_no_tiny_episode():
    # 1분 글 + 28분 영상, 하루 5분 → 글만 있는 1분 회차 대신 영상 5분을 붙인다
    s = season([para_minutes(1), blk("to_do", "강의 (28:00)")])
    eps = planner.plan(s, 5)
    assert eps[0].minutes == 6
    assert all(e.minutes >= 5 for e in eps[:-1])


def test_nested_lectures_and_videos_flattened():
    s = season([
        blk("paragraph", "Week 1", children=[blk("to_do", "1강 (14:10)"), blk("to_do", "2강 (18:27)")]),
        blk("numbered_list_item", "기초 계산", children=[
            {"id": "v", "type": "video", "video": {"type": "external", "external": {"url": "https://youtu.be/kVh8Horwabs"}, "caption": []}},
        ]),
    ], lambda _id: {"seconds": 1200, "title": "영상"})
    assert [u.kind for u in s.units] == ["text", "lecture", "lecture", "text", "video"]


def test_split_media_titles_numbered():
    s = season([blk("to_do", "4강 기획법 (66:00)")])
    eps = planner.plan(s, 55)
    assert [e.title for e in eps] == ["4강 기획법 (66:00) (1/2)", "4강 기획법 (66:00) (2/2)"]
    rest = planner.plan(s, 55, start=eps[0].end, first_index=2)
    assert rest[0].title == "4강 기획법 (66:00) (이어서)"


def test_episodes_from_starts_matches_plan():
    lens = ["14:10", "18:27", "17:44", "66:00", "24:14", "32:00"]
    s = season([blk("heading_2", "강의 목록")] + [blk("to_do", f"{i}강 ({t})") for i, t in enumerate(lens, start=1)])
    eps = planner.plan(s, 55)
    again = planner.episodes_from_starts(s, [e.start for e in eps])
    assert [(e.title, e.minutes) for e in again] == [(e.title, e.minutes) for e in eps]


def test_replan_keeps_done_episodes():
    s = season([para_minutes(5) for _ in range(12)])
    starts = [e.start for e in planner.plan(s, 10)]  # 6화
    new = planner.replan(s, 20, starts, keep=2)
    assert new[:2] == starts[:2]
    assert len(planner.episodes_from_starts(s, new)) == 2 + 2  # 남은 40분을 20분씩
    assert planner.starts_valid(s, new) and not planner.starts_valid(s, [(99, 0)])


def test_trailing_heading_moves_to_next_episode():
    # 1강 남은 25분 + 소제목, 2강(9:40)은 통째로 넣으면 115% 초과이고 자르면 4분만 남아 못 자름 → 소제목은 다음 회차 시작
    s = season([blk("to_do", "1강 (55:00)"), blk("heading_3", "2강 소개"), blk("to_do", "2강 (9:40)")])
    eps = planner.plan(s, 30)
    assert [seg.unit for seg in eps[1].segments] == [0]
    assert eps[2].title == "2강 소개"
