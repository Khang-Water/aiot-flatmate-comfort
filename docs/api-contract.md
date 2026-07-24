# API contract

Base URL: `http://localhost:8000`. JSON uses snake_case. Times use ISO 8601 with timezone. Runtime source of truth will be FastAPI Pydantic models; schemas in `contracts/` lock Phase 0 intent.

## State and events

### `GET /api/health`

Returns service status, version, database readiness, simulation state, and whether OpenAI is configured. Never returns secrets.

### `GET /api/state`

Returns current `RoomSnapshot`.

### `GET /api/events`

SSE stream. Event names:

- `snapshot`: complete room snapshot after connection/reconnect.
- `state_changed`: changed paths plus resulting snapshot version.
- `trace`: one `AssistantTraceEvent`.
- `simulation`: clock, pause, speed, or scenario status.
- `error`: recoverable stream-level error.

Every event has monotonically increasing `sequence` for current process. Client detects gaps and refetches `/api/state`.

### `GET /api/history`

Query: `metric`, `from`, `to`, `limit`. Returns timestamp/value/unit points. Unknown metrics return `400`; limit is capped by backend.

## Simulation

### `GET /api/simulation`

Returns running state, speed, seed, simulated time, active scenario, and elapsed scenario minutes.

### `GET /api/scenarios`

Returns scenario summaries and active scenario ID.

### `POST /api/scenarios/{scenario_id}/activate`

Starts scenario from its declared initial state and timeline. Unknown ID returns `404`.

### `POST /api/simulation/control`

```json
{
  "action": "pause | resume | reset | set_speed",
  "speed": 1
}
```

`speed` is required only for `set_speed` and must be one of `1`, `2`, `5`, `10`.

## Device commands

### `POST /api/devices/{device_id}/commands`

```json
{
  "values": {"speed": 2},
  "source": "manual"
}
```

Backend validates complete command before mutation. Response contains command ID, changed paths, before/after values, and resulting snapshot version.

## Assistant

### `POST /api/assistant/requests`

```json
{
  "text": "Phòng hơi ngột ngạt.",
  "source": "voice",
  "session_id": "browser-session-id"
}
```

Returns `202` with `request_id`. Progress arrives as `trace` SSE events. Only one assistant request mutates room state at a time; overlapping request returns `409`.

Missing `OPENAI_API_KEY` returns `503 openai_not_configured`. Model or final-response failure leaves pending device targets unapplied.

Model tools:

- `get_room_snapshot()`
- `get_relevant_preferences(context)`
- `get_recent_actions(limit)`
- `set_room_scene(...)`
- focused setters for AC, fan, lights, purifier, curtain, humidity device, and plugs
- preference save/feedback tools

Phase 4 implements `get_room_snapshot`, `get_recent_actions`, and atomic `set_room_scene`. Preference tools arrive in Phase 6; trace currently marks preference retrieval as skipped.

`set_room_scene` omits unchanged devices. Backend enforces ranges from `plan.md` and rejects atomic scene when any supplied field is invalid.

## Vietnamese speech

### `POST /api/asr`

Accepts browser-recorded audio and transcribes Vietnamese locally with faster-whisper `large-v3-turbo`, forced `language="vi"`, smart-home hotwords, and VAD padding. CPU `int8` is the default for machines without an NVIDIA GPU. First use downloads approximately 1.6 GB of model files.

Multipart form with field `audio`. Accepted browser audio MIME types must begin with `audio/`; payload limit is 15 MB.

Returns:

```json
{
  "text": "Tắt điều hòa và đèn chính.",
  "language": "vi",
  "language_probability": 0.99,
  "duration_seconds": 2.4
}
```

Audio is transcribed locally by faster-whisper `small`, forced to Vietnamese, with VAD, beam search, and smart-apartment vocabulary bias. First use downloads model assets. Empty/unrecognized audio returns `422`; unavailable inference returns `503`.

### `POST /api/tts`

```json
{
  "text": "CO₂ đang ở mức 2418 ppm."
}
```

Returns `audio/wav` generated locally by Supertonic 3 with `lang="vi"`, 10 inference steps, and speed `1.15` by default. Before synthesis, FlatMate's app lexicon expands `%`, Kelvin, °C, CO₂, PM2.5, ppm, µg/m³, AC, AIoT, ASR, and TTS; VietNormalizer then expands numbers and Vietnamese reading forms.

Response headers include `X-Audio-Duration`, `X-TTS-Engine`, and `X-TTS-Voice`. Audio is not cached. First use downloads approximately 400 MB of model assets into the local Supertonic cache. Synthesis failure returns `503`; text response remains visible.

## History and preferences

- `GET /api/conversations`
- `GET /api/preferences`
- `POST /api/preferences`
- `PUT /api/preferences/{preference_id}`
- `DELETE /api/preferences/{preference_id}`
- `POST /api/preferences/reset-learned`

Explicit preferences outrank temporary and learned preferences. Reset removes learned records only and requires `{ "confirm": true }`.

Explicit and temporary preferences activate immediately. Temporary records require `expires_at`. When the LLM determines that a user correction expresses a useful preference, it creates or strengthens a learned preference and activates it immediately. Repeated matching evidence increases confidence. Applying a preference updates `last_used_at`.

## Error shape

```json
{
  "error": {
    "code": "invalid_device_value",
    "message": "Tốc độ quạt phải nằm trong khoảng 0–3.",
    "details": {"field": "speed", "value": 5}
  }
}
```
