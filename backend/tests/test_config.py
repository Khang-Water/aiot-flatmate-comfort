from app.config import Settings


def test_default_asr_uses_multilingual_turbo_model() -> None:
    settings = Settings(_env_file=None)

    assert settings.asr_model == "large-v3-turbo"
    assert settings.asr_device == "cpu"
    assert settings.asr_compute_type == "int8"
