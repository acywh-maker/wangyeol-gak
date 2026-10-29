from itertools import count

_ids = count()


def rt(text, bold=False):
    return {"plain_text": text, "annotations": {"bold": bold}}


def blk(kind, *spans, children=None, **extra):
    data = {"rich_text": [s if isinstance(s, dict) else rt(s) for s in spans], **extra}
    b = {"id": f"b{next(_ids)}", "type": kind, kind: data}
    if children:
        b["children"] = children
    return b


def video(url, caption=""):
    return {"id": f"b{next(_ids)}", "type": "video",
            "video": {"type": "external", "external": {"url": url}, "caption": [rt(caption)] if caption else []}}


def para_minutes(minutes):
    """한글만으로 약 n분 읽기 분량 문단 (분당 500자 기준)."""
    return blk("paragraph", "가" * int(minutes * 500))
