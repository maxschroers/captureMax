"""captureMax: low-latency live viewer for capture cards and webcams on Windows, macOS and Linux (Qt Multimedia)."""
import functools
import json
import sys
import time
from collections import deque
from pathlib import Path

from PySide6.QtCore import (QByteArray, QEasingCurve, QEvent, QLocale, QPoint, QPointF, QPropertyAnimation, QRect,
                            QRectF, QSettings, QSize, Qt, QTimer, QUrl, QVariantAnimation)
from PySide6.QtGui import QColor, QDesktopServices, QFont, QFontMetrics, QIcon, QImage, QPainter, QPalette, QPen, QPixmap
from PySide6.QtMultimedia import (QAudioFormat, QAudioSink, QAudioSource, QCamera, QMediaCaptureSession,
                                  QMediaDevices, QVideoFrame, QVideoFrameFormat, QVideoSink)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import (QAbstractButton, QApplication, QComboBox, QFrame, QGraphicsOpacityEffect, QGridLayout, QHBoxLayout, QLabel, QLayout, QMessageBox,
                               QProxyStyle, QPushButton, QSlider, QStyle, QStyledItemDelegate, QStyleOptionComboBox,
                               QStylePainter, QToolButton, QVBoxLayout, QWidget)

APP = "captureMax"
VERSION = "dev"  # release builds: CI writes the git tag here (.github/workflows/release.yml)
REPO = "maxschroers/captureMax"
ASSETS = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "assets"
# Discord dark theme (2025 refresh), sampled from the desktop client
ACCENT, ACCENT_HOVER, ACCENT_DEEP = "#5865f2", "#4752c4", "#3c45a5"  # blurple
# settings, measured from Discord's "Sprach- & Videochat" page: #202024 content, #1a1a1e panels, #1c1c20 inputs with a
# 1px #343439 border, 4px blurple slider with a round white knob, blurple switches, #2e2e33 dividers / grey buttons
BG, SURFACE, FIELD, BORDER, TRACK, TITLEBAR = "#202024", "#1a1a1e", "#1c1c20", "#343439", "#3f3f46", "#121214"
TEXT, HEADER, MUTED, DIM = "#dbdee1", "#f2f3f5", "#94959c", "#5c5d63"
GREEN, GREEN_HOVER, FOCUS = "#23a55a", "#1a7f45", "#00a8fc"
HOVER, SELECTED, GREY_BUTTON = "#2a2a2f", "#2e2e33", "#2e2e33"
# stream viewer: black control strip, grouped buttons, red end button, grey side icons
DC_GROUP, DC_GROUP_BORDER, DC_RED, DC_RED_HOVER = "#0a0a0c", "#26262b", "#d22d39", "#a8232d"
DC_TEXT, DC_ICON, DC_PILL, DC_TOOLTIP = TEXT, "#d4d5d9", "#4f505a", "#111214"
STATUS_COLORS = {"idle": MUTED, "ok": GREEN, "err": "#f23f43"}
JPEG = QVideoFrameFormat.PixelFormat.Format_Jpeg
LANGS = {"de": "Deutsch", "en": "English"}
FLAGS = {  # 3:2 artwork, drawn as svg (Windows has no flag emoji)
    "de": '<rect width="60" height="40" fill="#ffce00"/><rect width="60" height="26.7" fill="#dd0000"/>'
          '<rect width="60" height="13.3" fill="#000"/>',
    "en": '<rect width="60" height="40" fill="#012169"/>'
          '<path d="M0 0L60 40M60 0L0 40" stroke="#fff" stroke-width="8"/>'
          '<path d="M0 0L60 40M60 0L0 40" stroke="#c8102e" stroke-width="3"/>'
          '<path d="M30 0v40M0 20h60" stroke="#fff" stroke-width="12"/>'
          '<path d="M30 0v40M0 20h60" stroke="#c8102e" stroke-width="7"/>',
}

TR = {
    "de": {
        "subtitle": "Capture-Card- & Webcam-Viewer", "video": "Video", "audio": "Audio", "advanced": "Erweitert",
        "device": "Gerät", "res": "Auflösung", "fps": "FPS", "input": "Eingang", "output": "Ausgabe (Monitor)",
        "off": "Aus", "volume": "Lautstärke: {} %", "listen": "Ausgabe aktivieren",
        "delay": "Verzögerung: {} ms", "low_latency": "  (Low-Latency)", "auto_exp": "Auto-Belichtung (Webcam)",
        "exposure": "Belichtung: 1/{} s  (kürzer = dunkler, mehr FPS)",
        "exp_na": "Belichtung wird auf diesem System nicht unterstützt",
        "start": "Start", "save": "Speichern", "ready": "bereit", "starting": "starte...",
        "running": "läuft · {} · {:.0f} fps",
        "no_device": "Fehler: kein Videogerät gefunden", "no_frames": "Fehler: kein Bild vom Gerät (belegt?)",
        "error": "Fehler: {}",
        "update": "Update auf v{} verfügbar",
        "update_ask": "Version {} ist verfügbar (installiert: {}).\nJetzt herunterladen?", "yes": "Ja", "no": "Nein",
        "discard": "Einstellungen wurden geändert. Ohne Speichern schließen?",
        "tip_stop": "Stream beenden", "tip_mute": "Ton aus (M)", "tip_unmute": "Ton an (M)",
        "tip_settings": "Einstellungen", "tip_full": "Vollbild (F)",
        "tip_window": "Vollbild beenden (Esc)", "tip_volume": "Lautstärke (↑ ↓)",
    },
    "en": {
        "subtitle": "capture card & webcam viewer", "video": "Video", "audio": "Audio", "advanced": "Advanced",
        "device": "Device", "res": "Resolution", "fps": "FPS", "input": "Input", "output": "Output (monitor)",
        "off": "Off", "volume": "Volume: {} %", "listen": "Enable output",
        "delay": "Delay: {} ms", "low_latency": "  (low latency)", "auto_exp": "Auto exposure (webcam)",
        "exposure": "Exposure: 1/{} s  (shorter = darker, more FPS)",
        "exp_na": "Exposure control is not supported on this system",
        "start": "Start", "save": "Save", "ready": "ready", "starting": "starting...",
        "running": "running · {} · {:.0f} fps",
        "no_device": "Error: no video device found", "no_frames": "Error: no picture from device (in use?)",
        "error": "Error: {}",
        "update": "Update to v{} available",
        "update_ask": "Version {} is available (installed: {}).\nDownload it now?", "yes": "Yes", "no": "No",
        "discard": "Settings were changed. Close without saving?",
        "tip_stop": "Stop stream", "tip_mute": "Mute (M)", "tip_unmute": "Unmute (M)", "tip_settings": "Settings",
        "tip_full": "Fullscreen (F)", "tip_window": "Exit fullscreen (Esc)",
        "tip_volume": "Volume (↑ ↓)",
    },
}

