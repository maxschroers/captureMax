# PyInstaller build for Windows (onefile .exe), macOS (.app bundle) and Linux (onefile binary):
#   pyinstaller --noconfirm captureMax.spec
import re
import sys
from pathlib import PurePath

a = Analysis(["capturemax.py"], datas=[("assets", "assets")])

# PyInstaller's QtQml hook bundles every QML module (3D, PDF, web, charts, ...), doubling the size. assets/live.qml
# only imports QtQuick + QtMultimedia (QtQml comes with QtQuick); drop the rest and the Qt libraries only they use.
QML_KEEP = {"QtQml", "QtQuick", "QtMultimedia"}
UNUSED_QT = re.compile(r"Qt6?(Quick3D|3D|Pdf|Web(Engine|View|Channel|Sockets)|Charts|DataVisualization|Graphs|"
                       r"Location|Positioning|Sensors|Scxml|StateMachine|RemoteObjects|TextToSpeech|"
                       r"Quick(Controls2|Templates2|Dialogs2|Timeline|Particles|Effects|Shapes|VectorImage|Layouts))")


def needed(entry):
    parts = PurePath(entry[0]).parts
    if "qml" in parts:
        sub = parts[parts.index("qml") + 1:]
        if sub[0] not in QML_KEEP or (sub[0] == "QtQuick" and len(sub) > 2):  # QtQuick: root plugin only
            return False
    return not UNUSED_QT.search(entry[0])


a.binaries = [e for e in a.binaries if needed(e)]
a.datas = [e for e in a.datas if needed(e)]
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
