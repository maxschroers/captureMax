"""captureMax: low-latency live viewer for capture cards and webcams on Windows, macOS and Linux (Qt Multimedia)."""
import sys
import time
from collections import deque
from pathlib import Path

from PySide6.QtCore import QByteArray, QEvent, QLocale, QPoint, QRect, QSettings, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPalette, QPixmap
from PySide6.QtMultimedia import (QAudioInput, QAudioOutput, QCamera, QMediaCaptureSession, QMediaDevices,
                                  QVideoFrameFormat, QVideoSink)
from PySide6.QtWidgets import (QAbstractButton, QApplication, QComboBox, QFrame, QHBoxLayout, QLabel, QLayout,
                               QPushButton, QSlider, QStyle, QStyledItemDelegate, QStyleOptionComboBox, QStylePainter,
                               QToolButton, QVBoxLayout, QWidget)

APP = "captureMax"
ASSETS = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "assets"
ACCENT, ACCENT_HOVER = "#4a80f5", "#3a64c4"
BG, SURFACE, FIELD, BORDER = "#0e1a33", "#15254a", "#0e1a33", "#27407a"
TEXT, MUTED = "#f2f5fc", "#8c9bc0"
DANGER, DANGER_HOVER = "#e5484d", "#c43c40"
STATUS_COLORS = {"idle": MUTED, "ok": "#34d399", "err": "#f87171"}
JPEG = QVideoFrameFormat.PixelFormat.Format_Jpeg
LANGS = {"de": "Deutsch", "en": "English"}

TR = {
    "de": {
        "subtitle": "Capture-Card- & Webcam-Viewer", "video": "VIDEO", "audio": "AUDIO", "advanced": "ERWEITERT",
        "device": "Gerät", "res": "Auflösung", "fps": "FPS", "input": "Eingang", "output": "Ausgabe (Monitor)",
        "off": "Aus", "volume": "Lautstärke: {} %", "listen": "Für mich hören (aus = stumm)",
        "delay": "Verzögerung: {} ms", "low_latency": "  (Low-Latency)", "auto_exp": "Auto-Belichtung (Webcam)",
        "exposure": "Belichtung: 1/{} s  (kürzer = dunkler, mehr FPS)",
        "exp_na": "Belichtung wird auf diesem System nicht unterstützt",
        "start": "Start", "stop": "Stop", "ready": "bereit", "starting": "starte...",
        "running": "läuft · {} · {:.0f} fps",
        "no_device": "Fehler: kein Videogerät gefunden", "no_frames": "Fehler: kein Bild vom Gerät (belegt?)",
        "error": "Fehler: {}", "tip_mute": "Stumm (auch im Stream)", "tip_listen": "Nur für mich stumm",
    },
    "en": {
        "subtitle": "capture card & webcam viewer", "video": "VIDEO", "audio": "AUDIO", "advanced": "ADVANCED",
        "device": "Device", "res": "Resolution", "fps": "FPS", "input": "Input", "output": "Output (monitor)",
        "off": "Off", "volume": "Volume: {} %", "listen": "Listen myself (off = muted)",
        "delay": "Delay: {} ms", "low_latency": "  (low latency)", "auto_exp": "Auto exposure (webcam)",
        "exposure": "Exposure: 1/{} s  (shorter = darker, more FPS)",
        "exp_na": "Exposure control is not supported on this system",
        "start": "Start", "stop": "Stop", "ready": "ready", "starting": "starting...",
        "running": "running · {} · {:.0f} fps",
        "no_device": "Error: no video device found", "no_frames": "Error: no picture from device (in use?)",
        "error": "Error: {}", "tip_mute": "Mute (stream too)", "tip_listen": "Mute for me only",
    },
}

ICONS = {  # 24px stroke icons, rendered via Qt's SVG image plugin
    "volume": '<path d="M11 5 6 9H2v6h4l5 4V5z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M19 5a10 10 0 0 1 0 14"/>',
    "muted": '<path d="M11 5 6 9H2v6h4l5 4V5z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/>'
             '<path d="M19 5a10 10 0 0 1 0 14"/><path d="M3 3l18 18"/>',  # struck-through speaker
    "listen": '<path d="M3 14h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a9 9 0 0 1 18 0v7a2 2 0 0 1-2 2h-1'
              'a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3"/>',
    "deaf": '<path d="M3 14h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a9 9 0 0 1 18 0v7a2 2 0 0 1-2 2h-1'
            'a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3"/><path d="M3 3l18 18"/>',  # struck-through headphones
    "settings": '<path d="M4 6h9M19 6h1M4 12h3M13 12h7M4 18h11M21 18h-1"/>'
                '<circle cx="16" cy="6" r="2.5"/><circle cx="10" cy="12" r="2.5"/><circle cx="18" cy="18" r="2.5"/>',
}

