#!/usr/bin/env bash
set -euo pipefail

cleanup() {
  kill "$api_pid" "$web_pid" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

(
  cd backend
  uv run uvicorn app.main:app --reload --timeout-graceful-shutdown 2 --host 127.0.0.1 --port 8000
) &
api_pid=$!

npm --prefix frontend run dev &
web_pid=$!

wait -n "$api_pid" "$web_pid"
