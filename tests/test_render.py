from wangyeol import parser, planner, render

from helpers import blk, rt, video


def test_escapes_text_and_blocks_unsafe_links():
    evil = {"plain_text": "<script>alert(1)</script>", "annotations": {}, "href": "javascript:alert(1)"}
    html = render.blocks_html([blk("paragraph", evil)])
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "javascript:" not in html


def test_lists_and_bold():
    html = render.blocks_html([blk("bulleted_list_item", "가"), blk("bulleted_list_item", rt("나", True))])
    assert html == "<ul><li>가</li><li><strong>나</strong></li></ul>"


def test_video_segment_plays_only_its_range():
    s = parser.parse_season("p", "t", "u", None, [video("https://youtu.be/kVh8Horwabs")], lambda _id: {"seconds": 1800, "title": "영상"})
    eps = planner.plan(s, 10)
    html = render.segment_html(s.units, eps[1].segments[0])
    assert "embed/kVh8Horwabs" in html and "start=600" in html and "end=1200" in html
