"""Find the kit's serial port without asking: `--port auto`, the launcher and the UI's port box use this.

Ranking, best first: real USB serial adapters (they carry a USB vendor id: FTDI, CP210x, CH340 ...),
then Bluetooth RFCOMM, then anything else. Linux's /dev/ttyS* are the motherboard's legacy UART slots;
they are never the kit and would otherwise bury the real port, so they are left out. A port such as a
Raspberry Pi GPIO UART can still be given explicitly with --port.
"""
from __future__ import annotations

import re

_LEGACY = re.compile(r"^/dev/ttyS\d+$")
_RFCOMM = re.compile(r"(rfcomm|Bluetooth)", re.I)


def ranked_ports() -> list[tuple[str, str]]:
    """[(device, description)] most likely kit first."""
    from serial.tools import list_ports
    scored = []
    for p in list_ports.comports():
        if _LEGACY.match(p.device) and p.vid is None:
            continue
        if p.vid is not None:
            rank = 0
        elif _RFCOMM.search(p.device) or _RFCOMM.search(p.description or ""):
            rank = 1
        else:
            rank = 2
        scored.append((rank, p.device, p.description or ""))
    return [(device, description) for _, device, description in sorted(scored)]


def detect_port() -> str | None:
    ports = ranked_ports()
    return ports[0][0] if ports else None


if __name__ == "__main__":          # used by run.sh: prints the port, exits 1 when there is none
    found = detect_port()
    if found:
        print(found)
    raise SystemExit(0 if found else 1)
