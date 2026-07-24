# Backend

Python 3.11 FastAPI simulation, assistant, and local Vietnamese speech service. Phase 5 adds faster-whisper ASR, VietNormalizer text normalization, and Supertonic 3 WAV synthesis.

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
├── tts.py               VietNormalizer + lazy local Supertonic synthesis
└── storage.py           SQLite history and CSV export
```

Run from repository root with `make api`. Add `OPENAI_API_KEY` to root `.env` to enable assistant requests.

First `POST /api/asr` downloads faster-whisper `small` to the local cache. Defaults: CPU, `int8`, beam size 5; override with `ASR_MODEL`, `ASR_DEVICE`, `ASR_COMPUTE_TYPE`, and `ASR_BEAM_SIZE`.

First `POST /api/tts` downloads about 400 MB of Supertonic assets to the local cache. Defaults: voice `F1`, 10 inference steps, speed `1.15`; override with `SUPERTONIC_VOICE`, `SUPERTONIC_STEPS`, and `SUPERTONIC_SPEED`.
