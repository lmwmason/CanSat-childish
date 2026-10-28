"""Application service shared by the GUI and headless tools.

Single owner/event-loop model: call tick() at 20–50 Hz. UI consumes independent
snapshots; transport, parsing, calibration, persistence and command policy live
here. Transport and clocks can be injected for hardware-free integration tests.
"""
from __future__ import annotations

from collections import deque
import copy
from dataclasses import dataclass
from pathlib import Path
import time

from .models import Calibration, Telemetry, load_calibration
from .protocol import Frame, StreamParser, digital_command, time_command
from .recording import NullRecorder, Recorder, Replay
from .transport import TRANSPORTS, Transport, TransportFactory


@dataclass(frozen=True)
class Snapshot:
    mode: str
    source: str
    telemetry: Telemetry
    calibration: tuple
    analog_values: tuple
    rx_bytes: int
    tx_bytes: int
    valid_frames: int
    errors: int
    discarded: int
    link_age_s: float | None
    now: float
    log_directory: str
    notices: tuple
    terminal: tuple
    can_transmit: bool


class StationService:
    def __init__(self, log_root: Path, clock=time.monotonic, transport_factory: TransportFactory | None = None,
                 auto_record: bool = True):
        self.log_root = Path(log_root)
        self.auto_record = auto_record      # True: every session is recorded from its first byte (the original behaviour)
        self.clock = clock
        self.transport_factory = transport_factory  # test override; wins over the kind registry
        self.mode = "IDLE"
        self.source = ""
        self.transport: Transport | None = None
        self.replay = None
        self.recorder = None
        self.rec_origin = None              # clock value that recorded times are measured from
        self.log_directory = ""
        self.calibration = tuple(Calibration() for _ in range(8))
        self.calibration_path = ""
        self.notices = deque(maxlen=150)
        self.terminal = deque(maxlen=30)
        self._reset()

    def _reset(self):
        self.parser = StreamParser()
        self.telemetry = Telemetry()
        self.rx_bytes = self.tx_bytes = 0
        self.last_frame = None
        self.started = self.clock()
        self.last_flush = self.started
        self.tx_enabled = False
        self.notices.clear()
        self.terminal.clear()

    def notice(self, text):
        self.notices.append((self.clock(), text))

    def configure_calibration(self, path: Path):
        if self.mode in ("LIVE", "REPLAY"):
            raise ValueError("Stop the session before changing calibration")
        self.calibration = load_calibration(path)
        self.calibration_path = str(path)
        self.notice(f"Calibration loaded: {path}")

    def _start(self, mode, source):
        self.stop()
        self._reset()
        self.mode, self.source = mode, source
        self.recorder, self.log_directory, self.rec_origin = NullRecorder(), "", None
        if self.auto_record:
            try:
                self._begin_recording(self.started)     # recording from the first byte: same time base as before
            except OSError:
                self.mode = "IDLE"
                raise
            self.notice(f"{mode}: {source}; recording started")
        else:
            self.notice(f"{mode}: {source}; not recording (start it explicitly)")

    # -- recording is separate from the session: a session can be watched without being kept ----------------
    @property
    def recording(self) -> bool:
        return isinstance(self.recorder, Recorder)

    def _begin_recording(self, origin: float | None = None):
        self.recorder = Recorder(self.log_root, self.mode, self.source, self.calibration)
        self.log_directory = str(self.recorder.directory)
        # recorded times start at 0 here, so a replay of a late-started recording does not wait out the gap
        self.rec_origin = self.clock() if origin is None else origin

    def start_recording(self):
        if self.mode == "IDLE":
            raise ValueError("Start a session (connect or replay) before recording")
        if self.recording:
            raise ValueError("Already recording")
        self._begin_recording()
        self.notice(f"Recording started: {self.log_directory}")

    def stop_recording(self):
        if not self.recording:
            raise ValueError("Not recording")
        directory = self.log_directory
        self.recorder.close()
        self.recorder, self.log_directory, self.rec_origin = NullRecorder(), "", None
        self.notice(f"Recording stopped: {directory}")

    def _rec_t(self, now: float) -> float:
        """Seconds since recording started, the time base of everything written to disk."""
        return now - (self.rec_origin if self.rec_origin is not None else self.started)

    def connect(self, port: str, baud: int = 115200, kind: str = "serial"):
        self.stop()
        factory = self.transport_factory
        if factory is None:
            if kind not in TRANSPORTS:
                raise ValueError(f"Unknown transport {kind!r}; available: {', '.join(TRANSPORTS)}")
            factory = TRANSPORTS[kind]
        transport = factory(port, baud)
        try:
            self._start("LIVE", f"{port} / {baud} 8N1")
        except Exception:
            transport.close()
            raise
        self.transport = transport

    def start_replay(self, path: Path):
        replay = Replay(path)
        try:
            self._start("REPLAY", str(path))
        except Exception:
            replay.close()
            raise
        self.replay = replay

    def stop(self):
        self.tx_enabled = False
        errors = []
        for attr in ("transport", "replay", "recorder"):
            resource = getattr(self, attr)
            setattr(self, attr, None)
            if resource:
                try:
                    resource.close()
                except OSError as exc:
                    errors.append(str(exc))
        if self.mode != "IDLE":
            self.notice("Session stopped" + (": " + "; ".join(errors) if errors else ""))
        self.rec_origin = None
        self.mode = "IDLE"

    def enable_transmit(self, enabled: bool):
        if enabled and (self.mode != "LIVE" or not self.transport):
            raise ValueError("Transmission requires a live serial session")
        self.tx_enabled = bool(enabled)

    def _send(self, data: bytes, description: str):
        if not self.tx_enabled or self.mode != "LIVE" or not self.transport:
            raise ValueError("Enable TX in a live serial session first")
        try:
            # Record the intended bytes before writing; success is separately logged.
            self.recorder.event(Frame("TX_REQUEST", {"description": description}, data), self._rec_t(self.clock()))
            self.recorder.flush()
            self.transport.write(data)
            self.tx_bytes += len(data)
            self.recorder.bytes("tx", data, self._rec_t(self.clock()))
            self.recorder.event(Frame("TX_WRITTEN", {"description": description,
                                  "status": "written to serial; satellite execution unconfirmed"}, data),
                                self._rec_t(self.clock()))
            self.recorder.flush()
            self.notice(f"TX {description} — serial write complete; execution unconfirmed")
        except OSError as exc:
            self.notice(f"TX failed or delivery uncertain: {exc}; not retried")
            self.stop()
            raise

    def send_command(self, channel: int, value: int):
        self._send(digital_command(channel, value), f"ID {channel} = {value}")

    def send_time(self):
        self._send(time_command(int(time.time())), "UTC Unix time")

    def send_terminal(self, text: str, hexadecimal: bool = False):
        data = bytes.fromhex(text) if hexadecimal else text.encode("ascii") + b"\r\n"
        if not data or len(data) > 512:
            raise ValueError("Terminal sends must contain 1–512 bytes")
        self._send(data, f"terminal {data.hex(' ')}")

    def _events(self, events: list[Frame], now: float):
        for frame in events:
            self.telemetry.apply(frame, now)
            if self.recorder:
                self.recorder.event(frame, self._rec_t(now))
            if frame.kind == "ERROR":
                self.notice(frame.data["message"])
            else:
                self.last_frame = now

    def _receive(self, data: bytes, now: float):
        if not data:
            return
        self.rx_bytes += len(data)
        self.terminal.append((now, data[:200].hex(" "), repr(data[:200])))
        self.recorder.bytes("rx", data, self._rec_t(now))
        self._events(self.parser.feed(data, now), now)

    def tick(self):
        now = self.clock()
        try:
            if self.mode == "LIVE":
                self._receive(self.transport.read(), now)
            elif self.mode == "REPLAY":
                for elapsed, data in self.replay.poll(now - self.started):
                    self._receive(data, self.started + elapsed)
                if self.replay.finished:
                    self._events(self.parser.expire(now + self.parser.timeout_s), now)
                    self.stop()
                    self.notice("Replay complete (RX only)")
            if self.mode in ("LIVE", "REPLAY"):
                self._events(self.parser.expire(now), now)
            if self.recorder and now - self.last_flush >= 1:
                self.recorder.flush()
                self.last_flush = now
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.notice(f"Session error: {exc}")
            self.stop()

    def snapshot(self) -> Snapshot:
        now = self.clock()
        analog_values = tuple(c.apply(raw) for c,raw in zip(self.calibration,self.telemetry.atlm))
        return Snapshot(self.mode, self.source, copy.deepcopy(self.telemetry), self.calibration, analog_values,
                        self.rx_bytes, self.tx_bytes, self.parser.frames_ok, self.parser.errors,
                        self.parser.discarded, None if self.last_frame is None else now-self.last_frame,
                        now, self.log_directory, tuple(self.notices), tuple(self.terminal),
                        bool(self.mode == "LIVE" and self.tx_enabled))