QSS = f"""
* {{ font-family: "Segoe UI", "SF Pro Text", "Helvetica Neue", "Noto Sans", "DejaVu Sans", sans-serif;
     font-size: 13px; color: {TEXT}; }}
QWidget#main {{ background: {BG}; }}
QFrame#card, QFrame#head {{ background: {SURFACE}; border-radius: 10px; }}
QLabel {{ background: transparent; }}
QLabel[role="title"] {{ font-size: 14px; font-weight: bold; }}
QLabel[role="logo"] {{ font-size: 16px; font-weight: bold; }}
QLabel[role="hint"] {{ color: {MUTED}; font-size: 12px; }}
QLabel[role="hint"]:disabled {{ color: {BORDER}; }}
QComboBox {{ background: {FIELD}; border: none; border-radius: 8px; padding: 0 12px; min-height: 34px;
             combobox-popup: 0; }}
QComboBox:hover {{ background: {BORDER}; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox::down-arrow {{ image: url("{(ASSETS / "chevron.svg").as_posix()}"); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{ background: {FIELD}; border: 1px solid {BORDER}; padding: 4px; outline: none; }}
QComboBox QAbstractItemView::item {{ min-height: 30px; padding: 0 8px; border-radius: 6px; }}
QComboBox QAbstractItemView::item:hover {{ background: {BORDER}; }}
QComboBox QAbstractItemView::item:selected {{ background: {ACCENT}; }}
QComboBox#lang {{ min-height: 26px; padding: 0 8px; background: {FIELD}; }}
QSlider::groove:horizontal {{ height: 4px; background: {BORDER}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {ACCENT}; width: 16px; height: 16px; margin: -6px 0; border-radius: 8px; }}
QSlider::sub-page:horizontal:disabled, QSlider::handle:horizontal:disabled {{ background: {BORDER}; }}
QPushButton#start {{ background: {ACCENT}; border: none; border-radius: 12px; min-height: 48px;
                     font-size: 16px; font-weight: bold; }}
QPushButton#start:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#start[running="true"] {{ background: {DANGER}; }}
QPushButton#start[running="true"]:hover {{ background: {DANGER_HOVER}; }}
QLabel#status {{ background: {SURFACE}; border-radius: 16px; min-height: 32px; padding: 0 16px; font-size: 12px; }}
QFrame#bar {{ background: rgba(21, 37, 74, 235); border: 1px solid {BORDER}; border-radius: 14px; }}
QToolButton {{ background: {FIELD}; border: none; border-radius: 10px; min-width: 40px; min-height: 36px; }}
QToolButton:hover {{ background: {BORDER}; }}
"""


def icon(name):
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" '
           f'stroke="{TEXT}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg>')
    return QIcon(QPixmap.fromImage(QImage.fromData(QByteArray(svg.encode()), "SVG")))


def label(text="", role="hint"):
    lbl = QLabel(text)
    lbl.setProperty("role", role)
    return lbl


def windows_exposure(name, manual, value):
    """Qt can't set exposure on Windows, DirectShow can, and the driver keeps it for the Qt session that follows."""
    import cv2
    from pygrabber.dshow_graph import FilterGraph
    names = FilterGraph().get_input_devices()
    if name in names:
        cap = cv2.VideoCapture(names.index(name), cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25 if manual else 0.75)
        if manual:
            cap.set(cv2.CAP_PROP_EXPOSURE, value)
        cap.release()


