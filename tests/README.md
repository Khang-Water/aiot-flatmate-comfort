# Verification ownership

Tests arrive with each implementation phase. Phase 4 also covers Responses tool-loop replay, delayed scene commit, missing-key behavior, vague-request limits, trace persistence, and zero mutation after final API failure.

Required coverage:

- Contract and boundary validation.
- Deterministic simulation and scenario lifecycle.
- Context inference and device effects.
- SQLite history, explicit/correction preference behavior, and implicit promotion after repeated manual overrides.
- SSE ordering, gaps, and reconnect.
- OpenAI tool loop with mocked API responses.
- No state mutation after model, validation, or transport failure.
- Frontend state synchronization, accessibility, reduced motion, and WebGL fallback.
- English wake phrase followed by Vietnamese command capture in local and browser speech modes.
- End-to-end representative requests from `plan.md`.
