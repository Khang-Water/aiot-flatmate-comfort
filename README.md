# FlatMate Comfort

[![Deploy to Netlify](https://www.netlify.com/img/deploy/button.svg)](https://app.netlify.com/start/deploy?repository=https://github.com/Khang-Water/aiot-flatmate-comfort)

[Read the Vietnamese project report](https://khang-water.github.io/aiot-flatmate-comfort/)

FlatMate Comfort is an NT532 AIoT project that simulates a personalized one-bedroom smart apartment. Python generates sensor and device data; a responsive Vietnamese website renders a dimensioned 3D digital twin, accepts text or browser voice requests, shows observable assistant steps, provides a monitoring dashboard, and manages personalized preferences.

No physical devices are used. MQTT, ESP32, Home Assistant, Redis, PostgreSQL, alerts, authentication, and real-device integrations are outside scope.

## Current status

Current product includes deterministic simulation, SQLite history and structured preference memory, request-scoped SSE updates, a responsive one-bedroom digital twin, sensor/device overlays, context selection, a 24-hour dashboard, validated controls, MediaRecorder voice capture, local faster-whisper Vietnamese ASR, optional `Hey FlatMate` wake mode, offline VieNeu v3 Turbo Vietnamese speech with Supertonic fallback, guided demo commands, preference management, and conversation history. Invalid or failed assistant actions leave state unchanged. Without `OPENAI_API_KEY`, simulation, dashboard, manual controls, ASR, and TTS remain available.

Verified snapshot: 43 backend tests passed, 1 environment-dependent test skipped; Ruff, frontend domain checks, TypeScript, and production build passed.

## Stack

- Web: Next.js, TypeScript, responsive global CSS, React Three Fiber
- API: Python 3.11, FastAPI, Pydantic
- Live updates: Server-Sent Events (SSE)
- Storage: SQLite
- Data: deterministic Python-generated CSV and JSON scenarios
- Voice input: browser `MediaRecorder` + local faster-whisper `small` on CPU int8; browser recognition only handles optional `en-US` wake word
- Voice output: VietNormalizer + VieNeu v3 Turbo ONNX `int8` (voice `Mai Anh`) with Supertonic fallback
- AI: OpenAI Responses API with structured function tools

## Documents

- [Complete Vietnamese technical report](REPORT.md)
- [Word report](deliverables/FlatMate-Comfort-NT532-Technical-Report.docx)
- [Converted NT532 project instruction](docs/source/NT532-Project-Instruction.md)
- [Editable system architecture](docs/figures/flatmate-system-architecture.drawio)
- [Architecture preview](docs/figures/flatmate-system-architecture.png)
- [Product specification](docs/product-spec.md)
- [Architecture](docs/architecture.md)
- [UI and interaction flows](docs/ui-flows.md)
- [API contract](docs/api-contract.md)
- [Simulation design](docs/simulation-design.md)
- [Implementation phases](docs/phases.md)
- [Deployment](docs/deployment.md)

Original hardware-oriented proposal remains in [plan.md](plan.md) for reference. Approved simulation scope in `docs/` overrides hardware sections there.

The report intentionally leaves unknown student IDs/group-member details marked as missing instead of inventing them. Fill those fields before submission.

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

## Netlify

The deploy button publishes the Next.js frontend. Enter a public FastAPI URL when Netlify asks for
`NEXT_PUBLIC_API_URL`. The stateful Python simulation, SQLite, SSE, Whisper ASR, and offline TTS must
run on a separate persistent backend host. See [deployment instructions](docs/deployment.md).
