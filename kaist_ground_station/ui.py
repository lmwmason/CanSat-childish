"""Tk frontend: widgets, drawing, and user intent only.

No wire protocol, serial I/O, recording, calibration maths, or mutable backend
state is owned by this module. Every view is rendered from a service snapshot.
"""
from __future__ import annotations

import io
import math
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

import matplotlib
matplotlib.use("TkAgg")
from matplotlib import font_manager
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from .frontends import FrontendUnavailable
from .service import StationService
from .autodetect import ranked_ports as list_ports
from .transport import TRANSPORTS
from .ui_settings import UISettings

class StationWindow:
    def __init__(self, root: tk.Tk, service: StationService, settings: UISettings | None = None):
        self.root, self.service = root, service
        self.cfg = settings or UISettings()
        self.c = self.cfg.colors
        self.root.title("CanSat / KAIST Ground Station")
        self.root.geometry(f"{min(1280,root.winfo_screenwidth())}x{min(960,root.winfo_screenheight()-60)}")
        self.root.minsize(1000, 700)
        self.root.configure(bg=self.c["bg"])
        families = set(tkfont.families(root))
        default_family = tkfont.nametofont("TkDefaultFont").actual("family")
        family = next((f for f in self.cfg.font_family if f in families), default_family)
        mono = next((f for f in self.cfg.mono_family if f in families), tkfont.nametofont("TkFixedFont").actual("family"))
        self.mono, self.family = mono, family
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            tkfont.nametofont(name).configure(family=family, size=self.cfg.size_base)
        c = self.c
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure(".", background=c["bg"], foreground=c["text"], font=(family, self.cfg.size_base),
                        bordercolor=c["border"], lightcolor=c["bg"], darkcolor=c["bg"], troughcolor=c["panel"])
        style.configure("TButton", padding=(12, 6), background=c["button"], foreground=c["text"],
                        bordercolor=c["button"], font=(family, self.cfg.size_base, "bold"))
        style.map("TButton", background=[("active", c["button_active"]), ("disabled", c["panel"])],
                  foreground=[("disabled", c["muted"])], bordercolor=[("disabled", c["panel"])])
        for name in ("TEntry", "TCombobox"):
            style.configure(name, fieldbackground=c["panel"], foreground=c["text"], insertcolor=c["text"],
                            arrowcolor=c["text"], bordercolor=c["border"], selectbackground=c["button"])
        style.map("TCombobox", fieldbackground=[("readonly", c["panel"])], foreground=[("readonly", c["text"])])
        root.option_add("*TCombobox*Listbox.background", c["panel"])
        root.option_add("*TCombobox*Listbox.foreground", c["text"])
        root.option_add("*TCombobox*Listbox.selectBackground", c["button"])
        style.configure("TCheckbutton", indicatorbackground=c["panel"], indicatorforeground=c["text"])
        style.map("TCheckbutton", background=[("active", c["bg"])], indicatorbackground=[("selected", c["ok"])])
        style.configure("TNotebook", background=c["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", padding=(16, 7), background=c["panel"], foreground=c["muted"],
                        bordercolor=c["border"])
        style.map("TNotebook.Tab", background=[("selected", c["button_active"])], foreground=[("selected", c["text"])])
        style.configure("TLabelframe", background=c["bg"], bordercolor=c["border"], borderwidth=2, relief="solid")
        style.configure("TLabelframe.Label", background=c["bg"], foreground=c["text"],
                        font=(family, self.cfg.size_base, "bold"))
        style.configure("Treeview", background=c["panel"], fieldbackground=c["panel"], foreground=c["text"],
                        rowheight=26, bordercolor=c["border"])
        style.configure("Treeview.Heading", background=c["button"], foreground=c["text"],
                        font=(family, self.cfg.size_base, "bold"), bordercolor=c["border"])
        style.map("Treeview", background=[("selected", c["button_active"])])
        style.configure("Vertical.TScrollbar", background=c["button"], troughcolor=c["panel"], arrowcolor=c["text"],
                        bordercolor=c["panel"], lightcolor=c["button"], darkcolor=c["button"])
        style.map("Vertical.TScrollbar", background=[("active", c["button_active"])])
        # ttk's own dpi is derived from tk scaling; matplotlib needs the same number to match text size.
        self.dpi = float(root.tk.call("tk", "scaling")) * 72
        # NanumGothic is a single .ttf; matplotlib picks the wrong face from Noto CJK .ttc collections
        known = {f.name for f in font_manager.fontManager.ttflist}
        plt_fonts = [f for f in self.cfg.plot_family if f in known]
        matplotlib.rcParams.update({"font.family": plt_fonts or ["DejaVu Sans"], "axes.unicode_minus": False,
                                    "font.size": self.cfg.size_plot})
        self.status = tk.StringVar(value="IDLE / 수신 대기")
        self.footer = tk.StringVar(value="")
        self.metrics = {}
        self.tx_enabled = tk.BooleanVar(value=False)
        self.last_notices = None
        self.last_terminal = None
        self.last_messages = None
        self.image_bytes = None
        self.image_fit = None
        self.qlook_version = -1
        self.qlook_fit = None
        self.plot_keys = {}
        self._build()
        self.refresh_ports()
        root.protocol("WM_DELETE_WINDOW", self.close)
        self._tick()

    def _button(self, parent, text, fn, **kwargs):
        button = ttk.Button(parent, text=text, command=lambda: self.action(fn))
        button.pack(side="left", padx=3, **kwargs)
        return button

    def action(self, fn):
        try:
            fn()
        except Exception as exc:
            messagebox.showerror("Ground station", str(exc), parent=self.root)

    def _build(self):
        connections = ttk.Frame(self.root, padding=(10, 8))
        connections.pack(fill="x")
        ttk.Label(connections, text="방식").pack(side="left")
        self.kind = ttk.Combobox(connections, values=list(TRANSPORTS), width=8, state="readonly")
        self.kind.set(next(iter(TRANSPORTS)))
        self.kind.pack(side="left", padx=(4, 10))
        ttk.Label(connections, text="포트").pack(side="left")
        self.port = ttk.Combobox(connections, width=18)
        self.port.pack(side="left", padx=(4, 3))
        self._button(connections, "새로고침", self.refresh_ports)
        ttk.Label(connections, text="보율").pack(side="left", padx=(10, 0))
        self.baud = ttk.Combobox(connections, values=[115200, 9600, 38400, 57600, 230400], width=8)
        self.baud.set("115200")
        self.baud.pack(side="left", padx=(4, 10))
        self.connect_button = self._button(connections, "연결", self.connect)
        self._button(connections, "정지", self.stop)
        self._button(connections, "로그 재생", self.replay)
        self._button(connections, "센서 환산 설정", self.calibration)

        cards = ttk.LabelFrame(self.root, text="수신 상태", padding=(8, 4))
        cards.pack(fill="x", padx=10, pady=(0, 6))
        for i, (key, label) in enumerate((("alt", "GPS 고도"), ("fix", "고정 / 위성 수"),
                                         ("rx", "수신량"), ("frames", "정상 / 오류 프레임"), ("age", "마지막 수신 후"))):
            cell = ttk.Frame(cards)
            cell.grid(row=0, column=i, sticky="w", padx=(0, 16))
            cards.columnconfigure(i, weight=1)
            ttk.Label(cell, text=label, foreground=self.c["muted"]).pack(anchor="w")
            var = tk.StringVar(value="—")
            ttk.Label(cell, textvariable=var, font=(self.mono, self.cfg.size_metric, "bold")).pack(anchor="w")
            self.metrics[key] = var
        self.status_label = ttk.Label(cards, textvariable=self.status, foreground=self.c["warn"])
        self.status_label.configure(font=(self.family, self.cfg.size_status))
        self.status_label.grid(row=0, column=5, sticky="e")

        ttk.Label(self.root, textvariable=self.footer, foreground=self.c["muted"], padding=(10, 4),
                  anchor="w").pack(side="bottom", fill="x")
        body = ttk.Frame(self.root, padding=(10, 0))
        body.pack(fill="both", expand=True)
        upper = ttk.Frame(body)
        upper.pack(fill="both", expand=True)
        upper.columnconfigure(0, weight=3)
        upper.columnconfigure(1, weight=2)
        upper.rowconfigure(0, weight=1)
        track = ttk.LabelFrame(upper, text="GPS 궤적 (기준점으로부터의 동·북 거리)", padding=4)
        track.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.gps_text = tk.StringVar(value="GPS 위치 대기")
        self.gps_label = ttk.Label(track, textvariable=self.gps_text, foreground=self.c["muted"])
        self.gps_label.pack(side="bottom", fill="x", pady=(4, 0))
        self.track_fig, self.track_canvas = self._figure(track)
        attitude = ttk.LabelFrame(upper, text="IMU 회전 (장착 방향 보정 전)", padding=4)
        attitude.grid(row=0, column=1, sticky="nsew")
        self.imu_text = tk.StringVar(value="IMU 데이터 대기")
        self.imu_label = ttk.Label(attitude, textvariable=self.imu_text, foreground=self.c["muted"])
        self.imu_label.pack(side="bottom", fill="x", pady=(4, 0))
        self.attitude_fig, self.attitude_canvas = self._figure(attitude)

        notebook = ttk.Notebook(body, height=260)
        notebook.pack(fill="both", expand=True, pady=8)
        sensors = ttk.Frame(notebook, padding=8)
        notebook.add(sensors, text="센서 / 고도")
        table = ttk.Frame(sensors)
        table.pack(side="left", fill="y", padx=(0, 10))
        self.analog = ttk.Treeview(table, columns=("channel", "raw", "value", "unit"), show="headings", height=8)
        for col, title in zip(self.analog["columns"], ("ATLM 채널", "원시값", "환산값", "단위")):
            self.analog.heading(col, text=title)
            self.analog.column(col, width=90, anchor="center", stretch=False)
        self.analog.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.analog.yview)
        scroll.pack(side="right",fill="y")
        self.analog.configure(yscrollcommand=scroll.set)
        for i in range(8):
            self.analog.insert("", "end", iid=str(i), values=(i, "—", "—", "raw"))
        self.alt_fig, self.alt_canvas = self._figure(sensors)

        digital = ttk.Frame(notebook, padding=12)
        notebook.add(digital, text="디지털 상태 / IMU 원시값")
        self.digital_labels = []
        for i in range(32):
            label = tk.Label(digital, text=f"{i:02d}  —", bg=self.c["panel"], fg=self.c["muted"], padx=12, pady=8, relief="flat", highlightthickness=1, highlightbackground=self.c["border"],
                             font=(self.mono, self.cfg.size_base))
            label.grid(row=i // 8, column=i % 8, padx=3, pady=3, sticky="ew")
            digital.columnconfigure(i % 8, weight=1)
            self.digital_labels.append(label)
        self.imu_values = tk.StringVar(value="추가 IMU 필드는 센서 출력 설정 확인 전까지 순서대로 표시합니다.")
        ttk.Label(digital, textvariable=self.imu_values, wraplength=950).grid(row=4, column=0, columnspan=8, pady=10)

        camera = ttk.Frame(notebook, padding=8)
        notebook.add(camera, text="카메라 / QLOOK")
        self.camera_label = tk.Label(camera, text="JPEG 수신 대기", bg=self.c["panel"], fg=self.c["muted"], width=40, relief="flat", highlightthickness=1, highlightbackground=self.c["border"])
        self.camera_label.pack(side="left", fill="both", expand=True, padx=5)
        self.qlook_label = tk.Label(camera, text="QLOOK 512 × 512 수신 대기", bg=self.c["panel"], fg=self.c["muted"], width=35, relief="flat", highlightthickness=1, highlightbackground=self.c["border"])
        self.qlook_label.pack(side="left", fill="both", expand=True, padx=5)

        messages = ttk.Frame(notebook,padding=8)
        notebook.add(messages,text="사용자 메시지")
        self.message_text = self._text(messages,height=8)

        terminal = ttk.Frame(notebook, padding=8)
        notebook.add(terminal, text="원시 수신 / BT 터미널")
        self.terminal_text = self._text(terminal, height=7)
        sendrow = ttk.Frame(terminal)
        sendrow.pack(fill="x", pady=5)
        self.terminal_input = ttk.Entry(sendrow)
        self.terminal_input.pack(side="left", fill="x", expand=True)
        self.hex_mode = tk.BooleanVar(value=False)
        ttk.Checkbutton(sendrow, text="HEX", variable=self.hex_mode).pack(side="left", padx=5)
        self.terminal_send = self._button(sendrow, "전송 (ASCII는 CRLF 추가)",
                                         lambda: self.service.send_terminal(self.terminal_input.get(), self.hex_mode.get()))

        commands = ttk.LabelFrame(body, text="지상 명령 (송신 후 실행 여부는 수신 상태로 확인)", padding=8)
        commands.pack(fill="x", pady=(0, 8))
        self.tx_check = ttk.Checkbutton(commands, text="TX 활성화", variable=self.tx_enabled,
                                        command=lambda: self.action(lambda: self.service.enable_transmit(self.tx_enabled.get())))
        self.tx_check.pack(side="left", padx=(0, 12))
        ttk.Label(commands, text="ID").pack(side="left")
        self.command_id = ttk.Combobox(commands, width=5, values=list(range(24)) + list(range(64, 72)), state="readonly")
        self.command_id.set("0")
        self.command_id.pack(side="left", padx=5)
        ttk.Label(commands, text="값").pack(side="left")
        self.command_value = ttk.Entry(commands, width=6)
        self.command_value.insert(0, "0")
        self.command_value.pack(side="left", padx=5)
        self.send_button = self._button(commands, "명령 전송", self.send_command)
        self.time_button = self._button(commands, "UTC 시각 전송", self.service.send_time)
        ttk.Label(commands, text="0–23: OFF/ON (0/1)   ·   64–71: 값 (0–255)", foreground=self.c["muted"]).pack(side="left", padx=10)

        self.event_text = self._text(body, height=4)
        # Share available height between plots and tabs; retain command controls.
        for widget in (upper,notebook,commands,self.event_text):
            widget.pack_forget()
        body.columnconfigure(0,weight=1)
        body.rowconfigure(0,weight=1,minsize=120)
        body.rowconfigure(1,weight=1,minsize=120)
        upper.grid(row=0,column=0,sticky="nsew")
        notebook.grid(row=1,column=0,sticky="nsew",pady=10)
        commands.grid(row=2,column=0,sticky="ew",pady=(0,8))
        self.event_text.grid(row=3,column=0,sticky="ew")

    def _style_axes(self, ax):
        c = self.c
        ax.set_facecolor(c["panel"])
        ax.grid(True, color=c["grid"], linewidth=0.8)
        ax.tick_params(colors=c["text"])
        ax.xaxis.label.set_color(c["text"])
        ax.yaxis.label.set_color(c["text"])
        ax.title.set_color(c["text"])
        for spine in ax.spines.values():
            spine.set_color(c["border"])

    def _figure(self, parent):
        figure = Figure(dpi=self.dpi, facecolor=self.c["panel"], layout="constrained")
        canvas = FigureCanvasTkAgg(figure, master=parent)
        widget = canvas.get_tk_widget()
        widget.configure(width=200, height=120, highlightthickness=0)
        widget.pack(fill="both", expand=True)
        return figure, widget

    def _text(self, parent, height):
        box = tk.Text(parent, height=height, bg=self.c["panel"], fg=self.c["text"], relief="flat", highlightthickness=1, highlightbackground=self.c["border"], wrap="word",
                      font=(self.mono, self.cfg.size_log), padx=8, pady=6, state="disabled")
        box.pack(fill="both", expand=True)
        return box

    def refresh_ports(self):
        ports = list_ports()
        self.port["values"] = [name for name, _ in ports]
        if ports and not self.port.get():
            self.port.set(ports[0][0])

    def connect(self):
        if not self.port.get().strip():
            raise ValueError("직렬 포트를 선택하거나 /dev/ttyUSB0 등의 경로를 입력하세요.")
        self.service.connect(self.port.get().strip(), int(self.baud.get()), self.kind.get())
        self.tx_enabled.set(False)

    def stop(self):
        self.service.stop()
        self.tx_enabled.set(False)

    def replay(self):
        path = filedialog.askopenfilename(title="세션의 traffic.jsonl 선택", filetypes=[("Traffic log", "*.jsonl")])
        if path:
            self.service.start_replay(Path(path))
            self.tx_enabled.set(False)

    def calibration(self):
        path = filedialog.askopenfilename(title="csAtlmSet.cfg 선택", filetypes=[("Calibration", "*.cfg"), ("All", "*")])
        if path:
            self.service.configure_calibration(Path(path))

    def send_command(self):
        self.service.send_command(int(self.command_id.get()), int(self.command_value.get()))

    def _replace(self, widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.see("end")
        widget.configure(state="disabled")

    def _changed(self, name, key):
        """True when a plot's inputs changed; avoids re-rendering identical figures every tick."""
        if self.plot_keys.get(name) == key:
            return False
        self.plot_keys[name] = key
        return True

    def _draw_track(self, track):
        if not self._changed("track", (len(track), track[-1] if track else None)):
            return
        fig = self.track_fig
        fig.clear()
        ax = fig.add_subplot()
        ax.set_aspect("equal", adjustable="datalim")
        ax.set_xlabel("동쪽 (m)")
        ax.set_ylabel("북쪽 (m)")
        self._style_axes(ax)
        if not track:
            ax.text(0.5, 0.5, "GPS FIX를 기다리는 중", transform=ax.transAxes, ha="center", va="center", color=self.c["muted"])
        else:
            lat0, lon0 = track[0]
            east = [(lon-lon0)*111195*math.cos(math.radians(lat0)) for lat, lon in track]
            north = [(lat-lat0)*111195 for lat, lon in track]
            ax.plot(east, north, color=self.c["line1"], linewidth=2.2, label="궤적")
            ax.plot(east[:1], north[:1], "o", color=self.c["line3"], label="시작")
            ax.plot(east[-1:], north[-1:], "o", color=self.c["line4"], label="현재")
            ax.legend(loc="upper right", fontsize="small", facecolor=self.c["panel"], edgecolor=self.c["border"], labelcolor=self.c["text"])
            # keep at least a 50 m window so a stationary receiver is not magnified into noise
            cx, cy = (min(east)+max(east))/2, (min(north)+max(north))/2
            half = max(max(east)-min(east), max(north)-min(north), 50)/2*1.15
            ax.plot([cx-half, cx+half], [cy-half, cy+half], alpha=0)  # sets the minimum view window
        fig.canvas.draw_idle()

    def _draw_attitude(self, values):
        if not self._changed("attitude", tuple(values[:3])):
            return
        fig = self.attitude_fig
        fig.clear()
        ax = fig.add_subplot()
        ax.set_aspect("equal")
        ax.set_axis_off()
        if len(values) < 3:
            ax.text(0.5, 0.5, "IMU 수신 대기", transform=ax.transAxes, ha="center", va="center", color=self.c["muted"])
            fig.canvas.draw_idle()
            return
        rx, ry, rz = [math.radians(v) for v in values[:3]]

        def rotate(p):
            x, y, z = p
            y, z = y*math.cos(rx)-z*math.sin(rx), y*math.sin(rx)+z*math.cos(rx)
            x, z = x*math.cos(ry)+z*math.sin(ry), -x*math.sin(ry)+z*math.cos(ry)
            x, y = x*math.cos(rz)-y*math.sin(rz), x*math.sin(rz)+y*math.cos(rz)
            return x+0.4*y, z-0.4*y

        vertices = [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-0.5, 0.5)]
        for i, p in enumerate(vertices):
            for q in vertices[i+1:]:
                if sum(a != b for a, b in zip(p, q)) == 1:
                    (x0, y0), (x1, y1) = rotate(p), rotate(q)
                    ax.plot([x0, x1], [y0, y1], color=self.c["muted"], linewidth=1.4)
        ox, oy = rotate((0, 0, 0))
        for p, color, label in [((1.8, 0, 0), self.c["line2"], "X"), ((0, 1.8, 0), self.c["line3"], "Y"), ((0, 0, 1.8), self.c["line1"], "Z")]:
            x, y = rotate(p)
            ax.annotate("", xy=(x, y), xytext=(ox, oy), arrowprops={"arrowstyle": "-|>", "color": color, "lw": 1.8})
            ax.text(x*1.08, y*1.08, label, color=color, fontweight="bold", ha="center", va="center")
        ax.set_xlim(-2.6, 2.6)
        ax.set_ylim(-2.6, 2.6)
        fig.canvas.draw_idle()

    def _draw_altitude(self, history):
        if not self._changed("altitude", (len(history), history[-1] if history else None)):
            return
        fig = self.alt_fig
        fig.clear()
        ax = fig.add_subplot()
        ax.set_title("GPS 고도", fontsize="medium")
        ax.set_xlabel("수신 경과 시간 (s)")
        ax.set_ylabel("고도 (m)")
        self._style_axes(ax)
        if len(history) < 2:
            ax.text(0.5, 0.5, "GPS 수신 대기", transform=ax.transAxes, ha="center", va="center", color=self.c["muted"])
        else:
            t0 = history[0][0]
            ax.plot([t-t0 for t, _ in history], [z for _, z in history], color=self.c["line1"], linewidth=2.2)
        fig.canvas.draw_idle()

    def _render(self, s):
        state = s.telemetry
        age = s.link_age_s
        health = "정지" if s.mode=="IDLE" else ("수신 대기" if age is None else ("수신 중" if age<3 else "수신 지연"))
        self.status.set(f"{s.mode}: {health}")
        self.status_label.configure(foreground=self.c["ok"] if s.mode!="IDLE" and age is not None and age<3 else self.c["warn"])
        gps = state.gps
        alt = gps.get("altitude_m")
        self.metrics["alt"].set("—" if alt is None else f"{alt:.1f} m")
        self.metrics["fix"].set(f"{gps.get('fix','—')} / {gps.get('satellites','—')}")
        self.metrics["rx"].set(f"{s.rx_bytes/1024:.1f} KiB")
        self.metrics["frames"].set(f"{s.valid_frames} / {s.errors}")
        self.metrics["age"].set("—" if age is None else f"{age:.1f} s")
        if gps.get("fix"):
            self.gps_text.set(f"{gps['lat']:.7f}, {gps['lon']:.7f}   UTC {gps['utc']}   HDOP {gps['hdop']}")
        else:
            self.gps_text.set("GPS 위치 대기 / NO FIX")
        if state.imu:
            self.imu_text.set("  ".join(f"{a} {v:+.1f}°" for a,v in zip("XYZ",state.imu)))
            self.imu_values.set("IMU fields: " + "  ".join(f"[{i}] {v:g}" for i,v in enumerate(state.imu)) +
                                "  |  추가 필드의 단위·축은 출력 설정 확인 필요")
        else:
            self.imu_text.set("IMU 데이터 대기")
            self.imu_values.set("IMU 데이터 대기")
        for i in range(8):
            raw = state.atlm[i] if state.atlm else None
            cal = s.calibration[i]
            self.analog.item(str(i), values=(i, "—" if raw is None else raw,
                                           "—" if raw is None else f"{s.analog_values[i]:.3f}",
                                           cal.unit if cal.enabled else "raw"))
        for i,label in enumerate(self.digital_labels):
            v = state.dtlm[i] if i<len(state.dtlm) else None
            label.configure(text=f"{i:02d}  {'—' if v is None else v}",
                            fg=self.c["text"] if v else self.c["muted"], bg=self.c["on"] if v else self.c["panel"])
        self._draw_track(state.track)
        self._draw_attitude(state.imu)
        self._draw_altitude(state.altitude_history)
        self.tx_check.configure(state="normal" if s.mode=="LIVE" else "disabled")
        if s.mode != "LIVE":
            self.tx_enabled.set(False)
        for button in (self.send_button,self.time_button,self.terminal_send):
            button.configure(state="normal" if s.can_transmit else "disabled")
        if s.notices != self.last_notices:
            self._replace(self.event_text, "\n".join(f"{t:.1f}  {msg}" for t,msg in s.notices))
            self.last_notices = s.notices
        if s.terminal != self.last_terminal:
            self._replace(self.terminal_text, "\n".join(f"{t:.1f} RX  {preview}\n{hexdata}" for t,hexdata,preview in s.terminal))
            self.last_terminal = s.terminal
        messages = tuple(state.messages)
        if messages != self.last_messages:
            self._replace(self.message_text,"\n".join(f"{t:.1f} MSG_{channel:X}  {text}" for t,channel,text in messages))
            self.last_messages = messages
        self._images(state)
        gps_age = "—" if "GPS" not in state.seen else f"{s.now-state.seen['GPS']:.1f}s"
        imu_age = "—" if "IMU" not in state.seen else f"{s.now-state.seen['IMU']:.1f}s"
        self.footer.set(f"GPS age {gps_age} · IMU age {imu_age} · discarded {s.discarded} B · TX {s.tx_bytes} B  |  LOG {s.log_directory or '—'}")

    def _fit(self, label, minimum=120):
        return max(minimum, label.winfo_width()-12), max(minimum, label.winfo_height()-12)

    def _images(self, state):
        from PIL import Image, ImageTk
        fit = self._fit(self.camera_label)
        if state.jpeg != self.image_bytes or (state.jpeg and fit != self.image_fit):
            self.image_bytes, self.image_fit = state.jpeg, fit
            if state.jpeg:
                try:
                    image = Image.open(io.BytesIO(state.jpeg))
                    image.thumbnail(fit, Image.LANCZOS)
                    self.photo = ImageTk.PhotoImage(image)
                    self.camera_label.configure(image=self.photo, text="")
                except (OSError, ValueError) as exc:
                    self.camera_label.configure(image="", text=f"JPEG 디코딩 실패: {exc}")
            else:
                self.camera_label.configure(image="", text="JPEG 수신 대기")
        if not state.jpeg:
            self.camera_label.configure(text=f"JPEG 수신 {state.image_progress[0]} / {state.image_progress[1]} B")
        qfit = self._fit(self.qlook_label)
        if state.qlook_version != self.qlook_version or (state.qlook_version and qfit != self.qlook_fit):
            self.qlook_version, self.qlook_fit = state.qlook_version, qfit
            if state.qlook_version:
                image = Image.frombytes("L", (512, 512), bytes(state.qlook))
                side = min(qfit)
                image = image.resize((side, side), Image.LANCZOS)
                self.qphoto = ImageTk.PhotoImage(image)
                self.qlook_label.configure(image=self.qphoto, text="")
            else:
                self.qlook_label.configure(image="", text="QLOOK 512 × 512 수신 대기")

    def _tick(self):
        self.service.tick()
        self._render(self.service.snapshot())
        self.root.after(100, self._tick)

    def close(self):
        self.service.stop()
        self.root.destroy()


def run(service: StationService, settings: UISettings | None = None) -> None:
    """Frontend entry point (see frontends.py)."""
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise FrontendUnavailable(f"GUI display unavailable: {exc}") from exc
    StationWindow(root, service, settings)
    root.mainloop()