def windows_mixer_mute(muted):
    """Mute this process in the Windows volume mixer on every output. The app itself keeps playing, so window
    capture (Discord, OBS) still gets the audio while the user hears nothing."""
    from ctypes import POINTER, c_float, c_int, c_uint, c_void_p
    from ctypes.wintypes import BOOL, DWORD
    from comtypes import CLSCTX_ALL, COMMETHOD, GUID, HRESULT, STDMETHOD, CoCreateInstance, IUnknown

    class ISimpleAudioVolume(IUnknown):
        _iid_ = GUID("{87CE5498-68D6-44E5-9215-6DA47EF883D8}")
        _methods_ = [STDMETHOD(HRESULT, "SetMasterVolume", []), STDMETHOD(HRESULT, "GetMasterVolume", []),
                     COMMETHOD([], HRESULT, "SetMute", (["in"], BOOL), (["in"], POINTER(GUID)))]

    class IAudioSessionManager(IUnknown):
        _iid_ = GUID("{77AA99A0-1BD6-484F-8BC7-2C654C9A9B6F}")  # IAudioSessionManager2 (starts with v1's methods)
        _methods_ = [STDMETHOD(HRESULT, "GetAudioSessionControl", []),
                     COMMETHOD([], HRESULT, "GetSimpleAudioVolume", (["in"], POINTER(GUID)), (["in"], DWORD),
                               (["out"], POINTER(POINTER(ISimpleAudioVolume))))]

    class IMMDevice(IUnknown):
        _iid_ = GUID("{D666063F-1587-4E43-81F1-B948E807363F}")
        _methods_ = [COMMETHOD([], HRESULT, "Activate", (["in"], POINTER(GUID)), (["in"], DWORD), (["in"], c_void_p),
                               (["out"], POINTER(POINTER(IAudioSessionManager))))]

    class IMMDeviceCollection(IUnknown):
        _iid_ = GUID("{0BD7A1BE-7A1A-44DB-8397-CC5392387B5E}")
        _methods_ = [COMMETHOD([], HRESULT, "GetCount", (["out"], POINTER(c_uint))),
                     COMMETHOD([], HRESULT, "Item", (["in"], c_uint), (["out"], POINTER(POINTER(IMMDevice))))]

    class IMMDeviceEnumerator(IUnknown):
        _iid_ = GUID("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
        _methods_ = [COMMETHOD([], HRESULT, "EnumAudioEndpoints", (["in"], c_int), (["in"], DWORD),
                               (["out"], POINTER(POINTER(IMMDeviceCollection))))]

    devices = CoCreateInstance(GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}"), IMMDeviceEnumerator,
                               CLSCTX_ALL).EnumAudioEndpoints(0, 1)  # render endpoints, active
    for i in range(devices.GetCount()):
        manager = devices.Item(i).Activate(IAudioSessionManager._iid_, CLSCTX_ALL, None)
        manager.GetSimpleAudioVolume(None, 0).SetMute(muted, None)  # None = the process's default session


class Toggle(QAbstractButton):
    """Pill switch with text (a stylesheet can't give QCheckBox a sliding knob)."""

    def __init__(self, checked):
        super().__init__()
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self):
        return QSize(48 + self.fontMetrics().horizontalAdvance(self.text()), 24)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(ACCENT if self.isChecked() else BORDER))
        p.drawRoundedRect(0, 2, 38, 20, 10, 10)
        p.setBrush(QColor(TEXT))
        p.drawEllipse(QPoint(28 if self.isChecked() else 10, 12), 8, 8)
        p.setPen(QColor(TEXT))
        p.drawText(QRect(48, 0, self.width() - 48, self.height()), Qt.AlignmentFlag.AlignVCenter, self.text())


class Combo(QComboBox):
    """Dropdown whose popup list is exactly as wide as the field."""

    def __init__(self):
        super().__init__()
        self.setItemDelegate(QStyledItemDelegate(self))  # lets the stylesheet style the items
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(6)

    def showPopup(self):
        super().showPopup()
        self.view().window().setFixedWidth(self.width())

    def paintEvent(self, _):  # like QComboBox, but long device names end in "…" instead of being cut off
        p, opt = QStylePainter(self), QStyleOptionComboBox()
        self.initStyleOption(opt)
        p.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, opt)
        room = self.style().subControlRect(QStyle.ComplexControl.CC_ComboBox, opt,
                                           QStyle.SubControl.SC_ComboBoxEditField, self).width()
        opt.currentText = self.fontMetrics().elidedText(opt.currentText, Qt.TextElideMode.ElideRight, room - 4)
        p.drawControl(QStyle.ControlElement.CE_ComboBoxLabel, opt)

    def fill(self, items, keep):
        self.blockSignals(True)
        self.clear()
        self.addItems(items)
        self.setCurrentIndex(max(self.findText(keep), 0))
        self.blockSignals(False)


