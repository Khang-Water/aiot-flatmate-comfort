import re
from collections.abc import Sequence

LexiconEntry = tuple[re.Pattern[str], str]

APP_TTS_LEXICON: Sequence[LexiconEntry] = (
    (
        re.compile(
            r"\b(?:AC|điều hòa)\s+(?:giảm|tăng|đổi|chỉnh)(?:\s+từ)?\s+"
            r"\d+(?:[.,]\d+)?\s*°\s*C\s+(?:xuống|lên|sang|còn)\s+(?:mức\s+)?"
            r"(?P<target>\d+(?:[.,]\d+)?)\s*°\s*C\b",
            re.IGNORECASE,
        ),
        r"điều hòa đặt \g<target> độ",
    ),
    (
        re.compile(r"\bcửa sổ\s+giữ\s+đóng(?:\s+để\s+làm\s+mát)?", re.IGNORECASE),
        "cửa sổ vẫn đóng",
    ),
    (re.compile(r"\bPM\s*2[.,]5\b", re.IGNORECASE), "pê em hai phẩy năm"),
    (re.compile(r"\bCO(?:2|₂)\b", re.IGNORECASE), "xê ô hai"),
    (re.compile(r"µg\s*/\s*m(?:3|³)", re.IGNORECASE), "mi crô gam trên mét khối"),
    (re.compile(r"\bug\s*/\s*m(?:3|³)\b", re.IGNORECASE), "mi crô gam trên mét khối"),
    (re.compile(r"(?<=\d)\s*°\s*C\b", re.IGNORECASE), " độ"),
    (re.compile(r"(?<=\d)\s*K\b", re.IGNORECASE), " ken vin"),
    (re.compile(r"(?<=\d)\s*%"), " phần trăm"),
    (re.compile(r"\bppm\b", re.IGNORECASE), "phần triệu"),
    (re.compile(r"\bkWh\b", re.IGNORECASE), "ki lô oát giờ"),
    (re.compile(r"(?<=\d)\s*W\b", re.IGNORECASE), " oát"),
    (re.compile(r"\bdB\b", re.IGNORECASE), "đề xi ben"),
    (re.compile(r"\blux\b", re.IGNORECASE), "lúc"),
    (re.compile(r"\bTV\b", re.IGNORECASE), "ti vi"),
    (re.compile(r"\bAC\b", re.IGNORECASE), "điều hòa"),
    (re.compile(r"\bAIoT\b", re.IGNORECASE), "ây ai ô ti"),
    (re.compile(r"\bASR\b", re.IGNORECASE), "ây ét a"),
    (re.compile(r"\bTTS\b", re.IGNORECASE), "ti ti ét"),
)


def apply_app_tts_lexicon(text: str) -> str:
    prepared = text
    for pattern, replacement in APP_TTS_LEXICON:
        prepared = pattern.sub(replacement, prepared)
    return prepared
