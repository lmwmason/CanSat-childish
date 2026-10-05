"""Builds build/CanSatGroundStation.pyz - one file that runs on any machine with Python 3.10+ and
PyQt6 (Raspberry Pi included, no compiler needed).

    python tools/build_zipapp.py            (run from the guiTool folder)
"""
import shutil
import sys
import tempfile
import zipapp
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build" / "CanSatGroundStation.pyz"


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp) / "app"
        shutil.copytree(ROOT / "cansat_gui", stage / "cansat_gui",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copy(ROOT / "run_gui.py", stage / "__main__.py")
        OUT.parent.mkdir(parents=True, exist_ok=True)
        zipapp.create_archive(stage, OUT, interpreter="/usr/bin/env python3", compressed=True)
    OUT.chmod(0o755)
    print(f"built {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
