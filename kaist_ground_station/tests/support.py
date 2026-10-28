"""Test helper: a live-looking transport that plays a recording's received bytes by the service clock."""
import json

from kaist_ground_station.recording import DEMO_RECORDING


class RecordedKit:
    def __init__(self, clock, path=DEMO_RECORDING):
        self.clock, self.closed = clock, False
        self.written = []
        self.started = clock()
        self.rows = [(r["t"], bytes.fromhex(r["hex"])) for r in map(json.loads, path.read_text().splitlines())
                     if r.get("direction") == "rx"]
        self.at = 0

    def read(self):
        elapsed, out = self.clock() - self.started, b""
        while self.at < len(self.rows) and self.rows[self.at][0] <= elapsed:
            out += self.rows[self.at][1]
            self.at += 1
        return out

    def write(self, data):
        self.written.append(data)

    def close(self):
        self.closed = True

