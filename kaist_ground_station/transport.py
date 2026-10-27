"""Nonblocking serial transport. The service owns lifecycle; UI never reads ports."""
from __future__ import annotations

import os
from typing import Callable, Protocol


class Transport(Protocol):
    """What StationService requires of a byte link (serial, BLE, TCP, ...).

    Implementations are created by a ``TransportFactory`` and owned by the service,
    which calls these methods from its single tick thread.
    """

    def read(self) -> bytes:
        """Return bytes received since the last call; ``b""`` when none. Must not block."""

    def write(self, data: bytes) -> None:
        """Send all of ``data`` or raise ``OSError``. Partial writes are errors, not retried."""

    def close(self) -> None:
        """Release the link. Must be safe to call once after any failure."""


# Called as factory(port, baud). Adapters whose address is not a serial port/baud
# pair should interpret these two arguments themselves until the connect input is generalised.
TransportFactory = Callable[[str, int], Transport]



class SerialTransport:  # implements Transport
    def __init__(self, port: str, baud: int = 115200):
        import serial
        # exclusive locking is POSIX-only in pyserial (Linux/macOS/Raspberry Pi); Windows ports are exclusive anyway
        extra = {"exclusive": True} if os.name == "posix" else {}
        self.port = serial.Serial(port, baudrate=baud, bytesize=8, parity="N", stopbits=1,
                                  timeout=0, write_timeout=0.25, rtscts=False, dsrdtr=False,
                                  xonxoff=False, **extra)

    def read(self) -> bytes:
        return self.port.read(min(self.port.in_waiting, 65536))

    def write(self, data: bytes) -> None:
        count = self.port.write(data)
        if count != len(data):
            raise OSError(f"Partial serial write: {count}/{len(data)}; command not retried")

    def close(self) -> None:
        self.port.close()


def list_ports() -> list[tuple[str, str]]:
    from serial.tools import list_ports as serial_ports
    return [(p.device, p.description) for p in serial_ports.comports()]


# Register new link types here; the UI and --transport list these names.
# A factory receives the "port" and "baud" fields as entered, whatever they mean for that link.
TRANSPORTS: dict[str, TransportFactory] = {"serial": SerialTransport}
