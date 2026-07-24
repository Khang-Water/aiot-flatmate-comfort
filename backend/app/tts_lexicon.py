import re
from collections.abc import Sequence

LexiconEntry = tuple[re.Pattern[str], str]

APP_TTS_LEXICON: Sequence[LexiconEntry] = (
    (re.compile(r"\bPM\s*2[.,]5\b", re.IGNORECASE), "pê em hai phẩy năm"),
    (re.compile(r"\bCO(?:2|₂)\b", re.IGNORECASE), "xê ô hai"),
    (re.compile(r"µg\s*/\s*m(?:3|³)", re.IGNORECASE), "mi crô gam trên mét khối"),
    (re.compile(r"\bug\s*/\s*m(?:3|³)\b", re.IGNORECASE), "mi crô gam trên mét khối"),
    (re.compile(r"(?<=\d)\s*°\s*C\b", re.IGNORECASE), " độ xê"),
    (re.compile(r"(?<=\d)\s*K\b", re.IGNORECASE), " ken vin"),
    (re.compile(r"(?<=\d)\s*%"), " phần trăm"),
    (re.compile(r"\bppm\b", re.IGNORECASE), "phần triệu"),
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
