# Deployment

## Netlify frontend

Use the deploy button in the root README. Netlify reads `netlify.toml`, installs the frontend from
`frontend/`, and builds the Next.js static export in `frontend/out` with Node.js 20.

Set this template environment variable during deployment:

```text
NEXT_PUBLIC_API_URL=https://your-public-api.example.com
```

Use no trailing slash. The frontend build succeeds without this value, but browser features that need
simulation state, SSE, assistant requests, ASR, or TTS cannot work until a public backend URL is set.

After Netlify assigns the production site URL, configure the backend with the exact origin:

```text
WEB_ORIGIN=https://your-site.netlify.app
```

Restart the backend after changing `WEB_ORIGIN`. Netlify deploy previews use different origins; the
current backend intentionally allows one exact web origin.

## Why the backend is separate

The FastAPI backend is not suitable for Netlify Functions. It owns a long-running deterministic
simulation, Server-Sent Events, SQLite state, and local ASR/TTS models. The Whisper model alone is about
1.6 GB. Deploy the backend on a persistent VM or container service such as Render, Railway, Fly.io, or a
small VPS, then pass its HTTPS URL to Netlify.

Required backend persistence and resources:

- Python 3.11 and `uv`
- writable persistent volume for `data/flatmate.db`
- enough RAM and disk for faster-whisper `large-v3-turbo` and Supertonic
- HTTPS endpoint that supports long-lived SSE connections
- environment values from `.env.example`

Do not place `OPENAI_API_KEY` in Netlify frontend environment variables. Keep it only on the backend.
