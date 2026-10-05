from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import QApplication

BG = "#070b17"
PANEL = "#0f1730"
PANEL_HI = "#18234a"
BORDER = "#26366a"
TEXT = "#e8eefc"
MUTED = "#7f8db3"
ACCENT = "#3fcf8e"   # "good" green
BLUE = "#5db0ff"
ORANGE = "#f6b25a"
AMBER = "#f2c14e"
RED = "#ff5c6c"

STATE_COLORS = {
    "BOOT": AMBER,
    "ARMED": BLUE,
    "DESCENT": ORANGE,
    "STANDBY": BLUE,
    "GLIDE": ORANGE,
    "LANDED": ACCENT,
    "IDLE": MUTED,
    "WAIT": AMBER,
    "STAB": BLUE,
    "SPIN": ORANGE,
    "OPEN": RED,
    "REST": BLUE,
    "WING": ACCENT,
}

QSS = f"""
* {{ color: {TEXT}; }}
QWidget {{ background: {BG}; }}
QLabel {{ background: transparent; }}
QFrame#panel, QGroupBox {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 6px; }}
QGroupBox {{ margin-top: 14px; padding-top: 8px; font-weight: bold; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {MUTED}; background: {BG}; }}
QPushButton {{ background: {PANEL_HI}; border: 1px solid {BORDER}; border-radius: 4px; padding: 6px 14px; }}
QPushButton:hover {{ border-color: {ORANGE}; }}
QPushButton:disabled {{ color: {MUTED}; }}
QPushButton#connect {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {BLUE}, stop:1 {ORANGE}); color: #07101f; font-weight: bold; border: none; }}
QPushButton#connect[on="true"] {{ background: {RED}; color: white; }}
QPushButton#danger {{ border-color: {RED}; color: {RED}; }}
QPushButton#danger:disabled {{ border-color: {BORDER}; color: {MUTED}; }}
QPushButton#tab {{ background: transparent; border: none; border-bottom: 3px solid transparent;
    border-radius: 0; padding: 10px 26px; font-size: 14px; font-weight: bold; color: {MUTED}; }}
QPushButton#tab:checked {{ color: {TEXT}; border-bottom: 3px solid {ORANGE}; background: {PANEL_HI}; }}
QComboBox {{ background: {PANEL_HI}; border: 1px solid {BORDER}; border-radius: 4px; padding: 5px 8px; min-width: 120px; }}
QComboBox QAbstractItemView {{ background: {PANEL}; selection-background-color: {BLUE}; }}
QPlainTextEdit {{ background: #050813; border: 1px solid {BORDER}; border-radius: 4px; }}
QTableWidget {{ background: {PANEL}; gridline-color: {BORDER}; border: 1px solid {BORDER};
    alternate-background-color: {PANEL_HI}; selection-background-color: #1f4a8a; }}
QHeaderView::section {{ background: {PANEL_HI}; border: none; border-right: 1px solid {BORDER};
    padding: 4px; font-weight: bold; }}
QProgressBar {{ background: #050813; border: 1px solid {BORDER}; border-radius: 4px; text-align: center; height: 18px; }}
QProgressBar::chunk {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {BLUE}, stop:1 {ORANGE}); border-radius: 3px; }}
QStatusBar {{ background: {PANEL}; }}
QSplitter::handle {{ background: {BORDER}; }}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(BG))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.Base, QColor(PANEL))
    pal.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.Button, QColor(PANEL_HI))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(BLUE))
    app.setPalette(pal)
    f = QFont(app.font())
    f.setPointSize(10)
    app.setFont(f)
    app.setStyleSheet(QSS)


LOGO_PATH = str(__import__("pathlib").Path(__file__).with_name("logo.png"))


def logo_pixmap():
    from PyQt6.QtGui import QPixmap
    return QPixmap(LOGO_PATH)


def logo_icon():
    """Window icon: the dog-in-helmet part of the logo."""
    from PyQt6.QtGui import QIcon
    return QIcon(logo_pixmap().copy(330, 80, 700, 640))
