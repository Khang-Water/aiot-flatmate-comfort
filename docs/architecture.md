# Architecture

## Runtime

```text
Localhost                         Render Free / HTTPS
MediaRecorder -> /api/asr        SpeechRecognition vi-VN
/api/tts -> WAV                  speechSynthesis vi-VN
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
- Select speech provider at build time with `NEXT_PUBLIC_SPEECH_MODE`.
- Local mode records with `MediaRecorder`, uploads to faster-whisper, and plays backend WAV.
- Browser mode uses `SpeechRecognition` and `speechSynthesis` with `vi-VN`; optional wake phrase stays `en-US`.
- Send text requests and manual commands through REST.
- Consume ordered state and trace events through one SSE stream.

### API

- Own configuration, request lifecycle, REST endpoints, and SSE stream.
- Infer deterministic context before contacting the model.
- Run OpenAI Responses tool loop and publish safe trace events.
- Validate numerical targets before simulation mutations.
- Record conversations, actions, trace summaries, preferences, and implicit feedback evidence.
- Load local ASR/TTS modules only when `LOCAL_SPEECH_ENABLED=true`.
- In local mode, normalize Vietnamese TTS text, synthesize through VieNeu/Supertonic, and transcribe through faster-whisper.

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
- Browser speech on Render Free: removes model dependencies and CPU/RAM inference from server, accepting browser compatibility and voice variation.
- Optional `speech` dependency extra: local commands install it; deployment image omits it.
- Ephemeral SQLite on Render Free: adequate for demo, not durable preference storage.
- No automatic device changes outside explicit scenario, manual, or assistant actions.
- Implicit learning records evidence only; applying a promoted preference still requires a later validated assistant action.

## Failure behavior

- Missing OpenAI key: disable assistant submission and show setup message.
- OpenAI timeout/error: emit failed trace event and keep room state unchanged.
- Invalid tool arguments: reject complete tool action; do not partially apply scene.
- SSE disconnect: web reconnects and fetches fresh snapshot before processing new events.
- WebGL unavailable: dashboard and accessible apartment status remain usable.
- Microphone unavailable: text input remains usable.
- Local speech engine unavailable or browser Web Speech unsupported: final text remains visible and device actions remain complete.
