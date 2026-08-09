import json
import re
import wave
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from threading import Lock
from typing import Any, Protocol

from vietnormalizer import VietnameseNormalizer

from app.tts_lexicon import apply_app_tts_lexicon

_DECIMAL_DOT = re.compile(r"(?<=\d)\.(?=\d)")
_MARKDOWN_LINK = re.compile(r"\[([^]]+)]\([^)]+\)")
_URL = re.compile(r"https?://\S+")
_MARKDOWN_HEADING = re.compile(r"(?m)^\s*#{1,6}\s+")
_MARKDOWN_LIST_MARKER = re.compile(r"(?m)^\s*(?:[-*+]|\d+[.)])\s+")
_LINE_BREAK = re.compile(r"\s*\n+\s*")
_REDUNDANT_STOP = re.compile(r"([.!?;:,])\s*\.+")
_ELLIPSIS = re.compile(r"\.{2,}")
_PUNCTUATION_AFTER_STOP = re.compile(r"([.!?])\s*[,;:]+")
_TRAILING_SOFT_STOP = re.compile(r"[,;:]+\s*$")
_WHITESPACE = re.compile(r"\s+")


def prepare_vietnamese_tts_text(text: str, normalizer: VietnameseNormalizer) -> str:
    prepared = _MARKDOWN_LINK.sub(r"\1", text)
    prepared = _URL.sub("", prepared)
    prepared = _MARKDOWN_HEADING.sub("", prepared)
    prepared = _MARKDOWN_LIST_MARKER.sub("", prepared)
    prepared = prepared.replace("```", " ").replace("`", " ").replace("**", " ").replace("__", " ")
    prepared = _LINE_BREAK.sub(". ", prepared)
    prepared = _REDUNDANT_STOP.sub(r"\1 ", prepared)
    prepared = _ELLIPSIS.sub(".", prepared)
    prepared = _PUNCTUATION_AFTER_STOP.sub(r"\1", prepared)
    prepared = _TRAILING_SOFT_STOP.sub(".", prepared)
    prepared = apply_app_tts_lexicon(prepared)
    prepared = _DECIMAL_DOT.sub(",", prepared)
    return normalizer.normalize(_WHITESPACE.sub(" ", prepared).strip())


@dataclass(frozen=True)
class SynthesizedSpeech:
    audio: bytes
    duration_seconds: float
    normalized_text: str
    engine: str
    voice: str


class _SpeechSynthesizer(Protocol):
    def synthesize(self, text: str) -> SynthesizedSpeech: ...


class VieneuTts:
    """Lazy VieNeu v3 Turbo ONNX engine for deterministic Vietnamese CPU speech."""

    sample_rate = 48_000

    def __init__(self, voice: str) -> None:
        self.voice = voice
        self._engine: Any | None = None
        self._load_error: Exception | None = None
        self._normalizer = VietnameseNormalizer()
        self._lock = Lock()

    def _get_engine(self) -> Any:
        if self._load_error is not None:
            raise RuntimeError("VieNeu initialization previously failed") from self._load_error
        if self._engine is None:
            try:
                from vieneu import Vieneu

                self._engine = Vieneu(backend="onnx", precision="int8")
            except Exception as error:
                self._load_error = error
                raise
        return self._engine

    def synthesize(self, text: str) -> SynthesizedSpeech:
        with self._lock:
            import soundfile as sf

            engine = self._get_engine()
            normalized = prepare_vietnamese_tts_text(text, self._normalizer)
            # ponytail: Fixed CPU tuning; expose knobs only when another deployment needs different hardware tuning.
            wav = engine.infer(
                normalized,
                voice=self.voice,
                style="tu_nhien",
                temperature=0.0,
                top_k=20,
                top_p=0.9,
                repetition_penalty=1.25,
                silence_p=0.08,
                crossfade_p=0.02,
            )
            output = BytesIO()
            sf.write(output, wav, self.sample_rate, format="WAV", subtype="PCM_16")
            return SynthesizedSpeech(
                audio=output.getvalue(),
                duration_seconds=len(wav) / self.sample_rate,
                normalized_text=normalized,
                engine="vieneu-v3-turbo-onnx-int8",
                voice=self.voice,
            )


class SupertonicTts:
    """Lazy local Supertonic engine; first synthesis downloads model assets."""

    def __init__(self, voice: str, steps: int, speed: float) -> None:
        self.voice = voice
        self.steps = steps
        self.speed = speed
        self._engine: Any | None = None
        self._normalizer = VietnameseNormalizer()
        self._lock = Lock()

    def synthesize(self, text: str) -> SynthesizedSpeech:
        with self._lock:
            if self._engine is None:
                from supertonic import TTS

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
                silence_duration=0.08,
            )
            import soundfile as sf

            output = BytesIO()
            sf.write(output, wav.squeeze(), self._engine.sample_rate, format="WAV", subtype="PCM_16")
            return SynthesizedSpeech(
                audio=output.getvalue(),
                duration_seconds=float(duration[0]),
                normalized_text=normalized,
                engine="supertonic-3",
                voice=self.voice,
            )


class PiperTts:
    """Lazy single-threaded Piper engine sized for Render Free."""

    def __init__(self, model_path: Path, voice: str) -> None:
        self.model_path = model_path
        self.voice = voice
        self._engine: Any | None = None
        self._load_error: Exception | None = None
        self._normalizer = VietnameseNormalizer()
        self._lock = Lock()

    def _load_engine(self) -> Any:
        import onnxruntime
        from piper import PiperVoice
        from piper.config import PiperConfig

        config_path = Path(f"{self.model_path}.json")
        with config_path.open(encoding="utf-8") as config_file:
            config = PiperConfig.from_dict(json.load(config_file))
        options = onnxruntime.SessionOptions()
        # ponytail: Render Free has 0.1 CPU; expose thread tuning when deployment gains dedicated CPU.
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        session = onnxruntime.InferenceSession(
            str(self.model_path),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        return PiperVoice(session=session, config=config)

    def _get_engine(self) -> Any:
        if self._load_error is not None:
            raise RuntimeError("Piper initialization previously failed") from self._load_error
        if self._engine is None:
            try:
                self._engine = self._load_engine()
            except Exception as error:
                self._load_error = error
                raise
        return self._engine

    def synthesize(self, text: str) -> SynthesizedSpeech:
        with self._lock:
            engine = self._get_engine()
            normalized = prepare_vietnamese_tts_text(text, self._normalizer)
            output = BytesIO()
            with wave.open(output, "wb") as wav_file:
                engine.synthesize_wav(normalized, wav_file)
            audio = output.getvalue()
            with wave.open(BytesIO(audio), "rb") as wav_file:
                duration_seconds = wav_file.getnframes() / wav_file.getframerate()
            return SynthesizedSpeech(
                audio=audio,
                duration_seconds=duration_seconds,
                normalized_text=normalized,
                engine="piper-1.6.0-onnx-cpu",
                voice=self.voice,
            )


class OfflineTts:
    def __init__(self, primary: _SpeechSynthesizer, fallback: _SpeechSynthesizer | None = None) -> None:
        self.primary = primary
        self.fallback = fallback

    def synthesize(self, text: str) -> SynthesizedSpeech:
        try:
            return self.primary.synthesize(text)
        except Exception:
            if self.fallback is None:
                raise
            return self.fallback.synthesize(text)
