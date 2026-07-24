# FlatMate Comfort

FlatMate Comfort is a local smart-apartment simulation. Python generates sensor and device data; a responsive Vietnamese website renders a 3D apartment, accepts text or browser voice requests, shows observable assistant steps, provides a monitoring dashboard, and manages personalized preferences.

No physical devices are used. MQTT, ESP32, Home Assistant, Redis, PostgreSQL, alerts, authentication, and real-device integrations are outside scope.

## Current status

Phases 0–6 are implemented and Phase 7 integration is in progress. Phase 5 browser voice still awaits manual microphone verification. Current product includes deterministic simulation, SQLite history and preference memory, request-scoped SSE updates, responsive 3D apartment, sensor/device overlays, context selection, a 24-hour dashboard, validated controls, MediaRecorder voice capture, local faster-whisper Vietnamese ASR, optional `Hey FlatMate` wake mode, VietNormalizer text normalization, local Supertonic 3 Vietnamese speech, guided demo commands, preference management, and conversation history. Invalid or failed assistant actions leave state unchanged. Without `OPENAI_API_KEY`, simulation and dashboard still run while assistant shows setup guidance.

Next: manually verify microphone behavior, add browser-level smoke checks, then finish Phase 7 performance and failure-path work. Responsive layout and first guided-demo integration pass are complete.

## Planned stack

- Web: Next.js, TypeScript, responsive global CSS, React Three Fiber
- API: Python 3.11, FastAPI, Pydantic
- Live updates: Server-Sent Events (SSE)
- Storage: SQLite
- Data: deterministic Python-generated CSV and JSON scenarios
- Voice input: browser `MediaRecorder` + local faster-whisper `large-v3-turbo` on CPU int8; browser recognition only handles optional `en-US` wake word
- Voice output: VietNormalizer + local Supertonic 3 (`lang="vi"`, voice `F1`, 10 steps, speed `1.15` by default)
- AI: OpenAI Responses API with structured function tools

## Documents

- [Product specification](docs/product-spec.md)
- [Architecture](docs/architecture.md)
- [UI and interaction flows](docs/ui-flows.md)
- [API contract](docs/api-contract.md)
- [Simulation design](docs/simulation-design.md)
- [Implementation phases](docs/phases.md)

Original hardware-oriented proposal remains in [plan.md](plan.md) for reference. Approved simulation scope in `docs/` overrides hardware sections there.

## Local setup

Requirements: Node.js 20+, npm, Python 3.11+, and `uv`.

```bash
cp .env.example .env
make install
make dev
```

Open `http://localhost:3000`. API runs at `http://localhost:8000`; API reference is available at `http://localhost:8000/docs`.

- `http://localhost:3000`: 3D apartment digital twin
- `http://localhost:3000/dashboard`: monitoring and control dashboard
- `http://localhost:3000/history`: recent assistant conversations

Run project checks:

```bash
make check
```

With `make dev` running, verify API, guardrail, SSE, and all web routes:

```bash
make smoke
```
