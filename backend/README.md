# Backend

Python 3.11 FastAPI simulation, assistant, and offline Vietnamese speech service. Speech uses faster-whisper ASR, VietNormalizer text normalization, VieNeu v3 Turbo ONNX synthesis, and Supertonic fallback.

Current modules:

```text
app/
├── config.py            validated environment settings
├── assistant.py         Responses API loop and safe trace publishing
├── asr.py               lazy faster-whisper Vietnamese transcription
├── main.py              FastAPI lifecycle, routes, errors, SSE
├── models.py            Pydantic API and domain contracts
├── state.py             ordered in-process SSE broker
├── simulation.py        clock, drift, context, scenarios
├── scenarios.py         JSON scenario repository
├── commands.py          atomic device validation
├── tts.py               normalized VieNeu synthesis + Supertonic fallback
└── storage.py           SQLite history and CSV export
```

Run from repository root with `make api`. Add `OPENAI_API_KEY` to root `.env` to enable assistant requests.

First `POST /api/asr` downloads faster-whisper `small` to the local cache. Defaults: CPU, `int8`, beam size 2; override with `ASR_MODEL`, `ASR_DEVICE`, `ASR_COMPUTE_TYPE`, and `ASR_BEAM_SIZE`.

First `POST /api/tts` downloads VieNeu v3 Turbo model assets. Default engine is ONNX `int8` on CPU with voice `Mai Anh`; set `TTS_ENGINE=supertonic` to disable VieNeu. Supertonic remains automatic fallback and uses `SUPERTONIC_VOICE`, `SUPERTONIC_STEPS`, and `SUPERTONIC_SPEED`.
