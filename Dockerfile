FROM python:3.11.11-slim-bookworm AS piper-model

COPY scripts/fetch_piper_voice.py /tmp/fetch_piper_voice.py
RUN python /tmp/fetch_piper_voice.py /models

FROM node:22-bookworm-slim AS frontend

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN npm --prefix frontend ci
COPY frontend ./frontend
ENV NEXT_PUBLIC_API_URL="" \
    NEXT_PUBLIC_SPEECH_MODE=browser \
    NEXT_PUBLIC_TTS_MODE=backend
RUN npm --prefix frontend run build

FROM python:3.11.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    TTS_ENABLED=true \
    LOCAL_ASR_ENABLED=false \
    TTS_ENGINE=piper \
    TTS_MAX_CHARACTERS=800 \
    PIPER_MODEL_PATH=/app/models/vi_VN-vais1000-medium.onnx \
    PIPER_VOICE=vi_VN-vais1000-medium

RUN pip install --no-cache-dir uv==0.11.25

WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./backend/
RUN cd backend && uv sync --frozen --no-dev --no-install-project --extra piper

COPY --from=piper-model /models ./models

COPY backend ./backend
COPY data ./data
COPY THIRD_PARTY_NOTICES.md ./THIRD_PARTY_NOTICES.md
COPY --from=frontend /app/frontend/out ./frontend/out

ENV PATH="/app/backend/.venv/bin:$PATH"
WORKDIR /app/backend
EXPOSE 10000

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
