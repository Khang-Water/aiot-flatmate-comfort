from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration loaded from environment or repository `.env`."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    web_origin: str = "http://localhost:3000"
    database_path: Path = PROJECT_ROOT / "data" / "flatmate.db"
    simulation_seed: int = 42
    simulation_tick_seconds: float = Field(default=2, gt=0)
    simulation_minutes_per_tick: int = Field(default=1, gt=0)
    openai_api_key: str = ""
    openai_base_url: str | None = None
    openai_model: str = "gpt-5.6-sol"
    openai_reasoning_effort: str = "low"
    openai_timeout_seconds: float = Field(default=45, gt=0, le=180)
    supertonic_voice: str = Field(default="F1", pattern=r"^[MF][1-5]$")
    supertonic_steps: int = Field(default=10, ge=5, le=12)
    supertonic_speed: float = Field(default=1.15, ge=0.7, le=2.0)
    asr_model: str = "large-v3-turbo"
    asr_device: str = "cpu"
    asr_compute_type: str = "int8"
    asr_beam_size: int = Field(default=5, ge=1, le=10)


@lru_cache
def get_settings() -> Settings:
    return Settings()
