# Implementation phases

Complete and verify one phase before starting the next.

Current delivery: Phases 0–6 implemented. Phase 5 still awaits manual microphone verification. Responsive layout and several Phase 7 UI tasks were completed early.

## Phase 0 — Product structure ✅

Create documents, contracts, configuration template, and directory ownership notes. No runnable app.

Acceptance:

- Every planned screen, subsystem, interface, scenario, failure state, and exclusion has one source document.
- JSON schemas parse successfully.
- No secrets, generated runtime data, or fake implementation files exist.

## Phase 1 — Runtime foundation ✅

Create Next.js and FastAPI applications, configuration loading, health endpoint, CORS, SSE heartbeat/snapshot, and local run commands.

Acceptance: browser renders one API-provided snapshot; reconnect works; frontend/backend checks pass.

## Phase 2 — Simulation and storage ✅

Implement state model, seeded generator, scenario loader, simulation clock, commands, history export, and SQLite persistence.

Acceptance: reset reproduces identical data; every sensor/device changes through validated paths; all ten scenarios run.

## Phase 3 — 3D apartment and dashboard ✅

Implement apartment visualization, resident animation, room and device locations, sensor overlays, dashboard tiles, device controls, 24-hour charts, and accessible fallback. Kitchen and bathroom are visual zones only; they have no automation.

Acceptance: state changes appear consistently in 3D, text status, charts, and controls; chart points support hourly hover; reduced-motion and WebGL fallback work.

## Phase 4 — OpenAI assistant and trace ✅

Implement Responses API request, structured tools, atomic validation, SSE trace, Vietnamese response, and error behavior.

Acceptance: representative text requests cause correct simulated changes; invalid/API-failed requests do not mutate state.

## Phase 5 — Browser voice ◐ Browser verification pending

Implement push-to-talk as the reliable primary flow, optional English wake-word recognition, Vietnamese command recognition, microphone controls, interim transcript, speech synthesis, and text fallback.

Implemented: localhost `MediaRecorder` + faster-whisper `small` Vietnamese ASR, VieNeu v3 Turbo + Supertonic local TTS, optional Web Speech `en-US` wake mode, and deployment mode using browser `SpeechRecognition` with backend Piper `vi_VN-vais1000-medium` TTS. Backend tests, TypeScript, production build, and Docker smoke test pass.

Acceptance:

- Push-to-talk captures a Vietnamese request in supported Chrome/Edge versions on `localhost` or HTTPS.
- `Hey FlatMate` can start capture when continuous browser recognition is available; voice use does not depend on it.
- Final transcript, microphone/transcribing state, press-once-to-start/press-again-to-submit control, and spoken Vietnamese response are visible.
- Permission denial, recognition failure, and unsupported browsers leave text input fully usable.

## Phase 6 — Preferences and history ✅

Implement SQLite-backed explicit, temporary, learned, edited, deleted, and scoped-reset flows. Add correction evidence, context-specific matching, expiry, and management UI.

Implemented: preference/evidence SQLite tables, validated API CRUD, explicit and temporary memory, expiry filtering, immediately active conversational correction memory, implicit feedback from manual overrides, three-observation promotion for `learned` candidates, assistant retrieval/save/correction tools, applied-preference tracking, and conversation history UI. Preference management remains available through the API; the dedicated end-user page was removed.

Acceptance:

- User can state a temporary or persistent preference and inspect its stored scope.
- A correction becomes evidence; when the LLM identifies a useful preference, it is saved and active immediately.
- Repeated matching evidence increases learned confidence.
- A manual override only becomes active memory after three identical targets follow matching assistant actions in the same context.
- Explicit preference wins over learned evidence and generic assistant behavior.
- Preference API can edit, delete, expire, or reset learned preferences without deleting conversation/device history.
- Assistant trace shows preference lookup and applied preference without exposing private model reasoning.

## Phase 7 — Integration and polish ◐ In progress

Finish guided demo, performance work, error/empty/loading states, representative end-to-end checks, and setup documentation. Responsive layout, larger typography, wide-screen use, touch targets, and responsive 3D camera are already complete.

Implemented: four-step guided demo commands, request-scoped SSE trace buffering, backend API error messages in the UI, reconnect warnings, runtime WebGL recovery UI, running-app smoke checks, an assistant integration test proving an LLM-selected correction is active on the next request, and an integration test proving repeated manual overrides promote implicit memory.

Acceptance:

- Clean local setup runs a complete Vietnamese voice-to-action demonstration.
- Text, push-to-talk, optional wake word, LLM tools, guardrails, simulation, charts, and preference memory work in one flow.
- Desktop, tablet, and mobile layouts have no horizontal overflow or inaccessible controls.
- Loading, disconnected, API failure, microphone denial, empty history, and WebGL failure paths remain usable.
- Automated backend, frontend, and representative browser-level checks pass.
