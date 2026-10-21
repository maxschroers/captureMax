"""captureMax: capture-card / webcam live viewer. DirectShow video (OpenCV) + WASAPI audio monitor, no external programs."""
import ctypes
import json
import sys
import threading
import time
import tkinter as tk
import tkinter.font
from collections import deque
from ctypes import wintypes
from pathlib import Path

import customtkinter as ctk
import cv2
import darkdetect
import numpy as np
import sounddevice as sd
from pygrabber.dshow_graph import FilterGraph

APP, LIVE = "captureMax", "captureMax - Live"
HERE = Path(sys.executable if getattr(sys, "frozen", False) else __file__).parent
ICON = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "assets" / "icon.ico"
SETTINGS = HERE / "settings.json"
RESOLUTIONS = ["1920x1080", "1280x720", "1024x576", "960x540", "854x480", "640x480", "640x360"]
FPS = ["120", "60", "50", "30", "25", "24", "15"]
ACCENT, ACCENT_HOVER = "#4a80f5", "#3a64c4"
BG, SURFACE, FIELD, BORDER = "#0e1a33", "#15254a", "#0e1a33", "#27407a"
TEXT, MUTED = "#f2f5fc", "#8c9bc0"
DANGER, DANGER_HOVER = "#e5484d", "#c43c40"
KEY = "#010203"  # transparent color key for rounded floating windows
VOLUME, MUTE, GEAR, CHEVRON, REFRESH = "", "", "", "", ""  # Segoe icon font glyphs

user32, dwmapi = ctypes.windll.user32, ctypes.windll.dwmapi
user32.FindWindowW.restype = user32.GetAncestor.restype = user32.WindowFromPoint.restype = wintypes.HWND
user32.WindowFromPoint.argtypes = [wintypes.POINT]
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.LoadImageW.restype = wintypes.HANDLE
user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT, ctypes.c_int, ctypes.c_int,
                              wintypes.UINT]
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]


def wasapi_devices():
    """(inputs, outputs) as {name: index}, WASAPI only (full names, shared-mode resampling)."""
    api = next(i for i, a in enumerate(sd.query_hostapis()) if a["name"] == "Windows WASAPI")
    devs = [(i, d) for i, d in enumerate(sd.query_devices()) if d["hostapi"] == api]
    return ({d["name"]: i for i, d in devs if d["max_input_channels"]},
            {d["name"]: i for i, d in devs if d["max_output_channels"]})


def glyphs(size):
    """Windows' own icon font (Fluent on 11, MDL2 on 10); Tk can't render emoji outside the BMP reliably."""
    return ("Segoe Fluent Icons" if "Segoe Fluent Icons" in tkinter.font.families() else "Segoe MDL2 Assets", size)


def style_window(hwnd):
    """HighGUI window chrome: app icon + dark title bar when Windows uses dark mode."""
    if darkdetect.isDark():
        dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(1)), 4)  # DWMWA_USE_IMMERSIVE_DARK_MODE
    for which, metric in ((1, 11), (0, 49)):  # ICON_BIG/SM_CXICON, ICON_SMALL/SM_CXSMICON
        size = user32.GetSystemMetrics(metric)
        icon = user32.LoadImageW(None, str(ICON), 1, size, size, 0x10)  # IMAGE_ICON, LR_LOADFROMFILE
        user32.SendMessageW(hwnd, 0x80, which, icon)  # WM_SETICON