ICONS = {  # 24px stroke icons, rendered via Qt's SVG image plugin; FILL = drawn solid in the icon's colour
    "volume_low": '<path d="M11 5 6 9H3v6h3l5 4V5z" fill="FILL"/><path d="M15.5 9.5a3.5 3.5 0 0 1 0 5"/>',  # Discord's
    "volume": '<path d="M11 5 6 9H3v6h3l5 4V5z" fill="FILL"/><path d="M15.5 9.5a3.5 3.5 0 0 1 0 5"/>'
              '<path d="M17.6 7.4a6.5 6.5 0 0 1 0 9.2"/>',  # second wave from 50 %
    "muted": '<path d="M11 5 6 9H3v6h3l5 4V5z" fill="FILL"/><path d="M16 9.5l5 5M21 9.5l-5 5"/>',
    "screen": '<rect x="3" y="4" width="18" height="12" rx="2" fill="FILL"/><path d="M12 16v4M8 20h8"/>',
    "stop": '<rect x="6" y="6" width="12" height="12" rx="2" fill="FILL"/>',
    "fullscreen": '<path d="M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2'
                  'M8 20H6a2 2 0 0 1-2-2v-2"/>',  # Discord: four corners, rounded joints
    "windowed": '<path d="M8 4v2a2 2 0 0 1-2 2H4M16 4v2a2 2 0 0 0 2 2h2M16 20v-2a2 2 0 0 1 2-2h2'
                'M8 20v-2a2 2 0 0 0-2-2H4"/>',
    "settings": '<path d="M4 6h9M19 6h1M4 12h3M13 12h7M4 18h11M21 18h-1"/>'
                '<circle cx="16" cy="6" r="2.5"/><circle cx="10" cy="12" r="2.5"/><circle cx="18" cy="18" r="2.5"/>',
}

QSS = f"""
* {{ font-family: "Segoe UI Variable Text", "Segoe UI", "SF Pro Text", "Helvetica Neue", "Noto Sans", "DejaVu Sans",
     sans-serif; font-size: 14px; color: {TEXT}; }}
QWidget#main {{ background: {BG}; }}
QFrame#card, QFrame#head {{ background: {SURFACE}; border: none; border-radius: 8px; }}
QLabel {{ background: transparent; }}
QLabel[role="title"] {{ color: {HEADER}; font-size: 20px; font-weight: 600; }}
QLabel[role="logo"] {{ color: {HEADER}; font-size: 17px; font-weight: 600; }}
QLabel[role="label"] {{ color: {HEADER}; font-size: 14px; font-weight: 600; }}
QLabel[role="hint"] {{ color: {MUTED}; font-size: 13px; }}
QLabel[role="hint"]:disabled, QLabel[role="label"]:disabled {{ color: {DIM}; }}
QComboBox {{ background: {FIELD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 0 10px; min-height: 30px;
             font-weight: 600; combobox-popup: 0; }}
QComboBox:hover, QComboBox:on {{ border-color: #4a4a50; }}
QComboBox:focus {{ border-color: {FOCUS}; }}
QComboBox:disabled {{ color: {DIM}; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox::down-arrow {{ image: url("{(ASSETS / "chevron.svg").as_posix()}"); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{ background: {FIELD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 4px;
                               outline: none; }}
QComboBox QAbstractItemView::item {{ min-height: 32px; padding: 0 8px; border-radius: 6px; font-weight: 600; }}
QComboBox QAbstractItemView::item:hover {{ background: {HOVER}; }}
QComboBox QAbstractItemView::item:selected {{ background: {SELECTED}; color: {HEADER}; }}
QComboBox#lang {{ min-height: 28px; }}
QSlider:horizontal {{ min-height: 18px; }}  /* room for the 14px knob, else it gets clipped */
QSlider::groove:horizontal {{ height: 4px; background: {TRACK}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: #fff; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }}
QSlider::handle:horizontal:focus {{ background: {FOCUS}; }}  /* keyboard focus (WCAG 2.4.7) */
QSlider::sub-page:horizontal:disabled {{ background: {TRACK}; }}
QSlider::handle:horizontal:disabled {{ background: {DIM}; }}
QPushButton#start {{ background: {ACCENT}; border: none; border-radius: 8px; min-height: 40px; font-size: 14px;
                     font-weight: 600; color: #fff; }}
QPushButton#start:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#start:pressed {{ background: {ACCENT_DEEP}; }}
QPushButton#start:focus {{ border: 2px solid {FOCUS}; }}
QPushButton#start:disabled {{ background: rgba(88, 101, 242, 120); color: rgba(255, 255, 255, 120); }}
QLabel#status {{ background: {SURFACE}; border-radius: 8px; min-height: 32px; padding: 0 14px; font-size: 13px; }}
QPushButton#update {{ background: {GREEN}; border: none; border-radius: 8px; min-height: 32px; padding: 0 14px;
                      font-size: 13px; font-weight: 600; color: #fff; }}
QPushButton#update:hover {{ background: {GREEN_HOVER}; }}
QPushButton#update:focus {{ border: 2px solid {FOCUS}; }}
QMessageBox {{ background: {BG}; }}
QMessageBox QPushButton {{ background: {GREY_BUTTON}; border: none; border-radius: 8px; min-height: 32px;
                           min-width: 90px; padding: 0 16px; color: #fff; font-weight: 600; }}
QMessageBox QPushButton:hover {{ background: #3a3a40; }}
QMessageBox QPushButton#primary {{ background: {ACCENT}; }}
QMessageBox QPushButton#primary:hover {{ background: {ACCENT_HOVER}; }}
QMessageBox QPushButton:focus {{ border: 2px solid {FOCUS}; }}
QFrame#bar {{ background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 rgba(0, 0, 0, 0),
                                          stop: 1 rgba(0, 0, 0, 200)); border: none; }}  /* soft fade over video */
QFrame#bar QToolButton {{ background: transparent; border: none; border-radius: 8px; }}
QFrame#bar QToolButton:hover {{ background: rgba(255, 255, 255, 26); }}
QFrame#group {{ background: {DC_GROUP}; border: 1px solid {DC_GROUP_BORDER}; border-radius: 12px; }}
QFrame#bar QToolButton#stop {{ background: {DC_RED}; border-radius: 12px; }}
QFrame#bar QToolButton#stop:hover {{ background: {DC_RED_HOVER}; }}
QFrame#bar QToolButton:focus {{ border: 2px solid {FOCUS}; }}
QFrame#chip {{ background: {DC_GROUP}; border-radius: 8px; }}
QFrame#chip QLabel {{ color: {DC_TEXT}; font-size: 14px; }}
QFrame#pill {{ background: transparent; }}
QFrame#pill QLabel {{ color: #fff; font-size: 13px; font-weight: bold; padding: 2px 8px; }}
QFrame#pill QLabel#quality {{ background: {DC_PILL}; border-top-left-radius: 10px; border-bottom-left-radius: 10px; }}
QFrame#pill QLabel#live {{ background: {DC_RED}; border-top-right-radius: 10px; border-bottom-right-radius: 10px; }}
/* Discord's stream volume: a 6px bar in a 2px black frame, round on top, standing flush on the control strip */
QFrame#volpop {{ background: #000; border-radius: 5px; }}
QToolTip {{ background: {DC_TOOLTIP}; color: {DC_TEXT}; border: none; padding: 6px 10px; font-size: 13px;
            font-weight: 600; }}
"""


