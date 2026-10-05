# PyInstaller spec for the ground station.  Build (from the guiTool folder):
#     pyinstaller cansat_gui.spec --noconfirm
# Output: dist/CanSatGroundStation/   (one folder; start CanSatGroundStation[.exe])
a = Analysis(
    ["run_gui.py"],
    pathex=["."],
    datas=[("cansat_gui/logo.png", "cansat_gui")],
    hiddenimports=[],
    excludes=["tkinter", "unittest", "PyQt6.QtWebEngineCore", "PyQt6.QtQml", "PyQt6.QtQuick"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CanSatGroundStation",
    console=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="CanSatGroundStation")
