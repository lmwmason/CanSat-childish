"""Entry point for the packaged app (PyInstaller) and for `python run_gui.py`.

    CanSatGroundStation              start the ground station
    CanSatGroundStation --selftest   start it headless with the demo flight, check that data flows
                                     and the bundled files are present, exit 0 (ok) / 1 (failed).
                                     Used by the release build to test the frozen binary.
"""
import os
import sys


def selftest() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv[:1])
    app.setOrganizationName("cansat-selftest")
    app.setApplicationName("cansat-selftest")
    from cansat_gui import mother, theme
    from cansat_gui.main_window import MainWindow

    result = {"code": 1}
    win = MainWindow()
    win.show()
    if theme.logo_pixmap().isNull():
        print("SELFTEST FAILED: logo.png is missing from the bundle", file=sys.stderr)
        return 1
    win.mother_link.open(mother.DEMO, mother.CRSF_BAUD)

    def check() -> None:
        v = win.mission.v
        path = win.mother_link.log_path
        ok = "roll" in v and "state" in v and path is not None and path.exists()
        print(f"SELFTEST {'OK' if ok else 'FAILED'}: {len(v)} telemetry fields, log {path}")
        result["code"] = 0 if ok else 1
        win.mother_link.close()
        app.quit()

    QTimer.singleShot(1500, check)
    app.exec()
    return result["code"]


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    from cansat_gui.__main__ import main
    sys.exit(main())
