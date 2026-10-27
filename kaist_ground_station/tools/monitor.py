"""Live terminal communication check; no frontend imports or satellite commands.

Run from the repository root: python3 -m kaist_ground_station.tools.monitor
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import re
import time

from kaist_ground_station.service import StationService


class ModemConnection:
    """Nonblocking SD1000U handshake. Only modem query/dial commands are sent.

    An OK or CONNECT is never counted as a valid CanSat telemetry frame.
    Failed attempts retry only after an explicit modem ERROR/disconnect; an
    unacknowledged pending attempt is not interrupted or repeatedly dialled.
    """

    def __init__(self, send, *, remote=None, enabled=True, retry_s=5.0):
        self.send = send
        self.remote = remote
        self.enabled = enabled
        self.retry_s = retry_s
        self.state = "PASSIVE"
        self.deadline = None
        self.buffer = bytearray()
        self.notice = "위성 패킷 수신 대기"
        self.last_valid_frames = 0

    def feed(self, data):
        if not self.enabled:
            return
        self.buffer.extend(data)
        if len(self.buffer) > 4096:
            del self.buffer[:-4096]

    def tick(self, now, *, valid_frames=0):
        if not self.enabled:
            return
        new_frames = valid_frames > self.last_valid_frames
        self.last_valid_frames = valid_frames
        if new_frames and self.state in ("PASSIVE", "QUERY", "RETRY", "DIALING", "UNKNOWN"):
            self.state = "CONNECTED"
            self.buffer.clear()
            self.notice = "위성 패킷 수신 확인"
        if self.deadline is None:
            self.deadline = now + 1.5
        if self.state == "PASSIVE" and now >= self.deadline:
            self._command("AT+BTINFO?")
            self.state, self.deadline = "QUERY", now + 4
            self.notice = "SD1000U 상태 조회 중"
        elif self.state == "QUERY":
            if b",STANDBY," in self.buffer:
                self._dial()
            elif b",CONNECT," in self.buffer or b"\r\nCONNECT " in self.buffer:
                self.state = "CONNECTED"
                self.buffer.clear()
                self.notice = "무선 연결됨 / 위성 패킷 대기"
            elif b",PENDING," in self.buffer:
                self.state = "DIALING"
                self.buffer.clear()
                self.notice = "수신기의 기존 연결 시도 대기"
            elif now >= self.deadline:
                self.state = "UNKNOWN"
                self.buffer.clear()
                self.notice = "모뎀 조회 응답 없음 / 수신 대기 (baud·DIP 설정 확인)"
        elif self.state == "DIALING":
            if b"\r\nCONNECT " in self.buffer:
                self.state = "CONNECTED"
                self.buffer.clear()
                self.notice = "무선 연결됨 / 위성 패킷 대기"
            elif b"\r\nERROR\r\n" in self.buffer:
                self._retry(now)
        elif self.state == "CONNECTED":
            # These modem-only lines are emitted when its radio link closes.
            if b"\r\nDISCONNECT\r\n" in self.buffer or b"\r\nNO CARRIER\r\n" in self.buffer:
                self._retry(now)
            else:
                del self.buffer[:-64]
        elif self.state == "RETRY" and now >= self.deadline:
            self._dial()

    def _command(self, text):
        self.buffer.clear()
        self.send(text)

    def _dial(self):
        self._command("ATD" + (self.remote or ""))
        self.state = "DIALING"
        self.notice = "위성 연결 시도 중 (전원이 켜져 있으면 잠시 기다리세요)"

    def _retry(self, now):
        self.state, self.deadline = "RETRY", now + self.retry_s
        self.buffer.clear()
        self.notice = f"위성 연결 안 됨 / {self.retry_s:g}초 뒤 재시도"


class MonitorService(StationService):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.modem = None

    def _receive(self, data, now):
        super()._receive(data, now)
        if self.modem is not None:
            self.modem.feed(data)


def choose_port(requested=None):
    if requested:
        return requested
    from serial.tools.list_ports import comports
    ports = list(comports())
    candidates = [p for p in ports if (p.vid, p.pid) == (0x0403, 0x6001)]
    if len(candidates) == 1:
        return candidates[0].device
    available = ", ".join(p.device for p in ports) or "없음"
    raise ValueError(f"SD1000U 포트를 하나로 찾지 못했습니다. 연결 후 다시 실행하거나 --port를 지정하세요. 포트: {available}")


def remote_address(value):
    value = value.replace(":", "").replace("-", "").upper()
    if not re.fullmatch(r"[0-9A-F]{12}", value):
        raise argparse.ArgumentTypeError("위성 주소는 12자리 16진수 또는 Bluetooth MAC 주소여야 합니다")
    return value


def status_line(snap, modem, previous, *, stale_s=5):
    age = snap.link_age_s
    if age is not None and age <= stale_s:
        label = "실시간 수신 중"
    elif age is not None:
        label = "수신 지연/끊김"
    else:
        label = modem.notice
    delta_t = max(snap.now-previous[0], .001)
    rate = max(0, snap.rx_bytes-previous[1])/delta_t
    age_text = "—" if age is None else f"{age:.1f}s"
    gps = snap.telemetry.gps
    gps_text = "대기" if not gps else ("미측위" if not gps["fix"] else f"FIX {gps['fix']} / {gps['satellites']}개")
    counts = snap.telemetry.counts
    return (f"{datetime.now():%H:%M:%S} [{label}] "
            f"RX {snap.rx_bytes:,}B ({rate:,.0f}B/s) | "
            f"패킷 {snap.valid_frames} / 오류 {snap.errors} | 마지막 {age_text} | "
            f"GPS {gps_text} | IMU {counts.get('IMU',0)} / 사진 {counts.get('IMAGE',0)}")


def run(args, *, service=None, sleep=time.sleep):
    service = service or MonitorService(args.log_dir)
    last_snap = None
    modem = None
    result = 1
    started = time.monotonic()
    try:
        port = choose_port(args.port)
        service.connect(port, args.baud)

        def send_modem(text):
            service.enable_transmit(True)
            try:
                service.send_terminal(text)
            finally:
                service.enable_transmit(False)

        modem = ModemConnection(send_modem, remote=args.remote, enabled=not args.no_dial)
        service.modem = modem
        print(f"직렬 포트 열림: {port} / {args.baud} 8N1", flush=True)
        print(f"로그: {service.log_directory}", flush=True)
        print("위성 패킷이 들어와야 '실시간 수신 중'으로 표시됩니다. 종료: Ctrl+C", flush=True)
        if not args.no_dial and not args.remote:
            print("수신기에 저장된 마지막 위성 주소로 연결합니다 (ATD).", flush=True)
        previous = (service.clock(), 0)
        next_report = service.clock()
        while service.mode == "LIVE":
            service.tick()
            if service.mode != "LIVE":
                break
            modem.tick(service.clock(), valid_frames=service.parser.frames_ok)
            now = service.clock()
            if now >= next_report:
                last_snap = service.snapshot()
                print(status_line(last_snap,modem,previous,stale_s=args.stale_seconds),flush=True)
                previous = (last_snap.now,last_snap.rx_bytes)
                next_report = now+args.interval
            if args.duration is not None and time.monotonic()-started >= args.duration:
                result = 0 if service.parser.frames_ok else 2
                break
            sleep(.02)
        else:
            result = 1
        if service.mode != "LIVE":
            for _,notice in list(service.notices)[-3:]:
                print(notice,flush=True)
            result = 1
    except KeyboardInterrupt:
        print("\n종료합니다.",flush=True)
        result = 0
    except (OSError, ValueError, ImportError) as exc:
        print(f"오류: {exc}",flush=True)
        result = 1
    finally:
        last_snap = service.snapshot()
        directory = Path(service.log_directory) if service.log_directory else None
        service.stop()
        if directory is not None:
            summary = {"rx_bytes":last_snap.rx_bytes,"valid_frames":last_snap.valid_frames,
                       "parser_errors":last_snap.errors,"counts":last_snap.telemetry.counts,
                       "last_frame_age_s":last_snap.link_age_s,"gps":last_snap.telemetry.gps,
                       "modem_state":modem.state if modem else None,
                       "duration_s":time.monotonic()-started,"exit_code":result}
            try:
                (directory/"monitor_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
            except OSError as exc:
                print(f"요약 저장 실패: {exc}",flush=True)
                result = 1
            print(f"수신 {last_snap.rx_bytes:,}B / 유효 패킷 {last_snap.valid_frames} / 오류 {last_snap.errors}",flush=True)
            print(f"로그 저장 완료: {directory}",flush=True)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port",help="생략하면 SD1000U의 FTDI 포트를 자동 검색")
    parser.add_argument("--baud",type=int,default=115200)
    parser.add_argument("--remote",type=remote_address,help="위성 Bluetooth 주소 (생략하면 수신기의 마지막 연결 주소)")
    parser.add_argument("--no-dial",action="store_true",help="모뎀 명령 없이 수신만 수행")
    parser.add_argument("--interval",type=float,default=1,help="출력 간격 초")
    parser.add_argument("--stale-seconds",type=float,default=5,help="수신 지연 표시 기준 초")
    parser.add_argument("--duration",type=float,help="시험 시간 초; 생략하면 Ctrl+C까지 실행")
    parser.add_argument("--log-dir",type=Path,default=Path("log/kaist-ground-station/monitor"))
    args = parser.parse_args(argv)
    for name in ("interval","stale_seconds","duration"):
        value=getattr(args,name)
        if value is not None and (not math.isfinite(value) or value<=0):
            parser.error(f"--{name.replace('_','-')} must be positive and finite")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
