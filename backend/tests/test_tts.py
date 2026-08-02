import sys
from types import ModuleType

import pytest
from vietnormalizer import VietnameseNormalizer

from app.asr import SMART_HOME_VOCABULARY
from app.tts import OfflineTts, SynthesizedSpeech, VieneuTts, prepare_vietnamese_tts_text


class _BrokenTts:
    def synthesize(self, _: str) -> SynthesizedSpeech:
        raise RuntimeError("model unavailable")


class _FallbackTts:
    def synthesize(self, text: str) -> SynthesizedSpeech:
        return SynthesizedSpeech(b"RIFF-fallback", 1.0, text, "supertonic-3", "F4")


def test_aiot_terms_are_normalized_for_vietnamese_speech() -> None:
    normalized = prepare_vietnamese_tts_text(
        "CO₂ 2418 ppm, PM2.5 13.9 µg/m³, nhiệt độ 25°C.",
        VietnameseNormalizer(),
    )

    assert "xê ô hai" in normalized
    assert "phần triệu" in normalized
    assert "pê em hai phẩy năm" in normalized
    assert "mi crô gam trên mét khối" in normalized
    assert "mười ba phẩy chín" in normalized
    assert "hai mươi lăm độ" in normalized


def test_flatmate_lexicon_normalizes_full_assistant_response() -> None:
    normalized = prepare_vietnamese_tts_text(
        "Chế độ làm việc giữ nguyên: đèn chính 50%, 2700K. Không đổi thiết bị khác. "
        "CO2 cao: 1609 ppm, nên thông gió nếu cần.",
        VietnameseNormalizer(),
    )

    assert "năm mươi phần trăm" in normalized
    assert "hai nghìn bảy trăm ken vin" in normalized
    assert "xê ô hai" in normalized
    assert "một nghìn sáu trăm lẻ chín phần triệu" in normalized
    assert "2700k" not in normalized


def test_flatmate_lexicon_normalizes_common_app_acronyms() -> None:
    normalized = prepare_vietnamese_tts_text(
        "AC dùng AIoT; ASR nhận lệnh và TTS đọc lại.",
        VietnameseNormalizer(),
    )

    assert "điều hòa" in normalized
    assert "ây ai ô ti" in normalized
    assert "ây ét a" in normalized
    assert "ti ti ét" in normalized


def test_markdown_and_urls_are_removed_before_speech() -> None:
    normalized = prepare_vietnamese_tts_text(
        "## Trạng thái\n- [Điều hòa](https://example.com/ac): 25°C. Xem https://example.com.",
        VietnameseNormalizer(),
    )

    assert "trạng thái" in normalized
    assert "điều hòa" in normalized
    assert "hai mươi lăm độ" in normalized
    assert "http" not in normalized
    assert "example" not in normalized


def test_markdown_cleanup_does_not_create_hesitation_punctuation() -> None:
    normalized = prepare_vietnamese_tts_text(
        "## Trạng thái\nĐã cập nhật:\n- Điều hòa 26°C...\n- Quạt mức 2.",
        VietnameseNormalizer(),
    )

    assert normalized.startswith("trạng thái.")
    assert ":." not in normalized
    assert ".." not in normalized
    assert "điều hòa hai mươi sáu độ" in normalized
    assert "quạt mức hai" in normalized


def test_temperature_change_is_spoken_as_concise_final_state() -> None:
    normalized = prepare_vietnamese_tts_text(
        "AC giảm 26°C xuống 25°C. Cửa sổ giữ đóng để làm mát.;",
        VietnameseNormalizer(),
    )

    assert normalized == "điều hòa đặt hai mươi lăm độ. cửa sổ vẫn đóng."
    assert "xuống" not in normalized
    assert "độ xê" not in normalized


def test_asr_vocabulary_contains_critical_device_names() -> None:
    assert "điều hòa" in SMART_HOME_VOCABULARY
    assert "đèn chính" in SMART_HOME_VOCABULARY
    assert "máy lọc không khí" in SMART_HOME_VOCABULARY


def test_offline_tts_uses_supertonic_when_vieneu_fails() -> None:
    speech = OfflineTts(primary=_BrokenTts(), fallback=_FallbackTts()).synthesize("Xin chào")

    assert speech.engine == "supertonic-3"
    assert speech.voice == "F4"


def test_vieneu_initialization_failure_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0
    module = ModuleType("vieneu")

    def fail_to_load(**_: str) -> None:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("missing model")

    monkeypatch.setattr(module, "Vieneu", fail_to_load, raising=False)
    monkeypatch.setitem(sys.modules, "vieneu", module)
    tts = VieneuTts("Mai Anh")

    with pytest.raises(RuntimeError):
        tts.synthesize("Xin chào")
    with pytest.raises(RuntimeError, match="previously failed"):
        tts.synthesize("Xin chào")

    assert attempts == 1
