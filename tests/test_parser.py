from wangyeol import parser
from wangyeol.text import eul, ieosseoyo

from helpers import blk, rt, video


def units(blocks, video_info=lambda _id: None):
    return parser.build_units(blocks, video_info)


def test_text_units_and_headings():
    us = units([blk("heading_2", "목표"), blk("paragraph", "가" * 500), blk("callout", "요약")])
    assert [u.kind for u in us] == ["text", "text", "text"]
    assert us[0].heading and us[0].title == "목표"
    assert abs(us[1].seconds - 60) < 1
    assert us[2].is_callout


def test_reading_seconds_mixed():
    assert abs(parser.reading_seconds("가" * 250 + " word" * 100) - (30 + 30)) < 1


def test_prediction_bold_answer_attached_to_previous_unit():
    us = units([
        blk("paragraph", "본문"),
        blk("quote", "장바구니 이탈을 더 줄인 건?"),
        blk("bulleted_list_item", "할인 쿠폰"),
        blk("bulleted_list_item", rt("무료 배송", bold=True)),
        blk("paragraph", "다음"),
    ])
    assert len(us) == 2
    assert us[0].prediction.choices == ["할인 쿠폰", "무료 배송"]
    assert us[0].prediction.answer == "무료 배송"


def test_prediction_answer_mark_hidden():
    us = units([blk("paragraph", "x"), blk("quote", "Q?"),
                blk("bulleted_list_item", "A (정답)"), blk("bulleted_list_item", "B")])
    assert us[0].prediction.choices == ["A", "B"]
    assert us[0].prediction.answer_index == 0


def test_prediction_invalid_kept_as_body():
    no_answer = units([blk("quote", "Q?"), blk("bulleted_list_item", "A"), blk("bulleted_list_item", "B")])
    assert all(u.prediction is None for u in no_answer) and len(no_answer) == 3
    three = units([blk("quote", "Q?"), blk("bulleted_list_item", rt("A", True)),
                   blk("bulleted_list_item", "B"), blk("bulleted_list_item", "C")])
    assert all(u.prediction is None for u in three)
    two_answers = units([blk("quote", "Q?"), blk("bulleted_list_item", rt("A", True)),
                         blk("bulleted_list_item", rt("B", True))])
    assert all(u.prediction is None for u in two_answers)


def test_youtube_ids():
    assert parser.youtube_id("https://youtu.be/kVh8Horwabs?si=abc") == "kVh8Horwabs"
    assert parser.youtube_id("https://www.youtube.com/watch?v=kVh8Horwabs&t=3") == "kVh8Horwabs"
    assert parser.youtube_id("https://youtube.com/shorts/kVh8Horwabs") == "kVh8Horwabs"
    assert parser.youtube_id("https://vimeo.com/123") is None


def test_parse_range_and_duration():
    assert parser.parse_range("12:30-17:45") == (750, 1065)
    assert parser.parse_range("구간 1:02:03–1:05:00") == (3723, 3900)
    assert parser.parse_range("17:45-12:30") is None
    assert parser.parse_duration("1. 슬파가 성공한 이유(14:10)") == 850
    assert parser.parse_duration("16-1 까지 1강 · 1시간 33분 16초") == 5596
    assert parser.parse_duration("15-1~3 까지 3강 · 29분 17초+27분 28초") == 1757 + 1648
    assert parser.parse_duration("2023 New 1강") is None


def test_video_duration_priority():
    url = "https://youtu.be/kVh8Horwabs"
    # 캡션 구간이 최우선
    assert units([video(url, "12:30-17:45")])[0].seconds == 315
    # 자동으로 읽은 길이
    assert units([video(url)], lambda _id: {"seconds": 600, "title": "영상"})[0].seconds == 600
    # 자동 실패 → 캡션의 (14:10)
    assert units([video(url, "(14:10)")])[0].seconds == 850
    # 둘 다 없음 → 10분
    assert units([video(url)])[0].seconds == 600


def test_range_note_paragraph_consumed():
    us = units([video("https://youtu.be/kVh8Horwabs"), blk("paragraph", "▶ 1:00-2:00"), blk("paragraph", "다음")])
    assert us[0].youtube["range"] == (60, 120)
    assert len(us) == 2


def test_lecture_units():
    us = units([
        blk("to_do", "4. 콘텐츠 기획법 · 1시간 6분"),
        blk("bulleted_list_item", "5. 오리지널리티(24:14)"),
        blk("bulleted_list_item", "하루 3분만 투자해도"),  # 일반 목록의 한글 시간은 강의 아님
    ])
    assert [u.kind for u in us] == ["lecture", "lecture", "text"]
    assert us[0].seconds == 3960 and us[1].seconds == 1454


def test_nested_video_counts_time():
    us = units([blk("toggle", "펼치기", children=[video("https://youtu.be/kVh8Horwabs")])], lambda _id: {"seconds": 300, "title": "영상"})
    assert us[0].kind == "text" and us[0].seconds >= 300
    assert us[0].blocks[0]["children"][0]["_yt"]["id"] == "kVh8Horwabs"


def test_josa():
    assert eul("무료 배송") == "무료 배송을"
    assert eul("사과") == "사과를"
    assert ieosseoyo("할인 쿠폰") == "할인 쿠폰이었어요"
    assert ieosseoyo("A") == "A였어요"
