"""Logic checks, Qt runs offscreen:  python -m unittest discover tests"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QEvent, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
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


if __name__ == "__main__":
    unittest.main()
