"""Parsers for the childCansat firmware serial protocol (115200 baud).

Commands: 's' status, 'd' dump CSV, 'e' erase log.
"""
import re
from dataclasses import dataclass

STATES = ("BOOT", "ARMED", "DESCENT", "LANDED")

CSV_HEADER = "idx,state,t_s,rel_alt_m,pressure_hPa,temp_C,humidity_pct,accel_g"
DUMP_END = "# end"

_STATUS_RE = re.compile(
    r"state=(\w+)\s+log=(\d+)/(\d+)\s+fault\(baro,imu,dht\)=([01])([01])([01])"
)
_HEADER_RE = re.compile(r"#\s*records=(\d+)/(\d+)\s+ground_Pa=(-?\d+)")


@dataclass
class Status:
    state: str
    log_count: int
    log_max: int
    baro_fault: bool
    imu_fault: bool
    dht_fault: bool


@dataclass
class DumpHeader:
    records: int
    capacity: int
    ground_pa: int


@dataclass
class Row:
    idx: int
    state: str
    t: float
    alt: float
    pressure: float
    temp: float
    hum: float
    accel: float

    def csv(self) -> str:
        return (f"{self.idx},{self.state},{self.t:.1f},{self.alt:.1f},"
                f"{self.pressure:.1f},{self.temp:g},{self.hum:g},{self.accel:.1f}")


def parse_status(line: str) -> Status | None:
    m = _STATUS_RE.search(line)
    if not m:
        return None
    return Status(m[1], int(m[2]), int(m[3]), m[4] == "1", m[5] == "1", m[6] == "1")


def parse_header(line: str) -> DumpHeader | None:
    m = _HEADER_RE.match(line)
    return DumpHeader(int(m[1]), int(m[2]), int(m[3])) if m else None


def parse_row(line: str) -> Row | None:
    p = line.strip().split(",")
    if len(p) != 8 or p[1] not in ("LANDED", "DESCENT"):
        return None
    try:
        return Row(int(p[0]), p[1], float(p[2]), float(p[3]), float(p[4]),
                   float(p[5]), float(p[6]), float(p[7]))
    except ValueError:
        return None
