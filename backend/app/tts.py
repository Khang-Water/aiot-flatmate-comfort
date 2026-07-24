import re
from dataclasses import dataclass
from io import BytesIO
from threading import Lock

import soundfile as sf
from supertonic import TTS
from vietnormalizer import VietnameseNormalizer

from app.tts_lexicon import apply_app_tts_lexicon

_DECIMAL_DOT = re.compile(r"(?<=\d)\.(?=\d)")


def prepare_vietnamese_tts_text(text: str, normalizer: VietnameseNormalizer) -> str:
    prepared = apply_app_tts_lexicon(text)
    prepared = _DECIMAL_DOT.sub(",", prepared)
    return normalizer.normalize(prepared)


@dataclass(frozen=True)
class SynthesizedSpeech:
    audio: bytes
    duration_seconds: float
    normalized_text: str


class SupertonicTts:
    """Lazy local Supertonic engine; first synthesis downloads model assets."""

    def __init__(self, voice: str, steps: int, speed: float) -> None:
        self.voice = voice
        self.steps = steps
        self.speed = speed
        self._engine: TTS | None = None
        self._normalizer = VietnameseNormalizer()
        self._lock = Lock()

    def synthesize(self, text: str) -> SynthesizedSpeech:
        with self._lock:
            if self._engine is None:
                self._engine = TTS(auto_download=True)
            normalized = prepare_vietnamese_tts_text(text, self._normalizer)
            style = self._engine.get_voice_style(voice_name=self.voice)
            wav, duration = self._engine.synthesize(
                text=normalized,
                lang="vi",
                voice_style=style,
                total_steps=self.steps,
                speed=self.speed,
                max_chunk_length=300,
                silence_duration=0.25,
            )
            output = BytesIO()
            sf.write(output, wav.squeeze(), self._engine.sample_rate, format="WAV", subtype="PCM_16")
            return SynthesizedSpeech(
                audio=output.getvalue(),
                duration_seconds=float(duration[0]),
                normalized_text=normalized,
            )