class Live(QWidget):
    """Video window: paints frames aspect-fit, hover bar with mute / listen / volume / settings at the bottom."""

    def __init__(self, main):
        super().__init__()
        self.main, self.frame, self.image = main, None, QImage()
        self.setWindowTitle(f"{APP} - Live")
        self.resize(1280, 720)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.bar = QFrame(self, objectName="bar")
        lay = QHBoxLayout(self.bar)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)
        self.mute = QToolButton(iconSize=QSize(20, 20))
        self.mute.clicked.connect(main.toggle_mute)
        self.listen = QToolButton(iconSize=QSize(20, 20))
        self.listen.clicked.connect(main.listen.toggle)
        self.vol = QSlider(Qt.Orientation.Horizontal, minimum=0, maximum=100)
        self.vol.setFixedWidth(200)
        self.vol.valueChanged.connect(main.vol.setValue)
        self.pct = label()
        self.pct.setFixedWidth(52)
        gear = QToolButton(icon=icon("settings"), iconSize=QSize(20, 20))
        gear.clicked.connect(main.show_settings)
        for w in (self.mute, self.listen, self.vol, self.pct, gear):
            lay.addWidget(w)
        self.bar.hide()
        self.bar.installEventFilter(self)
        self.hider = QTimer(self, singleShot=True, interval=1500)
        self.hider.timeout.connect(self.bar.hide)

    def show_frame(self, frame):
        self.frame = frame
        self.update()

    def paintEvent(self, _):
        if self.frame is not None:  # convert only frames that actually get painted; update() coalesces the rest
            self.image, self.frame = self.frame.toImage(), None
            self.main.shown += 1
        p = QPainter(self)
        p.fillRect(self.rect(), Qt.GlobalColor.black)
        if not self.image.isNull():
            r = QRect(QPoint(), self.image.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio))
            r.moveCenter(self.rect().center())
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            p.drawImage(r, self.image)

    def reveal(self):
        self.bar.adjustSize()
        self.bar.move((self.width() - self.bar.width()) // 2, self.height() - self.bar.height() - 24)
        self.bar.show()
        self.hider.start()

    def mouseMoveEvent(self, _):
        self.reveal()

    def enterEvent(self, _):
        self.reveal()

    def resizeEvent(self, _):
        if self.bar.isVisible():
            self.reveal()

    def eventFilter(self, obj, ev):  # keep the bar up while the cursor is on it
        if ev.type() == QEvent.Type.Enter:
            self.hider.stop()
        elif ev.type() == QEvent.Type.Leave:
            self.hider.start()
        return False

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key.Key_Escape:
            self.close()

    def closeEvent(self, _):
        self.main.stop()


class Main(QWidget):
    def __init__(self):
        super().__init__(objectName="main")
        self.setWindowTitle(APP)
        self.st = QSettings(APP, APP)
        default_lang = "de" if QLocale.system().language() == QLocale.Language.German else "en"
        self.lang = self.st.value("lang", default_lang)
        self.texts = []  # (widget, key) pairs re-labelled on language switch
        self.session = self.camera = None
        self.muted = False  # full mute incl. stream; per session on purpose, a silent stream after restart confuses
        self.frames, self.shown, self.last_frame, self.t0 = deque(), 0, 0.0, 0.0
        self.status_key, self.status_args, self.status_kind = "ready", (), "idle"
        self.sink = QVideoSink(self)
        self.sink.videoFrameChanged.connect(self.on_frame)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 20)
        root.setSpacing(12)
        root.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

        head = QFrame(objectName="head")
        h = QHBoxLayout(head)
        h.setContentsMargins(16, 12, 16, 12)
        logo = QLabel()
        logo.setPixmap(QIcon(str(ASSETS / "icon.png")).pixmap(22, 22))
        h.addWidget(logo)
        h.addWidget(label(f'capture<span style="color:{ACCENT}">MAX</span>', "logo"))
        h.addStretch()
        h.addWidget(self.tr_(label(), "subtitle"))
        self.lang_box = Combo()
        self.lang_box.setObjectName("lang")
        self.lang_box.addItems(LANGS.values())
        self.lang_box.setCurrentIndex(list(LANGS).index(self.lang))
        self.lang_box.currentIndexChanged.connect(lambda i: self.set_lang(list(LANGS)[i]))
        h.addSpacing(12)
        h.addWidget(self.lang_box)
        root.addWidget(head)

        cols = QHBoxLayout()
        cols.setSpacing(16)
        root.addLayout(cols)
        card = self.card(cols, "video")
        self.video = self.field(card, "device")
        row = QHBoxLayout()
        row.setSpacing(8)
        card.addLayout(row)
        self.res, self.fps = self.field(row, "res"), self.field(row, "fps")
        card.addStretch()

        card = self.card(cols, "audio")
        self.ain = self.field(card, "input")
        self.aout = self.field(card, "output")
        self.vol_lbl, self.vol = self.slider(card, 0, 100, int(self.st.value("volume", 100)))
        self.listen = self.tr_(Toggle(self.st.value("listen", True, type=bool)), "listen")
        card.addWidget(self.listen)
        card.addStretch()

        card = self.card(cols, "advanced")
        self.buf_lbl, self.buf = self.slider(card, 0, 2000, int(self.st.value("buf", 0)), step=50)
        self.auto_exp = self.tr_(Toggle(self.st.value("auto_exp", True, type=bool)), "auto_exp")
        card.addWidget(self.auto_exp)
        self.exp_lbl, self.exp = self.slider(card, -13, -1, int(self.st.value("exp", -6)))
        card.addStretch()
        if sys.platform == "darwin":  # AVFoundation exposes no exposure control for USB cameras
            self.auto_exp.setEnabled(False)

        self.btn = self.tr_(QPushButton(objectName="start", cursor=Qt.CursorShape.PointingHandCursor), "start")
        self.btn.clicked.connect(self.toggle)
        root.addWidget(self.btn)
        self.status = QLabel(objectName="status")
        root.addWidget(self.status)

        self.live = Live(self)
        self.video.currentIndexChanged.connect(self.fill_res)
        self.res.currentIndexChanged.connect(self.fill_fps)
        self.vol.valueChanged.connect(self.apply_audio)
        self.listen.toggled.connect(self.apply_audio)
        self.buf.valueChanged.connect(self.update_labels)
        self.exp.valueChanged.connect(self.update_labels)
        self.auto_exp.toggled.connect(self.update_labels)
        self.devices = QMediaDevices(self)
        for sig in (self.devices.videoInputsChanged, self.devices.audioInputsChanged,
                    self.devices.audioOutputsChanged):
            sig.connect(self.refresh)
        self.refresh()
        self.set_lang(self.lang)
        self.ticker = QTimer(self, interval=1000)
        self.ticker.timeout.connect(self.tick)
        self.ticker.start()

    # ---- building blocks
    def tr_(self, widget, key):
        self.texts.append((widget, key))
        return widget

    def t(self, key, *args):
        return TR[self.lang][key].format(*args)

    def card(self, cols, title):
        frame = QFrame(objectName="card")
        frame.setMinimumWidth(330)
        cols.addWidget(frame, 1)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(16, 14, 16, 16)
        lay.setSpacing(6)
        lay.addWidget(self.tr_(label(role="title"), title))
        lay.addSpacing(4)
        return lay

    def field(self, lay, key):
        box = QVBoxLayout()
        box.setSpacing(4)
        box.addWidget(self.tr_(label(), key))
        combo = Combo()
        box.addWidget(combo)
        box.addSpacing(6)
        lay.addLayout(box)
        return combo

    def slider(self, lay, lo, hi, value, step=1):
        lbl = label()
        sl = QSlider(Qt.Orientation.Horizontal, minimum=lo, maximum=hi, singleStep=step, pageStep=step, value=value)
        lay.addWidget(lbl)
        lay.addWidget(sl)
        lay.addSpacing(6)
        return lbl, sl

    # ---- language, labels, status
    def set_lang(self, lang):
        self.lang = lang
        self.st.setValue("lang", lang)
        for widget, key in self.texts:
            widget.setText(self.t(key))
            widget.updateGeometry()
        self.btn.setText(self.t("stop" if self.camera else "start"))
        self.live.mute.setToolTip(self.t("tip_mute"))
        self.live.listen.setToolTip(self.t("tip_listen"))
        self.refresh()  # the "Off" audio entry is translated too
        self.update_labels()
        self.apply_audio()
        self.set_status(self.status_key, *self.status_args, kind=self.status_kind)

    def update_labels(self):
        b = self.buf.value()
        self.buf_lbl.setText(self.t("delay", b) + (self.t("low_latency") if b == 0 else ""))
        manual_ok = self.auto_exp.isEnabled()
        self.exp.setEnabled(manual_ok and not self.auto_exp.isChecked())
        self.exp_lbl.setEnabled(self.exp.isEnabled())
        self.exp_lbl.setText(self.t("exposure", 2 ** -self.exp.value()) if manual_ok else self.t("exp_na"))

    def set_status(self, key, *args, kind="idle"):
        self.status_key, self.status_args, self.status_kind = key, args, kind
        self.status.setText(f"●  {self.t(key, *args)}")
        self.status.setStyleSheet(f"color: {STATUS_COLORS[kind]};")

    # ---- devices
    def refresh(self):
        self.cams, self.ains, self.aouts = (QMediaDevices.videoInputs(), QMediaDevices.audioInputs(),
                                            QMediaDevices.audioOutputs())
        self.video.fill([d.description() for d in self.cams], self.video.currentText() or self.st.value("video", ""))
        off = self.t("off")
        keep_in = self.ain.currentText() if self.ain.count() else self.st.value("audio_in", off)
        self.ain.fill([off] + [d.description() for d in self.ains],
                      off if keep_in in (TR["de"]["off"], TR["en"]["off"]) else keep_in)
        self.aout.fill([d.description() for d in self.aouts], self.aout.currentText() or self.st.value(
            "audio_out", QMediaDevices.defaultAudioOutput().description()))
        self.fill_res()

    def formats(self):
        return self.cams[self.video.currentIndex()].videoFormats() if self.cams else []

    def fill_res(self):
        sizes = sorted({(f.resolution().width(), f.resolution().height()) for f in self.formats()},
                       key=lambda s: s[0] * s[1], reverse=True)
        self.res.fill([f"{w}x{h}" for w, h in sizes], self.res.currentText() or self.st.value("res", ""))
        self.fill_fps()

    def fill_fps(self):
        rates = sorted({round(f.maxFrameRate()) for f in self.formats()
                        if f"{f.resolution().width()}x{f.resolution().height()}" == self.res.currentText()},
                       reverse=True)
        self.fps.fill([str(r) for r in rates], self.fps.currentText() or self.st.value("fps", ""))

    def pick_format(self):
        """Exact resolution, closest frame rate; on ties prefer MJPG (raw formats choke USB 2 bandwidth)."""
        fps = int(self.fps.currentText())
        cands = [f for f in self.formats() if f"{f.resolution().width()}x{f.resolution().height()}" == self.res.currentText()]
        return min(cands, key=lambda f: (abs(f.maxFrameRate() - fps), f.pixelFormat() != JPEG))

    # ---- capture
    def toggle(self):
        self.stop() if self.camera else self.start()

    def start(self):
        if not self.cams or not self.res.currentText():
            return self.set_status("no_device", kind="err")
        self.save()
        dev, manual = self.cams[self.video.currentIndex()], self.auto_exp.isEnabled() and not self.auto_exp.isChecked()
        if sys.platform == "win32" and (manual or self.st.value("exp_was_manual", False, type=bool)):
            windows_exposure(dev.description(), manual, self.exp.value())
        self.st.setValue("exp_was_manual", manual)
        self.camera = QCamera(dev)
        self.camera.setCameraFormat(self.pick_format())
        self.camera.errorOccurred.connect(lambda _, msg: self.set_status("error", msg, kind="err"))
        if manual and sys.platform != "win32":
            self.camera.activeChanged.connect(lambda on: on and self.qt_exposure())
        self.session = QMediaCaptureSession(self)
        self.session.setCamera(self.camera)
        self.session.setVideoSink(self.sink)
        if self.ain.currentIndex() > 0 and self.aouts:
            self.session.setAudioInput(QAudioInput(self.ains[self.ain.currentIndex() - 1], self.session))
            self.session.setAudioOutput(QAudioOutput(self.aouts[self.aout.currentIndex()], self.session))
        self.apply_audio()
        self.frames.clear()
        self.shown, self.t0 = 0, time.monotonic()
        self.last_frame = self.t0
        self.set_status("starting")
        self.camera.start()
        self.live.frame, self.live.image = None, QImage()
        self.live.show()
        self.live.raise_()
        self.set_running(True)

    def qt_exposure(self):
        if self.camera.isExposureModeSupported(QCamera.ExposureMode.ExposureManual):
            self.camera.setExposureMode(QCamera.ExposureMode.ExposureManual)
            self.camera.setManualExposureTime(2.0 ** self.exp.value())
        else:
            self.set_status("exp_na", kind="err")

    def stop(self):
        if not self.camera:
            return
        self.camera.stop()
        if sys.platform == "win32" and self.session.audioOutput():  # mixer mute outlives us, leave it clean
            windows_mixer_mute(False)
        self.session.deleteLater()
        self.camera.deleteLater()
        self.session = self.camera = None
        self.frames.clear()
        self.live.hide()
        self.set_running(False)
        if self.status_kind != "err":
            self.set_status("ready")

    def set_running(self, on):
        self.btn.setText(self.t("stop" if on else "start"))
        self.btn.setProperty("running", on)
        self.btn.style().unpolish(self.btn)
        self.btn.style().polish(self.btn)

    def on_frame(self, frame):
        """Delay buffer: show the oldest frame that is at least `delay` old, drop older ones (no backlog).
        Kept cheap on purpose: frames arrive as queued signals, a slow slot here makes them pile up = lag."""
        now = time.monotonic()
        self.last_frame, delay = now, self.buf.value() / 1000
        self.frames.append((now, frame))
        while len(self.frames) > 1 and now - self.frames[1][0] >= delay:
            self.frames.popleft()
        if now - self.frames[0][0] >= delay:
            self.live.show_frame(self.frames.popleft()[1])

    def tick(self):
        if not self.camera:
            return
        now = time.monotonic()
        if now - self.last_frame > 3:
            self.set_status("no_frames", kind="err")
        elif self.shown:
            size = self.live.image.size()
            self.set_status("running", f"{size.width()}x{size.height()}", self.shown / (now - self.t0), kind="ok")
        self.shown, self.t0 = 0, now

    def apply_audio(self):
        """Settings card and hover bar share volume/listen; the capture session's output follows both.
        Mute silences the app itself (stream too). Listen off on Windows only mutes it in the volume mixer,
        so window capture (Discord) keeps the audio."""
        vol, on = self.vol.value(), self.listen.isChecked()
        self.vol_lbl.setText(self.t("volume", vol))
        self.live.vol.setValue(vol)
        self.live.pct.setText(f"{vol} %")
        self.live.mute.setIcon(icon("muted" if self.muted else "volume"))
        self.live.listen.setIcon(icon("listen" if on else "deaf"))
        out = self.session.audioOutput() if self.session else None
        if out:
            out.setVolume(vol / 100)
            if sys.platform == "win32":
                out.setMuted(self.muted)
                windows_mixer_mute(not on)
            else:
                out.setMuted(self.muted or not on)

    def toggle_mute(self):
        self.muted = not self.muted
        self.apply_audio()

    def show_settings(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def save(self):
        for key, value in (("video", self.video.currentText()), ("res", self.res.currentText()),
                           ("fps", self.fps.currentText()), ("audio_in", self.ain.currentText()),
                           ("audio_out", self.aout.currentText()), ("volume", self.vol.value()),
                           ("listen", self.listen.isChecked()), ("buf", self.buf.value()),
                           ("auto_exp", self.auto_exp.isChecked()), ("exp", self.exp.value())):
            self.st.setValue(key, value)

    def closeEvent(self, _):
        self.save()
        self.stop()
        QApplication.quit()


def main():
    if sys.platform == "win32":  # own taskbar entry + icon instead of python's
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP)
    app = QApplication(sys.argv)
    app.setApplicationName(APP)
    app.setStyle("Fusion")
    pal = QPalette()
    for role, color in ((QPalette.ColorRole.Window, BG), (QPalette.ColorRole.Base, FIELD),
                        (QPalette.ColorRole.Text, TEXT), (QPalette.ColorRole.WindowText, TEXT),
                        (QPalette.ColorRole.Button, SURFACE), (QPalette.ColorRole.ButtonText, TEXT),
                        (QPalette.ColorRole.Highlight, ACCENT)):
        pal.setColor(role, QColor(color))
    app.setPalette(pal)
    app.setStyleSheet(QSS)
    app.setWindowIcon(QIcon(str(ASSETS / "icon.png")))
    w = Main()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
