from dataclasses import dataclass
from io import BytesIO
from threading import Lock

from faster_whisper import WhisperModel

SMART_HOME_VOCABULARY = (
    "điều hòa, đèn chính, đèn đầu giường, quạt, máy lọc không khí, cửa sổ, "
    "rèm cửa, máy tính, màn hình, ổ cắm, nhiệt độ, độ ẩm, CO2, PM2.5"
)


@dataclass(frozen=True)
class Transcription:
    text: str
    language: str
    language_probability: float
    duration_seconds: float


class VietnameseAsr:
    """Lazy local faster-whisper ASR for Vietnamese commands."""

    def __init__(self, model_name: str, device: str, compute_type: str, beam_size: int) -> None:
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.beam_size = beam_size
        self._model: WhisperModel | None = None
        self._lock = Lock()

    def transcribe(self, audio: bytes) -> Transcription:
        with self._lock:
            if self._model is None:
                self._model = WhisperModel(
                    self.model_name,
                    device=self.device,
                    compute_type=self.compute_type,
                )
            segments, info = self._model.transcribe(
                BytesIO(audio),
                language="vi",
                beam_size=self.beam_size,
                vad_filter=True,
                vad_parameters={
                    "min_silence_duration_ms": 500,
                    "speech_pad_ms": 250,
                },
                condition_on_previous_text=False,
                initial_prompt=(
                    "Đây là lệnh tiếng Việt điều khiển căn hộ thông minh FlatMate. "
                    "Hãy chép chính xác tên thiết bị, số, đơn vị và trạng thái bật tắt."
                ),
                hotwords=SMART_HOME_VOCABULARY,
            )
            text = " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
            return Transcription(
                text=text,
                language=info.language,
                language_probability=float(info.language_probability),
                duration_seconds=float(info.duration),
            )