def svg_icon(svg):
    return QIcon(QPixmap.fromImage(QImage.fromData(QByteArray(svg.encode()), "SVG")))


def icon(name, color=TEXT, weight=2):
    return svg_icon(f'<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" '
                    f'stroke="{color}" stroke-width="{weight}" stroke-linecap="round" stroke-linejoin="round">'
                    f'{ICONS[name].replace("FILL", color)}</svg>')


def flag(lang):
    return svg_icon(f'<svg xmlns="http://www.w3.org/2000/svg" width="60" height="40" viewBox="0 0 60 40">'
                    f'{FLAGS[lang]}</svg>')


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


@functools.cache
def windows_has_exposure(name):
    """Webcams offer DirectShow's camera control (exposure range), capture cards and virtual cameras don't."""
    from ctypes import POINTER, c_long
    from comtypes import COMMETHOD, GUID, HRESULT, IUnknown
    from pygrabber.dshow_graph import FilterGraph, SystemDeviceEnum
    from pygrabber.dshow_ids import DeviceCategories

    class IAMCameraControl(IUnknown):
        _iid_ = GUID("{C6E13370-30AC-11d0-A18C-00A0C9118956}")
        _methods_ = [COMMETHOD([], HRESULT, "GetRange", (["in"], c_long, "prop"),
                               *[(["out"], POINTER(c_long), n) for n in ("lo", "hi", "step", "default", "flags")])]

    names = FilterGraph().get_input_devices()
    if name not in names:
        return True  # unknown: keep the controls rather than hide them wrongly
    try:
        flt, _ = SystemDeviceEnum().get_filter_by_index(DeviceCategories.VideoInputDevice, names.index(name))
        flt.QueryInterface(IAMCameraControl).GetRange(4)  # 4 = CameraControl_Exposure
        return True
    except Exception:
        return False


def version_key(v):
    """0.10.2 -> (0, 10, 2), so versions compare numerically, not as text."""
    return tuple(int(part) for part in v.split("."))


def dark_titlebar(widget):
    """Windows draws a light title bar by default: ask DWM for a dark one in our background colour (colour: Win 11)."""
    if sys.platform != "win32":
        return
    import ctypes
    bg = QColor(TITLEBAR)
    for attr, value in ((20, 1), (35, bg.red() | bg.green() << 8 | bg.blue() << 16)):  # dark mode, caption colour
        ctypes.windll.dwmapi.DwmSetWindowAttribute(int(widget.winId()), attr, ctypes.byref(ctypes.c_int(value)), 4)


class JumpStyle(QProxyStyle):
    """Fusion, but a click on a slider jumps there instead of paging toward it."""

    def styleHint(self, hint, opt=None, widget=None, ret=None):
        if hint == QStyle.StyleHint.SH_Slider_AbsoluteSetButtons:
            return Qt.MouseButton.LeftButton.value
        return super().styleHint(hint, opt, widget, ret)


