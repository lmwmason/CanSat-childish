"""Display settings read from config/ui.cfg (or --ui-config); code holds only the fallbacks."""
from __future__ import annotations

import configparser
from dataclasses import dataclass, field
from pathlib import Path
import re

# Resolved from this file, not the working directory, so a fresh clone runs from anywhere.
DEFAULT_PATH = Path(__file__).resolve().parent / "config" / "ui.cfg"

# High-contrast instrument-panel palette; every name can be overridden in [colors].
DEFAULT_COLORS = {
    "bg": "#000000",        # window
    "panel": "#05111f",     # plots, tables, text boxes
    "border": "#ffffff",    # panel outlines
    "text": "#ffffff",
    "muted": "#b0b0b0",     # secondary labels
    "grid": "#045956",
    "button": "#514c4b",
    "button_active": "#6e6968",
    "ok": "#00ff00",
    "warn": "#ffff00",
    "bad": "#ff0000",
    "line1": "#00ffff",     # primary trace
    "line2": "#ff0000",
    "line3": "#00ff00",
    "line4": "#ffff00",
    "on": "#005a1f",        # active digital bit background
}

# Alarm thresholds (seconds / counts), tuned by the operator in [alarms]; 0 disables a check.
DEFAULT_ALARMS = {
    "link_warn_s": 3.0,      # no frame for this long -> warning
    "link_alarm_s": 10.0,    # no frame for this long -> alarm
    "stream_stale_s": 10.0,  # a continuously sent stream (GPS/IMU/ATLM/DTLM) silent while the link is alive
    "min_satellites": 4.0,   # fewer satellites than this -> warning
    "max_hdop": 5.0,         # HDOP above this -> warning
    "error_burst": 3.0,      # this many new error frames within 10 s -> warning
    "quality_warn_pct": 95.0,   # link quality (worse of valid-frame % and image-completion %, last 30 s) below this -> warning
    "quality_bad_pct": 80.0,    # ... below this -> alarm
}
PAGES = ("flight", "wind")      # web screens: "/" is flight, "/wind" is the wind field
LANGUAGES = ("en", "ko")   # web UI text tables in web/static/i18n.js
_BOOLS = {"true": True, "yes": True, "1": True, "on": True, "false": False, "no": False, "0": False, "off": False}
_BT_ADDRESS = re.compile(r"^[0-9a-fA-F]{12}$")
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def _names(text: str) -> list[str]:
    return [n.strip() for n in text.split(",") if n.strip()]


@dataclass
class UISettings:
    # Candidate families, first installed one wins. Empty/missing falls back to the Tk default.
    font_family: list[str] = field(default_factory=lambda: ["Noto Sans CJK KR", "NanumGothic", "DejaVu Sans"])
    mono_family: list[str] = field(default_factory=lambda: ["DejaVu Sans Mono", "NanumGothicCoding"])
    plot_family: list[str] = field(default_factory=lambda: ["NanumGothic", "Noto Sans CJK KR", "DejaVu Sans"])
    size_base: int = 11     # body text; the web UI derives its whole type scale from this
    size_status: int = 12
    size_metric: int = 14
    size_log: int = 9
    size_plot: int = 9
    language: str = "en"
    record_auto: bool = True             # web UI: record from the first byte (True) or only after Record is pressed (False)
    bluetooth_auto: bool = False         # dial the address once at start-up when launched on a live serial port
    bluetooth_address: str = ""          # 12 hex digits of the satellite's Bluetooth module, for the adapter's ATD command
    checkpoints: list = field(default_factory=lambda: ["Drone ascent start", "Drop", "Parachute open", "Landing"])   # button labels
    open_pages: list = field(default_factory=lambda: list(PAGES))   # windows opened at start-up, in this order
    colors: dict = field(default_factory=lambda: dict(DEFAULT_COLORS))
    alarms: dict = field(default_factory=lambda: dict(DEFAULT_ALARMS))


def _section(parser, name):
    return parser[name] if parser.has_section(name) else {}


def load_ui_settings(path: Path | None) -> UISettings:
    settings = UISettings()
    if path is None:
        if not DEFAULT_PATH.is_file():
            return settings
        path = DEFAULT_PATH
    parser = configparser.ConfigParser()
    if not parser.read(path, encoding="utf-8"):
        raise OSError(f"UI config not found: {path}")

    language = _section(parser, "ui").get("language")
    if language is not None:
        if language.strip() not in LANGUAGES:
            raise ValueError(f"{path}: [ui] language must be one of {', '.join(LANGUAGES)}")
        settings.language = language.strip()

    pages = _section(parser, "ui").get("open_pages")
    if pages is not None:
        wanted = _names(pages)
        unknown = [p for p in wanted if p not in PAGES]
        if unknown:
            raise ValueError(f"{path}: [ui] open_pages has unknown {', '.join(unknown)}; known: {', '.join(PAGES)}")
        settings.open_pages = wanted           # empty list = open nothing

    auto_start = _section(parser, "recording").get("auto_start")
    if auto_start is not None:
        if auto_start.strip().lower() not in _BOOLS:
            raise ValueError(f"{path}: [recording] auto_start must be true or false")
        settings.record_auto = _BOOLS[auto_start.strip().lower()]

    labels = _section(parser, "checkpoints").get("labels")
    if labels is not None:
        names = _names(labels)
        if len(names) > 12 or any(len(n) > 80 for n in names):
            raise ValueError(f"{path}: [checkpoints] labels: at most 12 labels of up to 80 characters")
        settings.checkpoints = names           # empty list = no buttons

    address = _section(parser, "bluetooth").get("address")
    if address is not None:
        address = address.strip()
        if address and not _BT_ADDRESS.match(address):
            raise ValueError(f"{path}: [bluetooth] address must be 12 hex digits, e.g. 0001958D78EC")
        settings.bluetooth_address = address.upper()
    auto = _section(parser, "bluetooth").get("auto_connect")
    if auto is not None:
        if auto.strip().lower() not in ("true", "false", "yes", "no", "1", "0", "on", "off"):
            raise ValueError(f"{path}: [bluetooth] auto_connect must be true or false")
        settings.bluetooth_auto = auto.strip().lower() in ("true", "yes", "1", "on")

    fonts = _section(parser, "fonts")
    for key in ("font_family", "mono_family", "plot_family"):
        if key in fonts:
            setattr(settings, key, _names(fonts[key]))

    sizes = _section(parser, "sizes")
    for key in ("base", "status", "metric", "log", "plot"):
        if key in sizes:
            try:
                value = int(sizes[key])
            except ValueError:
                raise ValueError(f"{path}: [sizes] {key} must be an integer") from None
            if value <= 0:
                raise ValueError(f"{path}: [sizes] {key} must be positive")
            setattr(settings, f"size_{key}", value)

    for key, value in _section(parser, "colors").items():
        if key not in DEFAULT_COLORS:
            raise ValueError(f"{path}: [colors] unknown name {key!r}; known: {', '.join(DEFAULT_COLORS)}")
        if not _HEX.match(value.strip()):
            raise ValueError(f"{path}: [colors] {key} must look like #rrggbb")
        settings.colors[key] = value.strip().lower()

    for key, value in _section(parser, "alarms").items():
        if key not in DEFAULT_ALARMS:
            raise ValueError(f"{path}: [alarms] unknown name {key!r}; known: {', '.join(DEFAULT_ALARMS)}")
        try:
            number = float(value)
        except ValueError:
            raise ValueError(f"{path}: [alarms] {key} must be a number") from None
        if number < 0:
            raise ValueError(f"{path}: [alarms] {key} must not be negative")
        settings.alarms[key] = number
    return settings
