"""화면 문구 도우미."""


def _has_batchim(word: str) -> bool:
    for ch in reversed(word.strip()):
        if "가" <= ch <= "힣":
            return (ord(ch) - ord("가")) % 28 != 0
        if ch.isalnum():
            return False  # 영문·숫자로 끝나면 받침 없음으로 처리
    return False


def eul(word: str) -> str:
    """'무료 배송' → '무료 배송을', '할인 쿠폰' → '할인 쿠폰을', '사과' → '사과를'"""
    return word + ("을" if _has_batchim(word) else "를")


def ieosseoyo(word: str) -> str:
    """'무료 배송' → '무료 배송이었어요', '사과' → '사과였어요'"""
    return word + ("이었어요" if _has_batchim(word) else "였어요")