class Toggle(QAbstractButton):
    """Pill switch with text (a stylesheet can't give QCheckBox a sliding knob)."""

    def __init__(self, checked):
        super().__init__()
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)  # Tab + Space; a mouse click doesn't leave a focus ring
        self.pos_ = float(checked)  # knob position 0..1, slides on toggle
        self.anim = QVariantAnimation(self, duration=160, easingCurve=QEasingCurve.Type.OutCubic)
        self.anim.valueChanged.connect(self.slide)
        self.toggled.connect(self.animate)

    def animate(self, on):
        self.anim.stop()
        self.anim.setStartValue(self.pos_)
        self.anim.setEndValue(float(on))
        self.anim.start()

    def slide(self, pos):
        self.pos_ = pos
        self.update()

    def sizeHint(self):
        font = self.font()
        font.setWeight(QFont.Weight.DemiBold)  # measured like it's painted
        return QSize(54 + QFontMetrics(font).horizontalAdvance(self.text()), 24)

    def paintEvent(self, _):
        """Discord switch: dark track with a 1px border when off, blurple when on, plain white knob."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(1 if self.isEnabled() else 0.4)
        off, on = QColor(FIELD).getRgbF(), QColor(ACCENT).getRgbF()
        p.setBrush(QColor.fromRgbF(*(a + (b - a) * self.pos_ for a, b in zip(off, on))))
        border = QColor(BORDER)
        border.setAlphaF(1 - self.pos_)  # the border fades out as the track fills
        p.setPen(QPen(border, 1))
        track = QRectF(0.5, 2.5, 38, 19)
        p.drawRoundedRect(track, 9.5, 9.5)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#fff"))
        p.drawEllipse(QPointF(10 + 19 * self.pos_, 12), 7, 7)
        if self.hasFocus():  # keyboard focus ring (WCAG 2.4.7)
            p.setPen(QPen(QColor(FOCUS), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(track, 9.5, 9.5)
        p.setPen(QColor(HEADER))
        font = p.font()
        font.setWeight(QFont.Weight.DemiBold)  # Discord's switch rows are labelled in semibold white
        p.setFont(font)
        p.drawText(QRect(50, 0, self.width() - 50, self.height()), Qt.AlignmentFlag.AlignVCenter, self.text())


class VolumeBar(QSlider):
    """Discord's stream volume: a slim pill track with a blurple pill rising from the bottom, both ends round
    (QSS can't round the fill's top where it meets the handle). Click or drag anywhere sets the level."""

    def __init__(self):
        super().__init__(Qt.Orientation.Vertical, minimum=0, maximum=100)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        r = QRectF(self.rect())
        radius = r.width() / 2
        p.setBrush(QColor("#3e3f40"))
        p.drawRoundedRect(r, radius, radius)
        level = r.height() * (self.value() - self.minimum()) / (self.maximum() - self.minimum())
        if level > 0:
            p.setBrush(QColor(FOCUS if self.hasFocus() else ACCENT))  # keyboard focus shows in the fill
            p.drawRoundedRect(QRectF(r.left(), r.bottom() - level, r.width(), level), radius, min(radius, level / 2))

    def mousePressEvent(self, ev):
        self.set_from(ev.position().y())

    def mouseMoveEvent(self, ev):  # only while pressed (no mouse tracking)
        self.set_from(ev.position().y())

    def set_from(self, y):
        self.setValue(round(self.maximum() * (1 - y / self.height())))  # setValue clamps to 0..100


class Combo(QComboBox):
    """Dropdown whose popup list is exactly as wide as the field."""

    def __init__(self):
        super().__init__()
        self.setItemDelegate(QStyledItemDelegate(self))  # lets the stylesheet style the items
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(6)
        popup = self.view().window()  # own top-level window: transparent, so only the list's rounded frame shows
        popup.setWindowFlags(popup.windowFlags() | Qt.WindowType.FramelessWindowHint
                             | Qt.WindowType.NoDropShadowWindowHint)
        popup.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

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
    """Video window: paints frames aspect-fit. Hover controls styled after Discord's stream viewer: full-width bottom
    gradient, LIVE badge + device left, round settings / mute / red stop centred, volume / info / fullscreen right."""

    def __init__(self, main):
        super().__init__()
        self.main, self.frame, self.image, self.frame_size = main, None, QImage(), QSize()
        self.mouse_at = QPointF(-1, -1)
        self.setWindowTitle(f"{APP} – Live")
        self.resize(1280, 720)
        self.setMinimumSize(800, 360)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # on activation the window takes focus (shortcuts), not a button
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.gpu = self.gpu_surface()  # created first, so the overlays below stack on top of it
        self.bar = QFrame(self, objectName="bar")
        self.grid = QGridLayout(self.bar)
        self.grid.setContentsMargins(16, 56, 16, 14)  # tall top margin: room for the gradient to fade in
        self.sides = left, mid, right = QHBoxLayout(), QHBoxLayout(), QHBoxLayout()
        for col, lay in enumerate(self.sides):
            lay.setSpacing(12 if col == 1 else 8)
            self.grid.addLayout(lay, 0, col, (Qt.AlignmentFlag.AlignLeft, Qt.AlignmentFlag.AlignCenter,
                                              Qt.AlignmentFlag.AlignRight)[col] | Qt.AlignmentFlag.AlignVCenter)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(2, 1)

        chip = QFrame(objectName="chip")  # Discord's name tag: monitor icon + source name
        c = QHBoxLayout(chip)
        c.setContentsMargins(8, 4, 10, 4)
        c.setSpacing(6)
        screen = QLabel()
        screen.setPixmap(icon("screen", DC_TEXT).pixmap(16, 16))
        self.title = QLabel()
        c.addWidget(screen)
        c.addWidget(self.title)
        left.addWidget(chip)

        group = QFrame(objectName="group")  # Discord groups the call actions in one framed pill
        g = QHBoxLayout(group)
        g.setContentsMargins(4, 4, 4, 4)  # same inset on all sides: the hover highlight sits evenly in the frame
        g.setSpacing(4)
        self.gear = QToolButton(icon=icon("settings", "#fff"), iconSize=QSize(22, 22))
        self.gear.setFixedSize(48, 40)
        self.gear.clicked.connect(main.toggle_settings)
        g.addWidget(self.gear)
        self.stop_btn = QToolButton(icon=icon("stop", "#fff"), iconSize=QSize(22, 22), objectName="stop")
        self.stop_btn.setFixedSize(60, 50)  # as tall as the framed group next to it
        self.stop_btn.clicked.connect(main.stop)
        mid.addWidget(group)
        mid.addWidget(self.stop_btn)

        # Discord: a speaker icon next to fullscreen; hovering it opens a vertical volume slider above, click mutes
        self.mute = QToolButton(iconSize=QSize(24, 24))
        self.mute.setFixedSize(44, 44)  # square: even padding around the icon on hover
        self.mute.clicked.connect(main.toggle_mute)
        self.volpop = QFrame(self, objectName="volpop")
        pop = QVBoxLayout(self.volpop)
        pop.setContentsMargins(2, 2, 2, 2)  # Discord's slim 2px frame
        self.vol = VolumeBar()
        self.vol.setFixedSize(6, 76)
        self.vol.valueChanged.connect(main.vol.setValue)
        pop.addWidget(self.vol, 0, Qt.AlignmentFlag.AlignHCenter)
        self.volpop.hide()
        self.pop_hider = QTimer(self, singleShot=True, interval=600)
        self.pop_hider.timeout.connect(self.volpop.hide)
        self.info = QFrame(self, objectName="pill")  # Discord's "720p 30 FPS | LIVE" badge, top right, on hover
        p = QHBoxLayout(self.info)
        p.setContentsMargins(0, 0, 0, 0)
        p.setSpacing(0)
        self.quality = QLabel(objectName="quality")
        p.addWidget(self.quality)
        p.addWidget(QLabel("LIVE", objectName="live"))
        self.info.hide()
        self.full = QToolButton(icon=icon("fullscreen", DC_ICON, 2.2), iconSize=QSize(24, 24))
        self.full.setFixedSize(44, 44)
        self.full.clicked.connect(self.toggle_fullscreen)
        for w in (self.mute, self.full):
            right.addWidget(w)
        for w in (self.gear, self.stop_btn, self.mute, self.vol, self.full):
            w.setFocusPolicy(Qt.FocusPolicy.TabFocus)  # reachable by keyboard, no focus ring after a click
            w.installEventFilter(self)
        self.bar.hide()
        self.bar.installEventFilter(self)
        self.volpop.installEventFilter(self)
        self.fade = QGraphicsOpacityEffect(self.bar, opacity=0)
        self.bar.setGraphicsEffect(self.fade)
        self.info_fade = QGraphicsOpacityEffect(self.info, opacity=0)  # the badge fades together with the bar
        self.info.setGraphicsEffect(self.info_fade)
        self.fader = QPropertyAnimation(self.fade, b"opacity", self)
        self.fader.valueChanged.connect(lambda v: v is not None and self.info_fade.setOpacity(v))  # None on restart
        self.fader.finished.connect(self.faded)
        self.hider = QTimer(self, singleShot=True, interval=1500)
        self.hider.timeout.connect(lambda: self.fade_to(0, 250))
        if geo := main.st.value("geo_live"):  # last size + position, opened windowed
            self.restoreGeometry(geo)
            self.setWindowState(Qt.WindowState.WindowNoState)
        dark_titlebar(self)

    def gpu_surface(self):
        """QML VideoOutput in a QQuickWidget: YUV -> RGB and scaling on the GPU (Qt RHI) instead of toImage() +
        drawImage on the GUI thread (~1 CPU core at 1080p). Not a native window, so the overlays still composite on
        top. Returns its video sink, or None to fall back to CPU painting (no usable GPU, e.g. some RDP sessions)."""
        view = QQuickWidget(self)
        view.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)  # mouse stays with Live (bar, cursor)
        view.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # and so do the keys (shortcuts)
        view.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        view.setClearColor(Qt.GlobalColor.black)
        view.setSource(QUrl.fromLocalFile(str(ASSETS / "live.qml")))
        sink = view.rootObject().findChild(QVideoSink) if view.status() == QQuickWidget.Status.Ready else None
        if sink is None:
            print("captureMax: GPU video surface unavailable, using CPU rendering:",
                  *(e.toString() for e in view.errors()), file=sys.stderr)
            view.deleteLater()
            return None
        self.view = view
        return sink

    def show_frame(self, frame):
        self.frame_size = frame.size()
        if self.gpu:
            self.gpu.setVideoFrame(frame)  # the scene graph renders it at the next vsync
            self.main.shown += 1
        else:
            self.frame = frame
            self.update()

    def clear(self):
        self.frame, self.image, self.frame_size = None, QImage(), QSize()
        if self.gpu:
            self.gpu.setVideoFrame(QVideoFrame())

    def paintEvent(self, _):  # CPU fallback only; with the GPU surface it just paints black once under it
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
        side = max(self.sides[0].sizeHint().width(), self.sides[2].sizeHint().width())
        for col in (0, 2):  # equal side columns keep the round buttons exactly centred
            self.grid.setColumnMinimumWidth(col, side)
        height = self.bar.sizeHint().height()
        self.bar.setGeometry(0, self.height() - height, self.width(), height)
        self.unsetCursor()
        self.bar.show()
        if self.info.isHidden():
            self.info.show()
            self.info.raise_()
        if self.fader.endValue() != 1:  # hidden or fading out
            self.fade_to(1, 150)
        self.hider.start()

    def fade_to(self, opacity, ms):
        self.fade.setEnabled(True)
        self.info_fade.setEnabled(True)
        self.fader.stop()
        self.fader.setDuration(ms)
        self.fader.setEndValue(opacity)
        self.fader.start()

    def faded(self):
        """Effect off once fully visible: it re-renders the bar offscreen on every video frame otherwise."""
        if self.fade.opacity() == 0:
            self.bar.hide()
            self.info.hide()
            self.volpop.hide()
            if self.isFullScreen():  # like Discord: an idle mouse disappears in fullscreen
                self.setCursor(Qt.CursorShape.BlankCursor)
        for effect in (self.fade, self.info_fade):
            effect.setEnabled(self.fade.opacity() < 1)

    def mouseMoveEvent(self, ev):
        """Only real movement: Qt also sends synthetic moves when overlays show / restack, which would loop."""
        if ev.position() != self.mouse_at:
            self.mouse_at = ev.position()
            self.reveal()

    def enterEvent(self, _):
        self.reveal()

    def set_info(self, text):
        """Quality + LIVE badge, top right, like Discord's "720p 30 FPS | LIVE"."""
        self.quality.setText(text)
        self.info.adjustSize()
        self.info.move(self.width() - self.info.width() - 16, 16)

    def resizeEvent(self, _):
        if self.gpu:
            self.view.setGeometry(self.rect())
        self.set_info(self.quality.text())
        if self.bar.isVisible():
            self.reveal()

    def show_volume(self):
        """Vertical volume slider above the speaker, standing on the black strip like Discord's."""
        self.pop_hider.stop()
        self.volpop.adjustSize()
        top = self.mute.mapTo(self, QPoint(self.mute.width() // 2, 0))
        self.volpop.move(top.x() - self.volpop.width() // 2, top.y() - self.volpop.height() - 6)
        self.volpop.show()
        self.volpop.raise_()

    def eventFilter(self, obj, ev):
        kind = ev.type()
        if kind == QEvent.Type.FocusIn and ev.reason() not in (Qt.FocusReason.TabFocusReason,
                                                               Qt.FocusReason.BacktabFocusReason):
            self.setFocus()  # the focus ring is for keyboard navigation only, never left behind by the mouse
        elif kind in (QEvent.Type.Enter, QEvent.Type.Leave):
            entering = kind == QEvent.Type.Enter
            if obj in (self.bar, self.volpop):  # keep the bar up while the cursor is on it
                self.hider.stop() if entering else self.hider.start()
            if obj in (self.mute, self.volpop):  # speaker <-> slider popup, with a short grace period between
                self.show_volume() if entering else self.pop_hider.start()
        return False

    def toggle_fullscreen(self):
        """Fullscreen has no title bar / frame, so a Discord window share shows only the picture."""
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def changeEvent(self, ev):
        if ev.type() == QEvent.Type.WindowStateChange:
            self.full.setIcon(icon("windowed" if self.isFullScreen() else "fullscreen", DC_ICON, 2.2))
            self.retranslate()

    def retranslate(self):
        """Tooltips + screen-reader names of the icon-only controls; language and state (muted, fullscreen) dependent."""
        t = self.main.t
        for w, key in ((self.gear, "tip_settings"), (self.stop_btn, "tip_stop"),
                       (self.mute, "tip_unmute" if self.main.muted else "tip_mute"),
                       (self.full, "tip_window" if self.isFullScreen() else "tip_full"), (self.vol, "tip_volume")):
            w.setToolTip("" if w is self.mute else t(key))  # the speaker opens the volume popup instead
            w.setAccessibleName(t(key))

    def mouseDoubleClickEvent(self, _):
        self.toggle_fullscreen()

    def keyPressEvent(self, ev):
        """Player conventions (YouTube / Discord): F / F11 fullscreen, M mute, arrows volume. Esc only leaves
        fullscreen; stopping the stream is never on a reflex key."""
        key = ev.key()
        if key in (Qt.Key.Key_F, Qt.Key.Key_F11):
            self.toggle_fullscreen()
        elif key == Qt.Key.Key_Escape and self.isFullScreen():
            self.showNormal()
        elif key == Qt.Key.Key_M:
            self.main.toggle_mute()
            self.reveal()
        elif key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            self.main.vol.setValue(self.main.vol.value() + (5 if key == Qt.Key.Key_Up else -5))
            self.reveal()
            self.show_volume()  # show the slider moving
            self.pop_hider.start()
        else:
            super().keyPressEvent(ev)

    def showEvent(self, _):
        self.setFocus()  # Qt restores this on activation; otherwise it focuses (and rings) the first bar button

    def hideEvent(self, _):
        self.main.st.setValue("geo_live", self.saveGeometry())

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
        self.session = self.camera = self.mic = self.speaker = None
        self.muted = False  # hover bar / M key, live only; "Enable output" in settings applies on Save
        self.frames, self.shown, self.last_frame, self.t0 = deque(), 0, 0.0, 0.0
        self.status_key, self.status_args, self.status_kind = "ready", (), "idle"
        self.exp_dev = None  # device the exposure controls were last set up for
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
        h.addWidget(label(f'capture<span style="color:{ACCENT}; font-weight:700">MAX</span>', "logo"))
        h.addStretch()
        h.addWidget(self.tr_(label(), "subtitle"))
        self.lang_box = Combo()
        self.lang_box.setObjectName("lang")
        self.lang_box.setIconSize(QSize(24, 16))
        self.lang_box.setMinimumContentsLength(8)
        for code, name in LANGS.items():
            self.lang_box.addItem(flag(code), name)
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
        self.listen = self.tr_(Toggle(self.st.value("listen", True, type=bool)), "listen")
        card.addWidget(self.listen)
        card.addSpacing(6)
        self.aout = self.field(card, "output")
        self.vol_lbl, self.vol = self.slider(card, 0, 100, int(self.st.value("volume", 100)))
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
        self.btn.clicked.connect(self.start)
        root.addWidget(self.btn)
        foot = QHBoxLayout()
        foot.setSpacing(10)
        self.status = QLabel(objectName="status")
        foot.addWidget(self.status, 1)
        self.upd = QPushButton(objectName="update", cursor=Qt.CursorShape.PointingHandCursor)
        self.upd.clicked.connect(self.open_download)
        self.upd.hide()
        foot.addWidget(self.upd)
        foot.addWidget(label(VERSION if VERSION == "dev" else f"v{VERSION}"))
        root.addLayout(foot)
        self.latest = None

        self.live = Live(self)
        self.video.currentIndexChanged.connect(self.fill_res)
        self.video.currentIndexChanged.connect(self.match_audio)
        self.video.currentIndexChanged.connect(self.match_exposure)
        self.res.currentIndexChanged.connect(self.fill_fps)
        for sig in (self.video.currentIndexChanged, self.res.currentIndexChanged, self.fps.currentIndexChanged,
                    self.ain.currentIndexChanged, self.aout.currentIndexChanged, self.buf.valueChanged,
                    self.exp.valueChanged, self.auto_exp.toggled, self.listen.toggled):  # last: after the cascades
            sig.connect(self.update_save)
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
        if not self.st.contains("audio_in"):  # first run: pair audio with the video device
            self.match_audio()
        self.set_lang(self.lang)
        self.ticker = QTimer(self, interval=1000)
        self.ticker.timeout.connect(self.tick)
        self.ticker.start()
        if geo := self.st.value("geo_main"):  # position of the last session (Qt keeps it on a connected screen)
            self.restoreGeometry(geo)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # the window holds focus at start, not the first dropdown
        for kind in (QComboBox, QSlider, QPushButton):
            for w in self.findChildren(kind):
                w.setFocusPolicy(Qt.FocusPolicy.TabFocus)  # focus ring only via keyboard; clicks work without focus
        dark_titlebar(self)
        self.net = QNetworkAccessManager(self)
        if VERSION != "dev":
            self.check_update()

    # ---- building blocks
    def tr_(self, widget, key):
        self.texts.append((widget, key))
        return widget

    def t(self, key, *args):
        return TR[self.lang][key].format(*args)

    def card(self, cols, title):
        frame = QFrame(objectName="card")
        frame.setMinimumWidth(350)
        cols.addWidget(frame, 1)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(6)
        lay.addWidget(self.tr_(label(role="title"), title))
        lay.addSpacing(8)
        return lay

    def field(self, lay, key):
        box = QVBoxLayout()
        box.setSpacing(6)
        lbl = self.tr_(label(role="label"), key)
        box.addWidget(lbl)
        combo = Combo()
        box.addWidget(combo)
        box.addSpacing(6)
        lay.addLayout(box)
        return combo

    def slider(self, lay, lo, hi, value, step=1):
        lbl = label(role="label")  # Discord: white heading above the slider ("Lautsprecherlautstärke")
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
        self.btn.setText(self.t("save" if self.camera else "start"))
        self.refresh()  # the "Off" audio entry is translated too
        self.update_labels()
        self.apply_audio()
        self.set_status(self.status_key, *self.status_args, kind=self.status_kind)
        if self.latest:
            self.upd.setText(self.t("update", self.latest))

    def update_labels(self):
        b = self.buf.value()
        self.buf_lbl.setText(self.t("delay", b) + (self.t("low_latency") if b == 0 else ""))
        manual_ok = self.auto_exp.isEnabled()
        self.exp.setEnabled(manual_ok and not self.auto_exp.isChecked())
        self.exp_lbl.setEnabled(self.exp.isEnabled())
        self.exp_lbl.setText(self.t("exposure", 2 ** -self.exp.value()) if manual_ok else self.t("exp_na"))

    def set_status(self, key, *args, kind="idle"):
        if kind == "err" and key != self.status_key:  # settings are hidden while live, the status line is there
            self.show_settings()
        self.status_key, self.status_args, self.status_kind = key, args, kind
        self.status.setText(f"●  {self.t(key, *args)}")
        if self.status.property("kind") != kind:  # restyling is costly; the running status updates every second
            self.status.setProperty("kind", kind)
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
        self.match_exposure()
        self.update_save()

    def update_save(self):
        """While live, "Save" restarts the stream (black for a moment): only offer it when something changed."""
        self.btn.setEnabled(not self.camera or self.state() != self.saved)

    def match_exposure(self):
        """Exposure controls only for webcams: a capture card passes its source's picture through as is.
        A webcam starts on auto exposure; manual holds until the next device switch (not on refresh / language)."""
        name = self.video.currentText()
        webcam = sys.platform != "win32" or not name or windows_has_exposure(name)
        for w in (self.auto_exp, self.exp_lbl, self.exp):
            w.setVisible(webcam)
        if webcam and name != self.exp_dev:
            self.auto_exp.setChecked(True)
        self.exp_dev = name

    def match_audio(self):
        """Capture cards / webcams show up as an audio input named after the camera ("Mikrofon (2- USB Capture)")."""
        name = self.video.currentText()
        i = next((i for i, d in enumerate(self.ains) if name and name in d.description()), None)
        if i is not None:
            self.ain.setCurrentIndex(i + 1)  # +1: "Off" comes first

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
    def start(self):
        """Start, or while running ("Save" from the hover bar's settings) restart with the new settings."""
        if not self.cams or not self.res.currentText() or not self.fps.currentText():
            return self.set_status("no_device", kind="err")
        self.stop()
        self.save()
        self.saved = self.state()
        dev = self.cams[self.video.currentIndex()]
        manual = not self.auto_exp.isHidden() and self.auto_exp.isEnabled() and not self.auto_exp.isChecked()
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
            self.start_audio(self.ains[self.ain.currentIndex() - 1], self.aouts[self.aout.currentIndex()])
        self.apply_audio()
        self.frames.clear()
        self.shown, self.t0 = 0, time.monotonic()
        self.last_frame = self.t0
        self.set_status("starting")
        self.camera.start()
        self.live.clear()
        self.live.set_info("…")
        self.live.title.setText(dev.description())
        self.live.show()
        self.live.raise_()
        self.hide()
        self.btn.setText(self.t("save"))
        self.update_save()

    def start_audio(self, dev_in, dev_out):
        """Own source -> sink pump instead of the capture session's audio path, which crackles. 48 kHz stereo when
        the device can; when the sink is full the excess is dropped, so audio latency can't creep up."""
        fmt = QAudioFormat()
        fmt.setSampleRate(48000)
        fmt.setChannelCount(2)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        if not dev_in.isFormatSupported(fmt):
            fmt = dev_in.preferredFormat()
        self.mic, self.speaker = QAudioSource(dev_in, fmt, self), QAudioSink(dev_out, fmt, self)
        self.speaker.setBufferSize(fmt.bytesForDuration(100_000))  # 100 ms: no dropouts, little latency
        out, inp = self.speaker.start(), self.mic.start()

        def pump():
            data, free = bytes(inp.readAll()), self.speaker.bytesFree()
            out.write(data[:free - free % fmt.bytesPerFrame()])
        inp.readyRead.connect(pump)

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
        if self.speaker:
            self.mic.stop()
            self.speaker.stop()
            self.mic.deleteLater()
            self.speaker.deleteLater()
            self.mic = self.speaker = None
        self.session.setCamera(None)
        self.session.deleteLater()
        self.session = self.camera = None  # unparented: freed right here, so a restart can reopen the device
        self.frames.clear()
        self.live.hide()
        self.btn.setText(self.t("start"))
        self.update_save()
        if self.status_kind != "err":
            self.set_status("ready")
        self.show_settings()

    def state(self):
        """What "Save" restarts with. Volume / mute apply live from the hover bar, so they don't count."""
        return (self.video.currentText(), self.res.currentText(), self.fps.currentText(), self.ain.currentIndex(),
                self.aout.currentText(), self.buf.value(), self.auto_exp.isChecked(), self.exp.value(),
                self.listen.isChecked())

    def restore(self, s):
        for combo, text in zip((self.video, self.res, self.fps), s):
            combo.setCurrentText(text)
        self.ain.setCurrentIndex(s[3])
        self.aout.setCurrentText(s[4])
        self.buf.setValue(s[5])
        self.auto_exp.setChecked(s[6])
        self.exp.setValue(s[7])
        self.listen.setChecked(s[8])

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
            size, fps = self.live.frame_size, self.shown / (now - self.t0)
            self.set_status("running", f"{size.width()}x{size.height()}", fps, kind="ok")
            self.live.set_info(f"{size.height()}p {fps:.0f} FPS")  # Discord's notation
        self.shown, self.t0 = 0, now

    def toggle_mute(self):
        self.muted = not self.muted
        self.apply_audio()

    def apply_audio(self):
        """Settings card and hover bar share the volume; the sink follows it, the hover mute and the saved
        "Enable output" (the settings toggle only greys out the output field until Save)."""
        vol = self.vol.value()
        self.aout.setEnabled(self.listen.isChecked())
        on = (self.saved[8] if self.camera else self.listen.isChecked()) and not self.muted
        self.vol_lbl.setText(self.t("volume", vol))
        self.live.vol.setValue(vol)
        level = "muted" if not on or vol == 0 else "volume_low" if vol < 50 else "volume"
        self.live.mute.setIcon(icon(level, DC_ICON))
        self.live.retranslate()
        if self.speaker:
            self.speaker.setVolume(vol / 100 if on else 0)

    # ---- updates
    def check_update(self):
        """Ask GitHub for the latest release, async. QtNetwork uses the OS's TLS + certificate store; a frozen Python's
        ssl module can't find CA certificates on macOS / some Linux distros."""
        req = QNetworkRequest(QUrl(f"https://api.github.com/repos/{REPO}/releases/latest"))
        req.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, f"{APP}/{VERSION}")  # GitHub requires one
        req.setTransferTimeout(5000)
        self.net.get(req).finished.connect(self.update_reply)

    def update_reply(self):
        """Silent on any failure (offline, rate-limited, odd tag): the update hint is a nicety, not a feature."""
        reply = self.sender()
        reply.deleteLater()
        if reply.error() != QNetworkReply.NetworkError.NoError:
            return
        try:
            latest = json.loads(bytes(reply.readAll()))["tag_name"].lstrip("v")
            newer = version_key(latest) > version_key(VERSION)
        except (ValueError, KeyError):
            return
        if newer:
            self.show_update(latest)

    def show_update(self, latest):
        self.latest = latest
        self.upd.setText(self.t("update", latest))
        self.upd.show()  # stays as a reminder after "No"
        if self.ask(self.t("update_ask", f"v{latest}", f"v{VERSION}")):
            self.open_download()

    def open_download(self):
        QDesktopServices.openUrl(QUrl(f"https://github.com/{REPO}/releases/latest"))

    def ask(self, text):
        """Modal yes / no over the window, buttons in the app's language (Qt's own would be English)."""
        box = QMessageBox(QMessageBox.Icon.Question, APP, text, parent=self)
        yes = QPushButton(self.t("yes"), box, objectName="primary")  # blurple like Discord's; named before styling
        box.addButton(yes, QMessageBox.ButtonRole.YesRole)
        box.setDefaultButton(box.addButton(self.t("no"), QMessageBox.ButtonRole.NoRole))
        box.exec()
        return box.clickedButton() is yes

    def showEvent(self, _):
        if self.focusWidget() is None:
            self.setFocus()  # else Qt focuses (and rings) the first control on activation

    def show_settings(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def hide_settings(self):
        """While live: unsaved changes need a confirm, then get reverted so the panel matches what's running."""
        if self.state() != self.saved:
            if not self.ask(self.t("discard")):
                return
            self.restore(self.saved)
        self.hide()

    def toggle_settings(self):
        self.hide_settings() if self.isVisible() and not self.isMinimized() else self.show_settings()

    def save(self):
        for key, value in (("video", self.video.currentText()), ("res", self.res.currentText()),
                           ("fps", self.fps.currentText()), ("audio_in", self.ain.currentText()),
                           ("audio_out", self.aout.currentText()), ("volume", self.vol.value()),
                           ("listen", self.listen.isChecked()), ("buf", self.buf.value()),
                           ("auto_exp", self.auto_exp.isChecked()), ("exp", self.exp.value())):
            self.st.setValue(key, value)

    def closeEvent(self, ev):
        if self.camera:  # live: settings is a panel over the stream, closing it keeps streaming
            ev.ignore()
            return self.hide_settings()
        self.save()
        self.st.setValue("geo_main", self.saveGeometry())
        self.stop()
        QApplication.quit()


def main():
    if sys.platform == "win32":  # own taskbar entry + icon instead of python's
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP)
    app = QApplication(sys.argv)
    app.setApplicationName(APP)
    app.setStyle(JumpStyle("Fusion"))
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
