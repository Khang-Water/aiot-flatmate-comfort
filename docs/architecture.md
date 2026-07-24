# Architecture

## Runtime

```text
Browser MediaRecorder/text
        |
        v
Next.js web app ---------------------- GET /api/events (SSE)
        |                                      ^
        | REST                                 | state + trace events
        v                                      |
FastAPI assistant API -> OpenAI Responses API |
        |              -> VietNormalizer      |
        |              -> Supertonic 3 WAV    |
        v                                      |
Validation -> simulation engine -> event bus --+
                    |
                    +-> in-memory current state
                    +-> SQLite history/preferences
                    +-> generated CSV/JSON data
```

## Responsibilities

### Web

- Render cozy fixed-layout 3D apartment and accessible text equivalent.
- Record command audio with `MediaRecorder`; use browser recognition only for optional `en-US` wake phrase.
- Upload command audio for local faster-whisper Vietnamese transcription.
- Send text requests and manual commands through REST.
- Consume ordered state and trace events through one SSE stream.
- Request locally generated Vietnamese WAV audio and play it with browser audio controls.

### API

- Own configuration, request lifecycle, REST endpoints, and SSE stream.
- Infer deterministic context before contacting the model.
- Run OpenAI Responses tool loop and publish safe trace events.
- Validate numerical targets before simulation mutations.
- Record conversations, actions, trace summaries, and preferences.
- Normalize Vietnamese TTS text with VietNormalizer and synthesize it locally with Supertonic 3.
- Transcribe uploaded command audio locally with faster-whisper and smart-home vocabulary bias.

### Simulation engine

- Maintain one authoritative `RoomSnapshot` in memory.
- Advance seeded environmental drift on configured ticks.
- Apply scenario events and validated manual/model commands.
- Persist sampled history to SQLite and export generated datasets.

### Storage

SQLite stores sensor samples, device actions, conversations, trace events, preferences, and correction evidence. Current apartment state stays in memory because only one local process and user exist.

## Key decisions

- SSE over WebSocket: server primarily pushes ordered state and trace events; commands remain ordinary REST.
- SQLite over Redis/PostgreSQL: one local demo process needs persistence, not distributed coordination.
- Responses API over Chat Completions: assistant needs structured tools and reasoning in one workflow.
- Primitive local 3D geometry first: reliable demo without asset licensing or network loading.
- Supertonic over browser speech synthesis: explicit Vietnamese model/language selection and consistent local voice.
- faster-whisper over browser Vietnamese recognition: controlled local model, language, VAD, beam search, and vocabulary.
- No automatic device changes outside explicit scenario, manual, or assistant actions.

## Failure behavior

- Missing OpenAI key: disable assistant submission and show setup message.
- OpenAI timeout/error: emit failed trace event and keep room state unchanged.
- Invalid tool arguments: reject complete tool action; do not partially apply scene.
- SSE disconnect: web reconnects and fetches fresh snapshot before processing new events.
- WebGL unavailable: dashboard and accessible apartment status remain usable.
- Microphone unavailable: text input remains usable.
- Supertonic unavailable: final text remains visible and device actions remain complete.
