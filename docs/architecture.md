# Architecture

## Runtime

```text
Localhost                         Render Free / HTTPS
MediaRecorder -> /api/asr        SpeechRecognition vi-VN
/api/tts -> VieNeu/Supertonic    /api/tts -> Piper medium WAV
             \                    /
              Next.js web app ---------------- GET /api/events (SSE)
                       |                                  ^
                       | REST                             | state + trace
                       v                                  |
              FastAPI assistant API -> OpenAI Responses API
                       |
                       v
              Validation -> simulation engine -> event bus
                                      |
                                      +-> in-memory state
                                      +-> SQLite history/preferences
                                      +-> generated CSV/JSON data
```

## Responsibilities

### Web

- Render cozy fixed-layout 3D apartment and accessible text equivalent.
- Select capture provider with `NEXT_PUBLIC_SPEECH_MODE` and TTS provider with `NEXT_PUBLIC_TTS_MODE`.
- Local mode records with `MediaRecorder`, uploads to faster-whisper, and plays backend WAV.
- Render mode uses `SpeechRecognition` with `vi-VN`, then plays Piper WAV returned by backend; optional wake phrase stays `en-US`.
- Send text requests and manual commands through REST.
- Consume ordered state and trace events through one SSE stream.

### API

- Own configuration, request lifecycle, REST endpoints, and SSE stream.
- Infer deterministic context before contacting the model.
- Retrieve context-scoped preferences before the model request.
- Treat model-supplied preference IDs as optional provenance; ignore unknown IDs and never mark them used.
- Enforce explicit numeric targets and deterministic Vietnamese light-color mappings before scene validation.
- Normalize model power/level dependencies, enforce CO₂ ventilation for work/sleep preparation, and preserve explicit user negation.
- Run OpenAI Responses tool loop and publish safe trace events.
- Validate numerical targets before simulation mutations.
- Mark abandoned invalid scenes failed instead of reporting a completed request.
- After commit, call the LLM once without tools using the original request, committed `ChangedValue` records, current snapshot, context, and preference flags; keep deterministic confirmation only as an API-error fallback.
- Record conversations, actions, trace summaries, preferences, and implicit feedback evidence.
- Load backend TTS only when `TTS_ENABLED=true`; load faster-whisper separately when `LOCAL_ASR_ENABLED=true`.
- Normalize Vietnamese TTS text through the same lexicon/VietNormalizer path before VieNeu, Supertonic, or Piper synthesis.

### Simulation engine

- Maintain one authoritative `RoomSnapshot` in memory.
- Advance seeded environmental drift on configured ticks.
- Apply scenario events and validated manual/model commands.
- Forward validated manual overrides to the preference learner after recording device actions.
- Persist sampled history to SQLite and export generated datasets.

### Storage

SQLite stores sensor samples, device actions, conversations, trace events, preferences, and explicit/correction/implicit evidence. For implicit feedback, storage matches a manual change with the latest assistant action on the same property, requires matching before/after continuity, creates an unconfirmed `learned` candidate, and promotes it after three identical observations in the same context. Current apartment state stays in memory because only one local process and user exist.

## Key decisions

- SSE over WebSocket: server primarily pushes ordered state and trace events; commands remain ordinary REST.
- SQLite over Redis/PostgreSQL: one local demo process needs persistence, not distributed coordination.
- Responses API over Chat Completions: assistant needs structured tools and reasoning in one workflow.
- Primitive local 3D geometry first: reliable demo without asset licensing or network loading.
- Local speech over cloud speech for development: controlled model, vocabulary and offline behavior.
- Browser ASR on Render Free: removes Whisper from server while keeping text fallback for unsupported browsers.
- Piper medium TTS on Render Free: removes browser voice dependency; measured full-service RSS is about 250 MiB under the 512 MB limit.
- Optional dependency extras: local commands install `speech`; deployment installs only `piper`.
- Ephemeral SQLite on Render Free: adequate for demo, not durable preference storage.
- No automatic device changes outside explicit scenario, manual, or assistant actions.
- Deterministic guards complement model tool use for high-confidence commands; they do not replace vague-intent reasoning.
- Implicit learning records evidence only; applying a promoted preference still requires a later validated assistant action.

## Failure behavior

- Missing OpenAI key: disable assistant submission and show setup message.
- OpenAI timeout/error before commit: emit a failed trace event and keep room state unchanged.
- OpenAI timeout/error while generating post-commit text: keep the committed state, return deterministic confirmation, and record the failed model call.
- Invalid tool arguments: reject complete tool action; do not partially apply scene.
- SSE disconnect: web reconnects and fetches fresh snapshot before processing new events.
- WebGL unavailable: dashboard and accessible apartment status remain usable.
- Microphone unavailable: text input remains usable.
- Backend TTS unavailable or browser recognition unsupported: final text remains visible and device actions remain complete.