class Player(threading.Thread):
    """Video loop + audio pass-through. `msg` carries status/errors to the GUI, `gain` is live volume (0 = mute)."""

    def __init__(self, cfg, gain):
        super().__init__(daemon=True)
        self.cfg, self.stop_ev, self.msg, self.gain, self.hwnd = cfg, threading.Event(), "starte...", gain, None

    def run(self):
        c = self.cfg
        cap = audio = None
        try:
            cap = cv2.VideoCapture(c["video_idx"], cv2.CAP_DSHOW)
            if not cap.isOpened():
                self.msg = "Fehler: Video-Device nicht zu öffnen (belegt?)"
                return
            w, h = map(int, c["res"].split("x"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
            cap.set(cv2.CAP_PROP_FPS, int(c["fps"]))
            if c["mjpg"]:  # must come after size/fps: DSHOW otherwise falls back to raw YUY2 (~1 fps over USB 2)
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            # webcams: auto exposure stretches frame time in low light. Driver remembers the mode, so always set it.
            cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75 if c["auto_exp"] else 0.25)
            if not c["auto_exp"]:
                cap.set(cv2.CAP_PROP_EXPOSURE, c["exp"])
            if c["audio_in"] is not None:
                audio = self.open_audio()
            delay = c["buf_ms"] / 1000
            frames, shown, t0 = deque(), 0, time.time()
            cv2.namedWindow(LIVE, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(LIVE, 1280, 720)
            self.hwnd = user32.FindWindowW(None, LIVE)
            style_window(self.hwnd)
            while not self.stop_ev.is_set():
                ok, frame = cap.read()
                if not ok:
                    self.msg = "Fehler: kein Bild vom Device"
                    return
                frames.append((time.time(), frame))
                if time.time() - frames[0][0] >= delay:
                    cv2.imshow(LIVE, frames.popleft()[1])
                    shown += 1
                if cv2.waitKey(1) == 27 or cv2.getWindowProperty(LIVE, cv2.WND_PROP_VISIBLE) < 1:
                    break
                if time.time() - t0 >= 1:
                    self.msg = (f"läuft · {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x"
                                f"{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))} · {shown / (time.time() - t0):.0f} fps")
                    shown, t0 = 0, time.time()
        except Exception as e:  # surface any device/driver error in the GUI
            self.msg = f"Fehler: {e}"
        finally:
            self.hwnd = None
            if audio:
                audio.close()
            if cap:
                cap.release()
            cv2.destroyAllWindows()
            self.stop_ev.set()

    def open_audio(self):
        c = self.cfg
        wasapi = sd.WasapiSettings(auto_convert=True)
        ch = min(2, int(sd.query_devices(c["audio_in"])["max_input_channels"]))
        s = sd.Stream(samplerate=48000, channels=ch, device=(c["audio_in"], c["audio_out"]), dtype="float32",
                      latency=max(c["buf_ms"], 20) / 1000, extra_settings=(wasapi, wasapi),
                      callback=lambda i, o, n, t, st: np.multiply(i, self.gain, out=o))
        s.start()
        return s


class Dropdown(ctk.CTkButton):
    """Field-styled picker whose list is exactly as wide as the field (CTkOptionMenu sizes its list to the text)."""

    def __init__(self, master, values, value):
        super().__init__(master, height=34, corner_radius=8, anchor="w", fg_color=FIELD, hover_color=BORDER,
                         text_color=TEXT, font=("Segoe UI", 13), command=self.open)
        chevron = ctk.CTkLabel(self, text=CHEVRON, width=16, height=16, fg_color="transparent", text_color=MUTED,
                               font=glyphs(11))
        chevron.place(relx=1, x=-12, rely=0.5, anchor="e")
        chevron.bind("<Button-1>", lambda e: self.open())
        self.values, self.value = list(values), ""
        self.set(value or (self.values[0] if self.values else ""))

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
        super().configure(text=value if len(value) <= 40 else value[:39] + "…")

    def configure(self, values=None, **kwargs):
        if values is not None:
            self.values = list(values)
        if kwargs:
            super().configure(**kwargs)

    def open(self):
        pop = tk.Toplevel(self, bg=BORDER)
        pop.overrideredirect(True)
        pop.attributes("-topmost", True)
        many = len(self.values) > 8
        box = (ctk.CTkScrollableFrame(pop, fg_color=FIELD, corner_radius=0, height=8 * 34) if many
               else ctk.CTkFrame(pop, fg_color=FIELD, corner_radius=0))
        box.pack(fill="both", expand=True, padx=1, pady=1)
        for v in self.values:
            ctk.CTkButton(box, text=v, anchor="w", height=32, corner_radius=6, text_color=TEXT,
                          fg_color=ACCENT if v == self.value else "transparent", hover_color=BORDER,
                          font=("Segoe UI", 13), command=lambda v=v: (self.set(v), pop.destroy())).pack(
                fill="x", padx=4, pady=1)
        pop.update_idletasks()
        pop.geometry(f"{self.winfo_width()}x{pop.winfo_reqheight()}"
                     f"+{self.winfo_rootx()}+{self.winfo_rooty() + self.winfo_height() + 4}")
        pop.bind("<FocusOut>", lambda e: e.widget is pop and pop.destroy())
        pop.bind("<Escape>", lambda e: pop.destroy())
        pop.focus_force()


class Overlay(tk.Toplevel):
    """Hover controls floating over the live window: mute, volume, settings. Real widgets, zero per-frame cost."""

    def __init__(self, app):
        super().__init__(app, bg=KEY)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-transparentcolor", KEY)
        self.attributes("-alpha", 0.94)
        self.withdraw()
        self.hide_at = 0
        bar = ctk.CTkFrame(self, corner_radius=14, fg_color=SURFACE, bg_color=KEY, border_width=1,
                           border_color=BORDER)
        bar.pack()
        icon_btn = dict(width=40, height=36, corner_radius=10, fg_color=FIELD, hover_color=BORDER,
                        text_color=TEXT, font=glyphs(15))
        self.mute = ctk.CTkButton(bar, command=lambda: app.listen.set(not app.listen.get()), **icon_btn)
        self.mute.pack(side="left", padx=(12, 8), pady=10)
        ctk.CTkSlider(bar, width=200, from_=0, to=100, number_of_steps=100, variable=app.volume, fg_color=BORDER,
                      button_color=ACCENT, button_hover_color=ACCENT_HOVER, progress_color=ACCENT).pack(side="left")
        self.pct = ctk.CTkLabel(bar, width=48, text_color=MUTED, font=("Segoe UI", 12))
        self.pct.pack(side="left", padx=(6, 4))
        ctk.CTkButton(bar, text=GEAR, command=app.show_settings, **icon_btn).pack(side="left", padx=(4, 12))

    def track(self, hwnd):
        """Show while the cursor is over the live window (or this bar), hide 1.5 s after it leaves."""
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        under = user32.GetAncestor(user32.WindowFromPoint(pt), 2)  # GA_ROOT
        me = user32.GetAncestor(self.winfo_id(), 2)
        if hwnd and under in (hwnd, me):
            self.hide_at = time.time() + 1.5
        if hwnd and time.time() < self.hide_at:
            r, p = wintypes.RECT(), wintypes.POINT()
            user32.GetClientRect(hwnd, ctypes.byref(r))
            user32.ClientToScreen(hwnd, ctypes.byref(p))
            w, h = self.winfo_reqwidth(), self.winfo_reqheight()
            self.geometry(f"+{p.x + (r.right - w) // 2}+{p.y + r.bottom - h - 24}")
            if self.state() == "withdrawn":
                self.deiconify()
        elif self.state() != "withdrawn":
            self.withdraw()


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("system")  # title bar follows Windows; widget colors are set explicitly
        ctk.set_default_color_theme("dark-blue")
        self.title(APP)
        self.iconbitmap(str(ICON))
        self.configure(fg_color=BG)
        self.resizable(False, False)  # no geometry: window sizes itself to the content
        self.player, self.last_msg = None, None
        s = self.load()
        self.listen = ctk.BooleanVar(value=s.get("listen", True))
        self.volume = ctk.IntVar(value=s.get("volume", 100))
        self.mjpg = ctk.BooleanVar(value=s.get("mjpg", True))
        self.auto_exp = ctk.BooleanVar(value=s.get("auto_exp", True))

        head = ctk.CTkFrame(self, corner_radius=10, fg_color=SURFACE, bg_color=BG)
        head.pack(fill="x", padx=24, pady=(24, 4))
        ctk.CTkLabel(head, text="◉ capture", font=("Segoe UI", 16, "bold"), text_color=TEXT).pack(
            side="left", padx=(16, 0), pady=12)
        ctk.CTkLabel(head, text="MAX", font=("Segoe UI", 16, "bold"), text_color=ACCENT).pack(side="left", pady=12)
        ctk.CTkLabel(head, text="capture card & webcam viewer", font=("Segoe UI", 12), text_color=MUTED).pack(
            side="right", padx=16)

        self.cols = ctk.CTkFrame(self, fg_color="transparent")
        self.cols.pack(fill="both", expand=True, padx=16, pady=(4, 0))
        self.cols.grid_rowconfigure(0, weight=1)
        card = self.card("VIDEO", 0)
        self.video = self.field(card, "Gerät", s.get("video"))
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 10))
        self.res = self.field(row, "Auflösung", s.get("res"), RESOLUTIONS, side="left")
        self.fps = self.field(row, "FPS", s.get("fps"), FPS, side="left")
        self.switch(card, "MJPG (nötig für hohe FPS über USB)", self.mjpg)

        card = self.card("AUDIO", 1)
        self.audio_in = self.field(card, "Eingang", s.get("audio_in"))
        self.audio_out = self.field(card, "Ausgabe (Monitor)", s.get("audio_out"))
        self.vol_lbl, _ = self.slider(card, 0, 100, 100, None, None, variable=self.volume)
        self.switch(card, "Für mich hören (aus = stumm)", self.listen)

        card = self.card("ERWEITERT", 2)
        self.buf_lbl, self.buf = self.slider(card, 0, 2000, 40, s.get("buf", 0), self.on_buf)
        self.switch(card, "Auto-Belichtung (Webcam)", self.auto_exp, self.on_auto_exp)
        self.exp_lbl, self.exp = self.slider(card, -13, -1, 12, s.get("exp", -6), self.on_exp)
        self.on_buf(self.buf.get())
        self.on_exp(self.exp.get())
        self.on_auto_exp()

        self.btn = ctk.CTkButton(self, text="Start", height=48, corner_radius=12, bg_color=BG, font=("Segoe UI", 16, "bold"),
                                 fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self.toggle)
        self.btn.pack(fill="x", padx=24, pady=(8, 8))
        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(fill="x", padx=24, pady=(0, 20))
        self.status = ctk.CTkLabel(foot, text="bereit", text_color=MUTED, anchor="w", font=("Segoe UI", 12),
                                   fg_color=SURFACE, bg_color=BG, corner_radius=16, height=32)
        self.status.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(foot, text=REFRESH, width=32, height=32, corner_radius=8, bg_color=BG, fg_color=SURFACE,
                      hover_color=BORDER, text_color=MUTED, font=glyphs(13), command=self.refresh).pack(side="right")

        self.overlay = Overlay(self)
        self.listen.trace_add("write", self.on_audio)
        self.volume.trace_add("write", self.on_audio)
        self.on_audio()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh()
        self.after(100, self.poll)

    def card(self, title, col):
        self.cols.grid_columnconfigure(col, weight=1, uniform="c", minsize=330)
        f = ctk.CTkFrame(self.cols, corner_radius=10, fg_color=SURFACE, bg_color=BG)
        f.grid(row=0, column=col, sticky="nsew", padx=8, pady=8)
        ctk.CTkLabel(f, text=title, anchor="w", font=("Segoe UI", 14, "bold"), text_color=TEXT).pack(
            fill="x", padx=16, pady=(14, 0))
        return f

    def switch(self, parent, text, var, command=None):
        ctk.CTkSwitch(parent, text=text, variable=var, command=command, text_color=TEXT, font=("Segoe UI", 12),
                      fg_color=BORDER, progress_color=ACCENT, button_color=TEXT).pack(
            anchor="w", padx=16, pady=(4, 14))

    def slider(self, parent, lo, hi, steps, value, command, variable=None):
        lbl = ctk.CTkLabel(parent, anchor="w", font=("Segoe UI", 12), text_color=MUTED)
        lbl.pack(fill="x", padx=16, pady=(10, 0))
        sl = ctk.CTkSlider(parent, from_=lo, to=hi, number_of_steps=steps, fg_color=BORDER, variable=variable,
                           button_color=ACCENT, button_hover_color=ACCENT_HOVER,
                           progress_color=ACCENT, command=command)
        if variable is None:
            sl.set(value)
        sl.pack(fill="x", padx=16, pady=(6, 10))
        return lbl, sl

    def field(self, parent, label, value, values=(), side=None):
        box = ctk.CTkFrame(parent, fg_color="transparent")
        if side:
            box.pack(side=side, fill="x", expand=True, padx=(0, 8) if label != "FPS" else 0)
        else:
            box.pack(fill="x", padx=16, pady=(0, 10))
        ctk.CTkLabel(box, text=label, anchor="w", font=("Segoe UI", 12), text_color=MUTED).pack(
            fill="x", pady=(10, 2))
        m = Dropdown(box, values, value)
        m.pack(fill="x")
        return m

    def on_buf(self, v):
        v = int(v)
        self.buf_lbl.configure(text=f"Verzögerung: {v} ms" + ("  (Low-Latency)" if v == 0 else ""))

    def on_exp(self, v):
        self.exp_lbl.configure(text=f"Belichtung: {int(v)}  (kleiner = dunkler, mehr FPS)")

    def on_auto_exp(self):
        on = self.auto_exp.get()
        self.exp.configure(state="disabled" if on else "normal", button_color=BORDER if on else ACCENT,
                           progress_color=BORDER if on else ACCENT)
        self.exp_lbl.configure(text_color=BORDER if on else MUTED)

    def on_audio(self, *_):
        """Settings card and overlay share listen/volume; push the resulting gain to the running player."""
        vol, on = self.volume.get(), self.listen.get()
        self.vol_lbl.configure(text=f"Lautstärke: {vol} %")
        self.overlay.pct.configure(text=f"{vol} %" if on else "stumm")
        self.overlay.mute.configure(text=VOLUME if on else MUTE)
        if self.player:
            self.player.gain = vol / 100 if on else 0.0

    def show_settings(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def load(self):
        try:
            return json.loads(SETTINGS.read_text())
        except (OSError, ValueError):
            return {}

    def save(self):
        SETTINGS.write_text(json.dumps({
            "video": self.video.get(), "res": self.res.get(), "fps": self.fps.get(),
            "audio_in": self.audio_in.get(), "audio_out": self.audio_out.get(),
            "listen": self.listen.get(), "volume": self.volume.get(), "mjpg": self.mjpg.get(),
            "buf": int(self.buf.get()), "auto_exp": self.auto_exp.get(), "exp": int(self.exp.get())}))

    def refresh(self):
        self.vdevs = FilterGraph().get_input_devices()
        self.ains, self.aouts = wasapi_devices()
        for menu, names in ((self.video, self.vdevs), (self.audio_in, list(self.ains)),
                            (self.audio_out, list(self.aouts))):
            menu.configure(values=names)
            if menu.get() not in names and names:
                menu.set(names[0])

    def toggle(self):
        if self.player and self.player.is_alive():
            self.player.stop_ev.set()
            return
        self.save()
        self.player = Player({
            "video_idx": self.vdevs.index(self.video.get()), "res": self.res.get(), "fps": self.fps.get(),
            "mjpg": self.mjpg.get(), "buf_ms": int(self.buf.get()),
            "auto_exp": self.auto_exp.get(), "exp": int(self.exp.get()),
            "audio_in": self.ains.get(self.audio_in.get()), "audio_out": self.aouts.get(self.audio_out.get())},
            gain=self.volume.get() / 100 if self.listen.get() else 0.0)
        self.player.start()
        self.btn.configure(text="Stop", fg_color=DANGER, hover_color=DANGER_HOVER)

    def poll(self):
        alive = self.player and self.player.is_alive()
        self.overlay.track(self.player.hwnd if alive else None)
        if self.player and self.player.msg != self.last_msg:
            m = self.last_msg = self.player.msg
            self.status.configure(text=f"  ●  {m}", text_color="#f87171" if m.startswith("Fehler") else
                                  "#34d399" if m.startswith("läuft") else MUTED)
        if self.player and not alive and self.btn.cget("text") == "Stop":
            self.btn.configure(text="Start", fg_color=ACCENT, hover_color=ACCENT_HOVER)
        self.after(100, self.poll)

    def close(self):
        if self.player:
            self.player.stop_ev.set()
            self.player.join(2)
        self.destroy()


if __name__ == "__main__":
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP)  # taskbar shows our icon, not python's
    App().mainloop()
