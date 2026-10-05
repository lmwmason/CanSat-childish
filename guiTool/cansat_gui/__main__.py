import sys

from PyQt6.QtWidgets import QApplication

from .main_window import MainWindow
from .theme import apply_theme


def main() -> int:
    app = QApplication(sys.argv)
    app.setOrganizationName("childCansat")
    app.setApplicationName("childCansat Ground Station")
    apply_theme(app)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
