#!/usr/bin/env bash
# Launcher for the KAIST CanSat ground station. Works from any directory.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"                      # the package is run as `python -m kaist_ground_station` from here

usage() {
  cat <<'EOF'
Usage: run.sh [command] [options]

  (none)                 connect to the kit automatically (USB serial adapter) and open both windows.
                         If no adapter is found, the UI still opens so you can pick a port by hand.
  live [PORT [BAUD]]     same, optionally with an explicit port, e.g.  run.sh live /dev/rfcomm0
                         Real-hardware sessions are logged under log/kaist-ground-station/hardware/sessions
  demo                   replay the bundled example recording (synthetic; GPS only climbs, so no drift estimate)
  mock [opts]            real GoPro descent + synthetic IMU/ATLM, fills every panel
                           --image FILE.jpg   show a test camera image    --speed N   playback speed
                           --loop             repeat                     --csv FILE  other GPS CSV
  replay FILE            replay a recorded session's traffic.jsonl (receive only)
  headless [opts]        capture without a window:  run.sh headless --port /dev/ttyUSB0 --duration 60
  tk                     the old Tk desktop window instead of the browser UI
  test                   run the unit tests
  help                   this text

Anything else is passed straight to `python -m kaist_ground_station`, e.g.
  run.sh --port /dev/rfcomm0 --ui-config my.cfg
Set PYTHON=/path/to/python to choose the interpreter (a .venv next to this script is used if present).
Settings (language, colours, fonts, alarm limits, checkpoint buttons, windows to open): config/ui.cfg
EOF
}

# interpreter: $PYTHON, else the package's own .venv, else python3
if [[ -n "${PYTHON:-}" ]]; then PY="$PYTHON"
elif [[ -x "$HERE/.venv/bin/python" ]]; then PY="$HERE/.venv/bin/python"
else PY="python3"; fi
command -v "$PY" >/dev/null 2>&1 || { echo "error: Python not found ($PY). Set PYTHON=/path/to/python." >&2; exit 1; }

need() {   # need MODULE... : fail with the install command instead of a stack trace
  local missing=()
  for m in "$@"; do "$PY" -c "import $m" 2>/dev/null || missing+=("$m"); done
  if ((${#missing[@]})); then
    echo "error: missing Python module(s): ${missing[*]}" >&2
    echo "install with:  $PY -m pip install -r \"$HERE/requirements.txt\"" >&2
    exit 1
  fi
}

cd "$ROOT"
cmd="${1:-}"
case "$cmd" in
  help|-h|--help) usage; exit 0 ;;
  ""|live)        [[ "$cmd" == live ]] && shift
                  need numpy PIL serial
                  port="${1:-}"
                  [[ -n "$port" ]] || port="$("$PY" -m kaist_ground_station.autodetect 2>/dev/null || true)"
                  if [[ -z "$port" ]]; then
                    echo "no serial adapter found: opening the UI unconnected (plug it in, or run.sh live /dev/ttyUSB0)" >&2
                    exec "$PY" -m kaist_ground_station
                  fi
                  echo "connecting to $port" >&2
                  exec "$PY" -m kaist_ground_station --port "$port" --baud "${2:-115200}" --log-dir "$ROOT/log/kaist-ground-station/hardware/sessions" ;;
  demo)           shift; need numpy PIL serial; exec "$PY" -m kaist_ground_station --demo "$@" ;;
  mock)           shift; need numpy PIL serial; exec "$PY" -m kaist_ground_station.tools.mock_web "$@" ;;
  replay)         shift; [[ $# -ge 1 ]] || { echo "error: replay needs a traffic.jsonl path" >&2; exit 2; }
                  [[ -f "$1" ]] || { echo "error: file not found: $1" >&2; exit 2; }
                  need numpy PIL serial
                  exec "$PY" -m kaist_ground_station --replay "$@" ;;
  headless)       shift; need numpy PIL serial; exec "$PY" -m kaist_ground_station --headless "$@" ;;
  tk)             shift; need numpy PIL serial matplotlib tkinter; exec "$PY" -m kaist_ground_station --frontend tk "$@" ;;
  test)           shift; need numpy PIL serial; exec "$PY" -m unittest discover -s kaist_ground_station/tests -t . "$@" ;;
  -*)             need numpy PIL serial; exec "$PY" -m kaist_ground_station "$@" ;;
  *)              echo "error: unknown command '$cmd'" >&2; echo >&2; usage >&2; exit 2 ;;
esac
