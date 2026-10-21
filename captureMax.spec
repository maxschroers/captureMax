# PyInstaller build for Windows (onefile .exe), macOS (.app bundle) and Linux (onefile binary):
#   pyinstaller --noconfirm captureMax.spec
import sys

a = Analysis(["capturemax.py"], datas=[("assets", "assets")])
pyz = PYZ(a.pure)
icon = "assets/icon.ico" if sys.platform == "win32" else "assets/icon.png"  # macOS converts png -> icns (Pillow)

if sys.platform == "darwin":
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="captureMax", console=False, icon=icon)
    coll = COLLECT(exe, a.binaries, a.datas, name="captureMax")
    app = BUNDLE(coll, name="captureMax.app", icon=icon, bundle_identifier="de.maxschroers.capturemax",
                 info_plist={  # without these macOS silently blocks camera / microphone access
                     "NSCameraUsageDescription": "captureMax shows the live picture of your camera or capture card.",
                     "NSMicrophoneUsageDescription": "captureMax plays back the audio of your capture card.",
                     "NSHighResolutionCapable": True})
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="captureMax", console=False, icon=icon)
