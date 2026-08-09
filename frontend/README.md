# Frontend

Next.js TypeScript digital twin and assistant console. Phase 4 adds Vietnamese text requests, OpenAI configuration state, observable tool/validation/action trace, and final response display.

Current modules:

```text
src/
├── app/                 3D home, dashboard, layout, global styles
├── components/
│   ├── apartment/       Three.js studio and animated entities
│   ├── assistant/       request form and safe trace timeline
│   └── dashboard/       device controls and SVG history chart
├── hooks/               shared REST/SSE state hook
├── lib/                 API helpers and Vietnamese labels
└── types/               room and simulation API mirrors
```

Run from repository root with `make web`.

- `NEXT_PUBLIC_SPEECH_MODE=local`: captures with `MediaRecorder` and uploads audio to `/api/asr`.
- `NEXT_PUBLIC_SPEECH_MODE=browser`: captures through `SpeechRecognition` with `vi-VN`.
- `NEXT_PUBLIC_TTS_MODE=backend`: requests WAV from `/api/tts`; used by localhost and Render Piper deployment.
- `NEXT_PUBLIC_TTS_MODE=browser`: optional fallback using `speechSynthesis` and an installed `vi`/`vi-VN` voice.
