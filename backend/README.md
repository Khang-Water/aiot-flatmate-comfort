# Backend

Python 3.11 FastAPI simulation and assistant service. Optional local speech extra uses faster-whisper ASR, VieNeu v3 Turbo ONNX synthesis, and Supertonic fallback; Render omits this extra.

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
└── storage.py           SQLite history, preference evidence, and implicit learning
```

Manual overrides become implicit feedback only when they change the same property most recently set by the assistant, the previous value still matches the assistant output, and the action occurs within 30 simulated minutes. Backend stores an unconfirmed `learned` candidate after the first observation and activates it after three identical targets in the same inferred context. Explicit, temporary, and conversational correction preferences keep their existing higher priority.

Run from repository root with `make api`. Command enables optional `speech` dependencies. Add `OPENAI_API_KEY` to root `.env` to enable assistant requests.

First `POST /api/asr` downloads faster-whisper `small` to the local cache. Defaults: CPU, `int8`, beam size 2; override with `ASR_MODEL`, `ASR_DEVICE`, `ASR_COMPUTE_TYPE`, and `ASR_BEAM_SIZE`.

First `POST /api/tts` downloads VieNeu v3 Turbo model assets. Default engine is ONNX `int8` on CPU with voice `Mai Anh`; set `TTS_ENGINE=supertonic` to disable VieNeu. Supertonic remains automatic fallback and uses `SUPERTONIC_VOICE`, `SUPERTONIC_STEPS`, and `SUPERTONIC_SPEED`.

Set `LOCAL_SPEECH_ENABLED=false` when installing without `--extra speech`. `/api/asr` and `/api/tts` then return `503`; deployed frontend uses browser speech instead.
