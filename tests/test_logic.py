"""Logic checks, Qt runs offscreen:  python -m unittest discover tests"""
import inspect
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QEvent, QPoint, QPointF, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import capturemax as c  # noqa: E402

app = QApplication.instance() or QApplication([])
TMP = tempfile.mkdtemp()
c.QSettings = lambda *_: QSettings(os.path.join(TMP, "settings.ini"), QSettings.Format.IniFormat)  # never the user's


class Logic(unittest.TestCase):
    def setUp(self):
        self.m = c.Main()

    def test_version_key_is_numeric(self):
        self.assertGreater(c.version_key("0.10.0"), c.version_key("0.9.9"))
        self.assertEqual(c.version_key("1.2.3"), (1, 2, 3))

    def test_asset_url_picks_windows_exe(self):
        release = {"assets": [{"name": "captureMax-macos.dmg", "browser_download_url": "m", "size": 1},
                              {"name": "captureMax-windows.exe", "browser_download_url": "w", "size": 2}]}
        self.assertEqual(c.asset_url(release), ("w", 2))
        self.assertIsNone(c.asset_url({"assets": release["assets"][:1]}))
        self.assertIsNone(c.asset_url({}))

    def test_source_run_is_not_installed(self):
        self.assertFalse(c.installed())
        self.assertFalse(self.m.inst.isVisibleTo(self.m))

    def test_combo_fill_keeps_selection(self):
        box = c.Combo()
        box.fill(["a", "b", "c"], "b")
        self.assertEqual(box.currentText(), "b")
        box.fill(["x", "y"], "b")  # gone: falls back to the first entry
        self.assertEqual(box.currentText(), "x")

    def test_combo_hover_cleared_when_mouse_leaves_list(self):
        def move(widget, local):  # no button held: Qt drops it unless the widget tracks the mouse
            app.sendEvent(widget, QMouseEvent(QEvent.Type.MouseMove, QPointF(local),
                                              QPointF(widget.mapToGlobal(local)), Qt.MouseButton.NoButton,
                                              Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier))

        box = c.Combo()
        box.fill(["a", "b", "c"], "a")
        box.show()
        box.showPopup()
        view, sel = box.view(), box.view().selectionModel()
        move(view.viewport(), view.visualRect(box.model().index(2, 0)).center())
        self.assertTrue(sel.isSelected(box.model().index(2, 0)))  # hovered
        popup = view.window()  # the open list has the mouse grab: a move off it goes to the popup window
        move(popup, QPoint(popup.width() + 50, popup.height() // 2))
        self.assertFalse(sel.hasSelection())
        box.hidePopup()

    def test_combo_wheel_scrolls_smoothly(self):
        box = c.Combo()
        box.fill([str(i) for i in range(30)], "0")
        box.show()
        box.showPopup()
        bar = box.view().verticalScrollBar()
        self.assertGreater(bar.maximum(), 100)
        for _ in range(2):  # two notches add up, even mid-glide
            app.sendEvent(box.view().viewport(), QWheelEvent(
                QPointF(10, 10), QPointF(10, 10), QPoint(), QPoint(0, -120), Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False))
        self.assertEqual(bar.value(), 0)  # not jumped: it glides
        self.assertEqual(box.scroller.endValue(), 96)
        box.scroller.setCurrentTime(box.scroller.duration())
        self.assertEqual(bar.value(), 96)
        box.hidePopup()

    def test_device_names_split_like_discord(self):
        self.assertEqual(c.split_device("Mikrofon (Razer BlackShark V2 Pro)"), ("Razer BlackShark V2 Pro", "Mikrofon"))
        self.assertEqual(c.split_device("Realtek Digital Output (Realtek(R) Audio)"),
                         ("Realtek(R) Audio", "Realtek Digital Output"))
        self.assertEqual(c.split_device("UGREEN 25854"), ("UGREEN 25854", ""))
        box = c.Combo("mic")
        box.fill(["Mikrofon (Razer)"], "")
        self.assertEqual(box.currentText(), "Mikrofon (Razer)")  # the full name is what gets saved and matched
        self.assertEqual(tuple(box.currentData()), ("Razer", "Mikrofon", "mic"))

    def test_delay_buffer_holds_then_drops_backlog(self):
        shown = []
        self.m.live.show_frame = shown.append
        self.m.buf.setValue(0)
        with mock.patch.object(c.time, "monotonic", return_value=0.0):
            self.m.on_frame("now")
        self.assertEqual(shown, ["now"])  # no delay: straight through

        shown.clear()
        self.m.frames.clear()
        self.m.buf.setValue(100)
        for t, frame in ((0.0, "a"), (0.05, "b"), (0.12, "c"), (0.30, "d")):
            with mock.patch.object(c.time, "monotonic", return_value=t):
                self.m.on_frame(frame)
        self.assertEqual(shown, ["a", "c"])  # a once 100 ms old; b dropped as backlog, c is the oldest due one

    def test_escape_windowed_keeps_the_stream(self):
        with mock.patch.object(self.m, "stop") as stop:
            app.sendEvent(self.m.live, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))
        stop.assert_not_called()

    def test_save_only_offered_when_settings_changed(self):
        self.m.camera, self.m.saved = object(), self.m.state()  # pretend live
        self.m.update_save()
        self.assertFalse(self.m.btn.isEnabled())
        self.m.buf.setValue(self.m.buf.value() + 50)
        self.assertTrue(self.m.btn.isEnabled())
        self.m.camera = None

    def test_start_asks_for_camera_access_first(self):
        """macOS: Qt refuses the camera until the user allowed it, and never asks by itself."""
        self.m.cams = [mock.Mock()]
        self.m.res.fill(["1920x1080"], "1920x1080")
        self.m.fps.fill(["60"], "60")
        Status = Qt.PermissionStatus
        with mock.patch.object(app, "checkPermission", return_value=Status.Undetermined), \
                mock.patch.object(app, "requestPermission") as ask:
            self.m.start()
        ask.assert_called_once()
        self.assertIsNone(self.m.camera)
        self.assertEqual(len(inspect.signature(ask.call_args.args[2]).parameters), 1)  # PySide refuses other functors
        with mock.patch.object(app, "checkPermission", return_value=Status.Undetermined), \
                mock.patch.object(self.m, "start") as again:
            ask.call_args.args[2](None)  # no prompt possible (source run): error, not another request
        again.assert_not_called()
        self.assertEqual(self.m.status_key, "cam_denied")
        self.m.status_key = None
        with mock.patch.object(app, "checkPermission", return_value=Status.Denied):
            self.m.start()
        self.assertIsNone(self.m.camera)
        self.assertEqual(self.m.status_key, "cam_denied")


if __name__ == "__main__":
    unittest.main()
