"""Run with python3 -m kaist_ground_station; headless capture is also available."""
import argparse
from pathlib import Path
import time

from .service import StationService
from .frontends import FRONTENDS, FrontendUnavailable, load_frontend
from .transport import TRANSPORTS


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--demo", action="store_true")
    source.add_argument("--port", help="e.g. /dev/ttyUSB0 or /dev/rfcomm0; \"auto\" picks the kit's USB serial port")
    source.add_argument("--replay", type=Path, help="a session traffic.jsonl (RX only)")
    parser.add_argument("--frontend", choices=list(FRONTENDS), default="web",
                        help="web = browser UI on localhost (default); tk = desktop window")
    parser.add_argument("--transport", choices=list(TRANSPORTS), default="serial")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--log-dir", type=Path, default=Path("log/kaist-ground-station/sessions"))
    parser.add_argument("--calibration", type=Path)
    parser.add_argument("--ui-config", type=Path, help="INI file for fonts and sizes (default: config/ui.cfg in the package)")
    parser.add_argument("--headless", action="store_true", help="capture without a window")
    parser.add_argument("--duration", type=float, help="stop after N seconds (headless only)")
    args = parser.parse_args(argv)
    if args.duration is not None and (not args.headless or args.duration <= 0):
        parser.error("--duration requires --headless and a positive number")
    if args.headless and not (args.demo or args.port or args.replay):
        parser.error("headless mode requires --demo, --port, or --replay")
    if args.port == "auto":
        from .autodetect import detect_port
        args.port = detect_port()
        if not args.port:
            parser.error("no serial port found: plug in the adapter, or give --port /dev/ttyUSB0")
        print(f"auto-detected serial port: {args.port}", flush=True)
    from .ui_settings import load_ui_settings
    try:
        settings = load_ui_settings(args.ui_config)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"error: {exc}\n")
    # Only the web UI has a Record button. Headless capture and the Tk window cannot start a recording
    # later, so they keep recording from the first byte.
    auto_record = settings.record_auto or args.headless or args.frontend != "web"
    service = StationService(args.log_dir, auto_record=auto_record)
    try:
        if args.calibration:
            service.configure_calibration(args.calibration)
        if args.demo:
            service.start_demo()
        elif args.port:
            service.connect(args.port, args.baud, args.transport)
        elif args.replay:
            service.start_replay(args.replay)
        if args.headless:
            started = time.monotonic()
            while service.mode != "IDLE":
                service.tick()
                if args.duration and time.monotonic()-started >= args.duration:
                    break
                time.sleep(0.02)
            s = service.snapshot()
            print(f"RX={s.rx_bytes} frames={s.valid_frames} errors={s.errors} log={s.log_directory}")
            for _,notice in s.notices:
                print(notice)
            return int(any("Session error:" in notice for _,notice in s.notices))
        try:
            load_frontend(args.frontend)(service, settings)
        except FrontendUnavailable as exc:
            parser.exit(1, f"{exc}\nUse --headless for capture without a display.\n")
        return 0
    except KeyboardInterrupt:
        return 0
    except (OSError, ValueError) as exc:
        parser.exit(1, f"error: {exc}\n")
    finally:
        service.stop()


if __name__ == "__main__":
    raise SystemExit(main())
