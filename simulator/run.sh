#!/usr/bin/env bash
# One-shot build + run helper for the CanSat-childish firmware sims.
#
# Usage:
#   ./run.sh                # build, then interactive menu
#   ./run.sh mother          # build + run the mothership sim
#   ./run.sh child [1|2|3]   # build + run a child satellite sim (default 1)
#   ./run.sh test            # build + run the headless failsafe test
#   ./run.sh viz             # run the Python live 3D telemetry viewer
#   ./run.sh all              # build, then launch mother + 3 children + the
#                             # 3D viewer together (tmux panes if tmux is
#                             # installed, otherwise separate terminal
#                             # windows, otherwise prints the commands to
#                             # run by hand)
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

echo "== building =="
make >/dev/null
echo "== build OK =="

# All vehicles in one flight must fly through the SAME randomized wind/
# weather (see sim_env_init() in sim/sim_world.c) - so this one run.sh
# invocation rolls one fresh seed and exports it to everything it
# launches below. To reproduce a specific flight, or to share it across
# sims started in separate terminals by hand, export CANSAT_WIND_SEED
# yourself to the same value before running each one.
if [ -z "${CANSAT_WIND_SEED:-}" ]; then
    export CANSAT_WIND_SEED="$RANDOM$RANDOM$RANDOM"
    echo "== randomized environment: CANSAT_WIND_SEED=$CANSAT_WIND_SEED =="
fi

run_mother() { exec ./build/mother_sim; }
run_child()  { exec ./build/child_sim "${1:-1}"; }
run_test()   { make build/test_core >/dev/null; exec ./build/test_core; }

have_python_viz() {
    command -v python3 >/dev/null 2>&1 && python3 -c "import matplotlib, numpy" >/dev/null 2>&1
}

run_viz() {
    if ! have_python_viz; then
        echo "python3 + matplotlib/numpy not found - install with:" >&2
        echo "  pip install -r viz/requirements.txt" >&2
        exit 1
    fi
    exec python3 viz/visualize.py
}

try_terminal_for() {
    # $1 = window title, $2.. = command to run
    local title="$1"; shift
    if command -v tmux >/dev/null 2>&1 && [ -n "${TMUX:-}" ]; then
        tmux split-window -h "$*"; return 0
    fi
    if command -v gnome-terminal >/dev/null 2>&1; then
        gnome-terminal --title="$title" -- bash -c "$*; exec bash" && return 0
    fi
    if command -v konsole >/dev/null 2>&1; then
        konsole --hold -e bash -c "$*" && return 0
    fi
    if command -v xterm >/dev/null 2>&1; then
        xterm -T "$title" -hold -e bash -c "$*" && return 0
    fi
    return 1
}

run_all() {
    local with_viz=0
    have_python_viz && with_viz=1
    [ "$with_viz" -eq 0 ] && echo "(no matplotlib/numpy found - skipping the 3D viewer pane; see viz/requirements.txt)"

    # Embed the seed directly in each pane's command rather than relying
    # on tmux to inherit it: if the tmux server was already running from
    # before this shell exported CANSAT_WIND_SEED, new panes would
    # otherwise inherit the server's older environment instead.
    local seeded="env CANSAT_WIND_SEED=$CANSAT_WIND_SEED"

    if command -v tmux >/dev/null 2>&1; then
        echo "== launching mother + 3 children$([ $with_viz -eq 1 ] && echo ' + 3D viewer') in a tmux session 'cansat' =="
        tmux kill-session -t cansat 2>/dev/null || true
        tmux new-session -d -s cansat -n fleet "$seeded ./build/mother_sim"
        tmux split-window -h -t cansat:fleet "$seeded ./build/child_sim 1"
        tmux split-window -v -t cansat:fleet.0 "$seeded ./build/child_sim 2"
        tmux split-window -v -t cansat:fleet.1 "$seeded ./build/child_sim 3"
        if [ "$with_viz" -eq 1 ]; then
            tmux split-window -v -t cansat:fleet.2 "python3 viz/visualize.py"
        fi
        tmux select-layout -t cansat:fleet tiled
        exec tmux attach -t cansat
    fi

    echo "tmux not found - trying separate terminal windows..."
    local ok=0
    try_terminal_for "mothership"  "cd '$PWD' && $seeded ./build/mother_sim"  && ok=1
    try_terminal_for "child-1"     "cd '$PWD' && $seeded ./build/child_sim 1" && ok=1
    try_terminal_for "child-2"     "cd '$PWD' && $seeded ./build/child_sim 2" && ok=1
    try_terminal_for "child-3"     "cd '$PWD' && $seeded ./build/child_sim 3" && ok=1
    if [ "$with_viz" -eq 1 ]; then
        try_terminal_for "3d-viz" "cd '$PWD' && python3 viz/visualize.py" && ok=1
    fi

    if [ "$ok" -eq 0 ]; then
        cat <<EOF

No tmux and no known terminal emulator found. Each sim needs its own
foreground terminal for keyboard input, so open terminals and run:

  ./build/mother_sim
  ./build/child_sim 1
  ./build/child_sim 2
  ./build/child_sim 3
  python3 viz/visualize.py
EOF
    fi
}

menu() {
    echo
    echo "  1) mothership sim"
    echo "  2) child satellite sim"
    echo "  3) headless failsafe test"
    echo "  4) live 3D visualizer (Python)"
    echo "  5) all (mother + 3 children + 3D viewer)"
    echo "  q) quit"
    read -rp "> " choice
    case "$choice" in
        1) run_mother ;;
        2) read -rp "which child (1-3)? [1] " idx; run_child "${idx:-1}" ;;
        3) run_test ;;
        4) run_viz ;;
        5) run_all ;;
        q|Q) exit 0 ;;
        *) echo "unknown choice"; menu ;;
    esac
}

case "${1:-}" in
    mother) run_mother ;;
    child)  run_child "${2:-1}" ;;
    test)   run_test ;;
    viz)    run_viz ;;
    all)    run_all ;;
    "")     menu ;;
    *) echo "unknown argument: $1" >&2; exit 1 ;;
esac
