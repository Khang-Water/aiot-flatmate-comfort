from vietnormalizer import VietnameseNormalizer

from app.asr import SMART_HOME_VOCABULARY
from app.tts import prepare_vietnamese_tts_text


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
    assert "hai mươi lăm độ xê" in normalized


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


def test_asr_vocabulary_contains_critical_device_names() -> None:
    assert "điều hòa" in SMART_HOME_VOCABULARY
    assert "đèn chính" in SMART_HOME_VOCABULARY
    assert "máy lọc không khí" in SMART_HOME_VOCABULARY
