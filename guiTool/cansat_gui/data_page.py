import csv

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QAbstractItemView, QFileDialog, QHeaderView, QGridLayout, QHBoxLayout, QLabel,
                             QMessageBox, QProgressBar, QPushButton, QScrollArea, QSplitter,
                             QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from . import theme
from .link import SerialLink
from .conn_bar import ConnectionBar
from .protocol import (CSV_HEADER, DUMP_END, DumpHeader, Row, parse_header, parse_row,
                       parse_status)
from .widgets import PlotWidget, Tile

DUMP_TIMEOUT_MS = 15000
COLUMNS = ["idx", "state", "t (s)", "alt (m)", "pressure (hPa)", "temp (°C)", "humidity (%)", "accel (g)"]


class DataPage(QWidget):
    """Download the EEPROM flight log over serial, inspect it and export CSV."""

    def __init__(self, link: SerialLink, parent=None):
        super().__init__(parent)
        self.link = link
        self.rows: list[Row] = []
        self.header: DumpHeader | None = None
        self._dumping = False
        self._timeout = QTimer(self, singleShot=True, interval=DUMP_TIMEOUT_MS)
        self._timeout.timeout.connect(lambda: self._finish(False, "Timed out waiting for data"))

        self.btn_read = QPushButton("Read child log")
        self.btn_save = QPushButton("Save CSV…")
        self.btn_open = QPushButton("Open CSV…")
        self.btn_erase = QPushButton("Erase EEPROM log")
        self.btn_erase.setObjectName("danger")
        self.btn_read.clicked.connect(self.read_log)
        self.btn_save.clicked.connect(self.save_csv)
        self.btn_open.clicked.connect(self.open_csv)
        self.btn_erase.clicked.connect(self.erase_log)
        self.progress = QProgressBar()
        self.progress.setVisible(False)

        top = QHBoxLayout()
        for b in (self.btn_read, self.btn_save, self.btn_open):
            top.addWidget(b)
        top.addStretch(1)
        top.addWidget(self.progress, 1)
        top.addStretch(1)
        top.addWidget(self.btn_erase)

        self.t_count = Tile("Records")
        self.t_dur = Tile("Duration")
        self.t_max = Tile("Max altitude")
        self.t_rate = Tile("Avg descent rate")
        self.t_ground = Tile("Ground pressure")
        tiles = QHBoxLayout()
        for t in (self.t_count, self.t_dur, self.t_max, self.t_rate, self.t_ground):
            tiles.addWidget(t)

        self.plots = [
            PlotWidget("Altitude", "m", theme.BLUE),
            PlotWidget("Pressure", "hPa", "#bc8cff"),
            PlotWidget("Temperature", "°C", theme.RED),
            PlotWidget("Humidity", "%", "#39c5cf"),
            PlotWidget("Acceleration", "g", theme.AMBER),
        ]
        plot_col = QVBoxLayout()
        plot_col.setSpacing(4)
        for pw in self.plots:
            pw.cursorChanged.connect(self._set_cursor)
            plot_col.addWidget(pw)
        plot_host = QWidget()
        plot_host.setLayout(plot_col)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(plot_host)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.currentCellChanged.connect(lambda r, *_: self._set_cursor(r, from_table=True))

        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(scroll)
        split.addWidget(self.table)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        split.setSizes([760, 500])
        split.setChildrenCollapsible(False)
        scroll.setMinimumWidth(420)

        self.msg = QLabel("Connect to the child CanSat, then press “Read log”.")
        self.msg.setStyleSheet(f"color:{theme.MUTED};")

        self.conn = ConnectionBar("Child", link)
        self.child = QLabel("Child satellite: not connected")
        self.child.setStyleSheet(f"color:{theme.MUTED};")

        root = QVBoxLayout(self)
        root.addWidget(self.conn)
        root.addWidget(self.child)
        root.addLayout(top)
        root.addLayout(tiles)
        root.addWidget(split, 1)
        root.addWidget(self.msg)

        link.line.connect(self._on_line)
        link.connectionChanged.connect(self._on_conn)
        self._show_stats()
        self._update_buttons()

    def _on_conn(self, up: bool) -> None:
        if not up:
            self.child.setText("Child satellite: not connected")
            self.child.setStyleSheet(f"color:{theme.MUTED};")
        self._update_buttons()

    # ---- actions -------------------------------------------------------
    def _update_buttons(self) -> None:
        up = self.link.is_open and not self._dumping
        self.btn_read.setEnabled(up)
        self.btn_erase.setEnabled(up)
        self.btn_save.setEnabled(bool(self.rows) and not self._dumping)

    def read_log(self) -> None:
        self.rows, self.header = [], None
        self._refresh_views()
        self._dumping = True
        self.link.poll_paused = True
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.msg.setText("Reading log…")
        self._timeout.start()
        self._update_buttons()
        self.link.send("d")

    def erase_log(self) -> None:
        if QMessageBox.warning(
                self, "Erase flight log",
                "This permanently erases every record stored in the CanSat EEPROM.\n"
                "Make sure you have saved the data. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel) != QMessageBox.StandardButton.Yes:
            return
        self._erasing = True
        self.link.send("e")
        self._timeout.start()
        self.msg.setText("Erasing…")

    def _on_line(self, line: str) -> None:
        if (st := parse_status(line)):
            faults = [n for n, f in (("BMP280", st.baro_fault), ("MPU6050", st.imu_fault),
                                     ("DHT11", st.dht_fault)) if f]
            self.child.setText(f"Child satellite: {st.state} · log {st.log_count}/{st.log_max} · "
                               f"{'faults: ' + ', '.join(faults) if faults else 'sensors OK'}")
            self.child.setStyleSheet(f"color:{theme.RED if faults else theme.ACCENT};")
            return
        if getattr(self, "_erasing", False):
            if line == "log erased":
                self._erasing = False
                self._timeout.stop()
                self.rows, self.header = [], None
                self._refresh_views()
                self.msg.setText("EEPROM log erased.")
            elif line.startswith("busy"):
                self._erasing = False
                self._timeout.stop()
                self.msg.setText("CanSat is descending, cannot erase now.")
            return
        if not self._dumping:
            return
        if line.startswith("busy"):
            self._finish(False, "CanSat is descending, cannot read the log now.")
        elif line == DUMP_END:
            self._finish(True, f"Read {len(self.rows)} records.")
        elif (h := parse_header(line)):
            self.header = h
            self.progress.setRange(0, max(h.records, 1))
        elif (r := parse_row(line)):
            self.rows.append(r)
            self.progress.setValue(len(self.rows))

    def _finish(self, ok: bool, text: str) -> None:
        self._timeout.stop()
        self._dumping = False
        self._erasing = False
        self.link.poll_paused = False
        self.progress.setVisible(False)
        self.msg.setText(text)
        self.msg.setStyleSheet(f"color:{theme.ACCENT if ok else theme.RED};")
        if self.header and len(self.rows) != self.header.records:
            self.msg.setText(f"{text} Warning: expected {self.header.records} records.")
        self._refresh_views()

    # ---- csv -----------------------------------------------------------
    def save_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save flight log", "flight_log.csv", "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="") as f:
            f.write(CSV_HEADER + "\n")
            f.writelines(r.csv() + "\n" for r in self.rows)
        self.msg.setText(f"Saved {len(self.rows)} records to {path}")

    def open_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open flight log", "", "CSV (*.csv)")
        if not path:
            return
        rows = []
        with open(path, newline="") as f:
            for line in f:
                if r := parse_row(line):
                    rows.append(r)
        self.rows, self.header = rows, None
        self._refresh_views()
        self.msg.setText(f"Loaded {len(rows)} records from {path}")

    # ---- views ---------------------------------------------------------
    def _refresh_views(self) -> None:
        self.table.setRowCount(len(self.rows))
        for i, r in enumerate(self.rows):
            vals = [r.idx, r.state, f"{r.t:.1f}", f"{r.alt:.1f}", f"{r.pressure:.1f}",
                    f"{r.temp:g}", f"{r.hum:g}", f"{r.accel:.1f}"]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                if r.state == "LANDED":
                    it.setForeground(QColor(theme.ACCENT))
                self.table.setItem(i, c, it)
        xs = [r.t for r in self.rows]
        for pw, attr in zip(self.plots, ("alt", "pressure", "temp", "hum", "accel")):
            pw.set_data(xs, [getattr(r, attr) for r in self.rows])
        self._show_stats()
        self._update_buttons()

    def _show_stats(self) -> None:
        if not self.rows:
            for t in (self.t_count, self.t_dur, self.t_max, self.t_rate, self.t_ground):
                t.set_value("--", theme.MUTED)
            return
        dur = self.rows[-1].t - self.rows[0].t
        peak = max(r.alt for r in self.rows)
        self.t_count.set_value(str(len(self.rows)))
        self.t_dur.set_value(f"{dur:.0f} s")
        self.t_max.set_value(f"{peak:.1f} m")
        self.t_rate.set_value(f"{(peak - self.rows[-1].alt) / dur:.1f} m/s" if dur > 0 else "--")
        self.t_ground.set_value(f"{self.header.ground_pa / 100:.1f} hPa" if self.header else "--")

    def _set_cursor(self, i: int, from_table: bool = False) -> None:
        for pw in self.plots:
            pw.set_cursor(i)
        if i >= 0 and not from_table:
            self.table.blockSignals(True)
            self.table.selectRow(i)
            self.table.scrollToItem(self.table.item(i, 0))
            self.table.blockSignals(False)
