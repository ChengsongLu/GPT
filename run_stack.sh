#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_DIR="$ROOT_DIR/.runtime"
PID_DIR="$RUNTIME_DIR/pids"
LOG_DIR="$RUNTIME_DIR/logs"
PYTHON_BIN="${PYTHON_BIN:-python}"

cd "$ROOT_DIR"

if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  RUNNER=("$ROOT_DIR/.venv/bin/python")
else
  RUNNER=("$PYTHON_BIN")
fi
SPAWNER="${RUNNER[0]}"

mkdir -p "$PID_DIR" "$LOG_DIR"

usage() {
  cat <<'EOF'
Usage:
  ./run_stack.sh      Start backend + mock GitLab + mock Feishu
  ./run_stack.sh -e   Stop all services started by this script

Environment:
  PYTHON_BIN   Python interpreter to use if uv is unavailable. Default: python
EOF
}

is_running() {
  local pid="$1"
  kill -0 "$pid" >/dev/null 2>&1
}

start_service() {
  local name="$1"
  local pid_file="$2"
  local log_file="$3"
  shift 3

  if [[ -f "$pid_file" ]]; then
    local existing_pid
    existing_pid="$(cat "$pid_file")"
    if [[ -n "$existing_pid" ]] && is_running "$existing_pid"; then
      echo "$name already running (pid $existing_pid)"
      return
    fi
    rm -f "$pid_file"
  fi

  local started_pid
  started_pid="$(
    "$SPAWNER" - "$pid_file" "$log_file" "$ROOT_DIR" "$@" <<'PY'
import os
import subprocess
import sys

pid_file, log_file, root_dir, *cmd = sys.argv[1:]

env = os.environ.copy()

with open(log_file, "ab", buffering=0) as log_handle:
    process = subprocess.Popen(
        cmd,
        cwd=root_dir,
        stdin=subprocess.DEVNULL,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        env=env,
    )

with open(pid_file, "w", encoding="utf-8") as pid_handle:
    pid_handle.write(str(process.pid))

print(process.pid)
PY
  )"
  echo "Started $name (pid $started_pid)"
}

wait_for_http() {
  local name="$1"
  local url="$2"

  for _ in {1..30}; do
    if curl -fsS "$url" >/dev/null 2>&1; then
      echo "$name is healthy at $url"
      return 0
    fi
    sleep 0.5
  done

  echo "$name failed health check: $url"
  return 1
}

stop_service() {
  local name="$1"
  local pid_file="$2"
  local port="${3:-}"

  if [[ ! -f "$pid_file" ]]; then
    if [[ -n "$port" ]]; then
      stop_service_by_port "$name" "$port"
      return
    fi
    echo "$name not running"
    return
  fi

  local pid
  pid="$(cat "$pid_file")"
  if [[ -z "$pid" ]]; then
    rm -f "$pid_file"
    echo "$name pid file empty, cleaned"
    return
  fi

  if is_running "$pid"; then
    kill "$pid" >/dev/null 2>&1 || true
    for _ in {1..20}; do
      if ! is_running "$pid"; then
        break
      fi
      sleep 0.2
    done
    if is_running "$pid"; then
      kill -9 "$pid" >/dev/null 2>&1 || true
    fi
    echo "Stopped $name (pid $pid)"
  else
    echo "$name already stopped"
  fi

  rm -f "$pid_file"

  if [[ -n "$port" ]]; then
    stop_service_by_port "$name" "$port"
  fi
}

stop_service_by_port() {
  local name="$1"
  local port="$2"
  local pids
  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"

  if [[ -z "$pids" ]]; then
    return
  fi

  local pid
  for pid in $pids; do
    kill "$pid" >/dev/null 2>&1 || true
    for _ in {1..20}; do
      if ! is_running "$pid"; then
        break
      fi
      sleep 0.2
    done
    if is_running "$pid"; then
      kill -9 "$pid" >/dev/null 2>&1 || true
    fi
    echo "Stopped $name via port $port (pid $pid)"
  done
}

start_all() {
  start_service \
    "mock-gitlab" \
    "$PID_DIR/mock-gitlab.pid" \
    "$LOG_DIR/mock-gitlab.log" \
    "${RUNNER[@]}" run_mock_gitlab.py

  start_service \
    "mock-feishu" \
    "$PID_DIR/mock-feishu.pid" \
    "$LOG_DIR/mock-feishu.log" \
    "${RUNNER[@]}" run_mock_feishu.py

  GPT_RELOAD=0 start_service \
    "backend" \
    "$PID_DIR/backend.pid" \
    "$LOG_DIR/backend.log" \
    "${RUNNER[@]}" run_backend.py

  if ! wait_for_http "mock-gitlab" "http://127.0.0.1:19001/health"; then
    stop_all
    exit 1
  fi
  if ! wait_for_http "mock-feishu" "http://127.0.0.1:19002/health"; then
    stop_all
    exit 1
  fi
  if ! wait_for_http "backend" "http://127.0.0.1:18000/health"; then
    stop_all
    exit 1
  fi

  cat <<EOF

Services started.
Backend:      http://127.0.0.1:18000
Mock GitLab:  http://127.0.0.1:19001
Mock Feishu:  http://127.0.0.1:19002

Logs:
  $LOG_DIR/backend.log
  $LOG_DIR/mock-gitlab.log
  $LOG_DIR/mock-feishu.log
EOF
}

stop_all() {
  stop_service "backend" "$PID_DIR/backend.pid" 18000
  stop_service "mock-gitlab" "$PID_DIR/mock-gitlab.pid" 19001
  stop_service "mock-feishu" "$PID_DIR/mock-feishu.pid" 19002
}

main() {
  if [[ $# -gt 1 ]]; then
    usage
    exit 1
  fi

  if [[ $# -eq 1 ]]; then
    case "$1" in
      -e|--exit|--stop)
        stop_all
        exit 0
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        usage
        exit 1
        ;;
    esac
  fi

  start_all
}

main "$@"
