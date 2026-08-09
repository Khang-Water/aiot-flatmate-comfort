FROM node:22-bookworm-slim AS frontend

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN npm --prefix frontend ci
COPY frontend ./frontend
ENV NEXT_PUBLIC_API_URL="" \
    NEXT_PUBLIC_SPEECH_MODE=browser
RUN npm --prefix frontend run build

FROM python:3.11.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    LOCAL_SPEECH_ENABLED=false

RUN pip install --no-cache-dir uv==0.11.25

WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./backend/
RUN cd backend && uv sync --frozen --no-dev --no-install-project

COPY backend ./backend
COPY data ./data
COPY --from=frontend /app/frontend/out ./frontend/out

ENV PATH="/app/backend/.venv/bin:$PATH"
WORKDIR /app/backend
EXPOSE 10000

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
