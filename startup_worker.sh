#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_ROOT="${APP_PATH:-$SCRIPT_DIR}"
if [[ ! -f "$APP_ROOT/app.py" && -f "/home/site/wwwroot/app.py" ]]; then
  APP_ROOT="/home/site/wwwroot"
fi

cd "$APP_ROOT"

APP_VENV_ROOT="$APP_ROOT/antenv"
if command -v python3 >/dev/null 2>&1; then
  HEALTH_PYTHON_BIN="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  HEALTH_PYTHON_BIN="$(command -v python)"
else
  HEALTH_PYTHON_BIN="$APP_VENV_ROOT/bin/python"
fi

if [[ -x "$APP_VENV_ROOT/bin/python" ]] && "$APP_VENV_ROOT/bin/python" -V >/dev/null 2>&1; then
  export PATH="$APP_VENV_ROOT/bin:${PATH:-}"
  WORKER_PYTHON_BIN="$APP_VENV_ROOT/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  WORKER_PYTHON_BIN="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  WORKER_PYTHON_BIN="$(command -v python)"
else
  WORKER_PYTHON_BIN="$HEALTH_PYTHON_BIN"
fi
export PYTHONPATH="$APP_ROOT:${PYTHONPATH:-}"

RUN_DIR="${WORKER_RUN_DIR:-$APP_ROOT/run}"
LOG_DIR="${WORKER_LOG_DIR:-/home/LogFiles}"
mkdir -p "$RUN_DIR" "$LOG_DIR"

WORKER_MODE="$(echo "${WORKER_MODE:-both}" | tr '[:upper:]' '[:lower:]')"

start_supervised_worker() {
  local name="$1"
  local log_file="$2"
  shift 2

  (
    while true; do
      "$@" >> "$log_file" 2>&1
      local exit_code=$?
      echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') [$name] exited with code $exit_code; restarting in 2s" >> "$log_file"
      sleep 2
    done
  ) &
}

case "$WORKER_MODE" in
  upload)
    echo "Starting DBDE upload worker..."
    start_supervised_worker \
      "upload-worker" \
      "$LOG_DIR/upload-worker.log" \
      "$WORKER_PYTHON_BIN" upload_worker.py --batch-size "${UPLOAD_WORKER_BATCH_SIZE:-4}" --poll-seconds "${UPLOAD_WORKER_POLL_SECONDS:-2.5}"
    ;;
  export)
    echo "Starting DBDE export worker..."
    start_supervised_worker \
      "export-worker" \
      "$LOG_DIR/export-worker.log" \
      "$WORKER_PYTHON_BIN" export_worker.py --batch-size "${EXPORT_WORKER_BATCH_SIZE:-3}" --poll-seconds "${EXPORT_WORKER_POLL_SECONDS:-2.0}"
    ;;
  both)
    echo "Starting DBDE upload + export workers..."
    start_supervised_worker \
      "upload-worker" \
      "$LOG_DIR/upload-worker.log" \
      "$WORKER_PYTHON_BIN" upload_worker.py --batch-size "${UPLOAD_WORKER_BATCH_SIZE:-4}" --poll-seconds "${UPLOAD_WORKER_POLL_SECONDS:-2.5}"
    start_supervised_worker \
      "export-worker" \
      "$LOG_DIR/export-worker.log" \
      "$WORKER_PYTHON_BIN" export_worker.py --batch-size "${EXPORT_WORKER_BATCH_SIZE:-3}" --poll-seconds "${EXPORT_WORKER_POLL_SECONDS:-2.0}"
    ;;
  *)
    echo "Invalid WORKER_MODE='$WORKER_MODE' (expected upload|export|both)" >&2
    exit 1
    ;;
esac

echo "Starting worker health host on port ${PORT:-8000}..."
exec "$HEALTH_PYTHON_BIN" worker_health_server.py
