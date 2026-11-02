#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x fire_spread/.venv/bin/python ]]; then
  echo '먼저 bash fire_spread/setup.sh 를 실행하세요.' >&2
  exit 1
fi
export WINDNINJA_CLI="${WINDNINJA_CLI:-$PWD/fire_spread/.windninja/bin/WindNinja_cli}"
exec fire_spread/.venv/bin/python -m fire_spread
