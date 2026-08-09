from app.config import Settings


def test_default_speech_models_are_cpu_friendly_and_high_quality() -> None:
    settings = Settings(_env_file=None)

    assert settings.openai_api_mode == "responses"
    assert settings.tts_enabled is True
    assert settings.local_asr_enabled is True
    assert settings.asr_model == "small"
    assert settings.asr_device == "cpu"
    assert settings.asr_compute_type == "int8"
    assert settings.asr_beam_size == 2
    assert settings.tts_engine == "vieneu"
    assert settings.tts_max_characters == 2_000
    assert settings.vieneu_voice == "Mai Anh"
    assert settings.supertonic_voice == "F4"
    assert settings.supertonic_steps == 12
    assert settings.supertonic_speed == 1.0
    assert settings.piper_voice == "vi_VN-vais1000-medium"
    assert settings.piper_model_path.name == "vi_VN-vais1000-medium.onnx"
