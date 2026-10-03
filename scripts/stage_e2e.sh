#!/usr/bin/env bash
# Runs frontend/tests/e2e/stage-demo.spec.ts against a fresh backend (:8301) and console (:5301) started with the
# stage flag set (Makefile STAGE_FLAGS) and no AI keys, STAGE_RUNS times (default 1), then stops both servers.
set -eu -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PORT="${STAGE_BACKEND_PORT:-8301}"
CONSOLE_PORT="${STAGE_CONSOLE_PORT:-5301}"
RUNS="${STAGE_RUNS:-1}"
FLAGS="${STAGE_FLAGS:?run it through make stage-e2e, which passes STAGE_FLAGS}"
# sim (default): both AI keys blanked, every badge reads SIMULATED. live: the keys of .env are used with the stage Gemini
# model, and the spec asserts LIVE · gemini on the slip and on a free question.
AI="${STAGE_E2E_AI:-sim}"
GEMINI="${STAGE_GEMINI_MODEL:-gemini-2.5-flash-lite}"
case "$AI" in sim | live) ;; *) echo "STAGE_E2E_AI must be sim or live" >&2; exit 1 ;; esac
for port in "$BACKEND_PORT" "$CONSOLE_PORT"; do
  if ss -ltn 2>/dev/null | grep -qE "[:.]$port "; then echo "port $port is already in use: stop what runs there first" >&2; exit 1; fi
done
PGIDS=()
# Each server runs in its own process group (setsid, then exec) so that stopping it also stops the node or python child.
stop_all() { for pgid in "${PGIDS[@]:-}"; do [ -n "$pgid" ] && kill -- "-$pgid" 2>/dev/null || true; done; }
trap stop_all EXIT INT TERM

# The e2e backend never touches the real Telegram bot: one poller per token (the dev server's), and no test messages.
if [ "$AI" = live ]; then AI_ENV=(GEMINI_MODEL="$GEMINI" TELEGRAM_BOT_TOKEN=); else AI_ENV=(SARVAM_API_KEY= GOOGLE_API_KEY= TELEGRAM_BOT_TOKEN=); fi
setsid bash -c 'cd "$1/backend" && exec env CHHATRI_FEATURES="$2" CHHATRI_DATA_IS_SYNTHETIC=true "${@:4}" \
  .venv/bin/python -m uvicorn --factory chhatri.api.app:create_app --host 127.0.0.1 --port "$3"' _ "$ROOT" "$FLAGS" "$BACKEND_PORT" "${AI_ENV[@]}" >/dev/null 2>&1 &
PGIDS+=($!)
setsid bash -c 'cd "$1/frontend" && exec env VITE_FEATURES="$2" VITE_API_URL="http://127.0.0.1:$3" \
  npm run dev -- --host 127.0.0.1 --port "$4" --strictPort' _ "$ROOT" "$FLAGS" "$BACKEND_PORT" "$CONSOLE_PORT" >/dev/null 2>&1 &
PGIDS+=($!)

for _ in $(seq 1 60); do
  curl -fs "http://127.0.0.1:$BACKEND_PORT/api/health" >/dev/null 2>&1 && curl -fs "http://127.0.0.1:$CONSOLE_PORT/" >/dev/null 2>&1 && break
  sleep 1
done
curl -fs "http://127.0.0.1:$BACKEND_PORT/api/health" >/dev/null || { echo "backend did not start" >&2; exit 1; }

cd "$ROOT/frontend"
for run in $(seq 1 "$RUNS"); do
  echo "== stage run $run of $RUNS"
  E2E_FEATURES="$FLAGS" STAGE_AI="$AI" STAGE_API_URL="http://127.0.0.1:$BACKEND_PORT" CONSOLE_URL="http://127.0.0.1:$CONSOLE_PORT" \
    npx playwright test --project=live --workers=1 stage-demo
done
