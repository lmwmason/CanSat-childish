#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
conda_bin="${CONDA_EXE:-$(command -v conda || true)}"
if [[ -z "$conda_bin" ]]; then
  echo 'Conda가 필요합니다. 설치 후 이 스크립트를 다시 실행하세요.' >&2
  exit 1
fi
if [[ ! -x fire_spread/.windninja/bin/WindNinja_cli ]]; then
  "$conda_bin" create --prefix "$PWD/fire_spread/.windninja" --override-channels -c conda-forge windninja=3.13.0.1 --yes
fi
if [[ ! -x fire_spread/.venv/bin/python ]]; then python3 -m venv fire_spread/.venv; fi
fire_spread/.venv/bin/python -m pip install -r fire_spread/requirements.txt
