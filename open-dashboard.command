#!/bin/zsh
set -e

cd -- "$(dirname -- "$0")"
url="http://127.0.0.1:8765/dashboard.html"
server_pid=""

if ! curl --silent --fail "http://127.0.0.1:8765/database.csv" >/dev/null 2>&1; then
  python3 -m http.server 8765 --bind 127.0.0.1 &
  server_pid=$!
  trap 'kill "$server_pid" 2>/dev/null || true' EXIT INT TERM
  for attempt in {1..40}; do
    if curl --silent --fail "http://127.0.0.1:8765/database.csv" >/dev/null 2>&1; then
      break
    fi
    sleep 0.25
  done
fi

open "$url"

if [[ -n "$server_pid" ]]; then
  wait "$server_pid"
fi
