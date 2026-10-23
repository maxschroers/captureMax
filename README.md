<p align="center"><img src="assets/icon.png" width="96" alt="captureMax icon"></p>

<h1 align="center">captureMax</h1>

<p align="center">Low-latency live viewer for capture cards and webcams on Windows, macOS and Linux. No OBS, no VLC, one app.</p>

![captureMax settings window](docs/screenshot.png)

![captureMax live view with Discord-style controls, volume bar and quality badge](docs/live.png)

## Features

- **Live video** from any capture card or webcam the OS knows. Resolution and FPS lists come from the device's
  real formats, and compressed formats (MJPG) are preferred automatically so USB devices reach full frame rate.
- **Audio monitoring**: plays the capture card's audio (48 kHz stereo) on any output. Volume and mute work live.
  The audio input follows the video device automatically.
- **Discord look**: modelled on Discord's current desktop client. The settings follow its voice & video
  settings page (dark panels, bordered dropdowns, thin blurple sliders with a round knob, blurple switches and
  buttons). Moving the mouse over the live window shows Discord's stream controls over a soft gradient: the
  device's name tag on the left, the framed settings button and the red stop button in the middle, speaker and
  fullscreen on the right, and the "1080p 60 FPS | LIVE" badge top right. Hovering the speaker raises Discord's
  slim, rounded volume bar (click or drag to set it), a click on the speaker mutes. Everything fades out when the
  mouse rests; in fullscreen the cursor hides too.
- **Fullscreen** with the button, `F`, `F11` or a double-click. No window frame, so a Discord window share shows
  only the picture.
- **GPU rendering**: colour conversion and scaling run on the graphics card (Qt Quick / RHI), which roughly halves
  the CPU load in fullscreen. Falls back to CPU drawing where no GPU is available.
- **Keyboard friendly**: visible focus on every control, `M` mute, `↑`/`↓` volume, screen-reader names for the icon
  buttons. Both windows reopen where you left them.
- **Settings while live**: the gear opens and closes the settings over the running stream. *Save* restarts with
  the new settings (it's only enabled once something changed); closing without saving asks before discarding.
- **Low latency** by default, with an optional video delay (0–2000 ms) to line up picture and sound.
- **Webcam tuning**: manual exposure for higher frame rates in low light (Windows and Linux). On Windows the
  exposure controls only appear for webcams; capture cards don't have any.
- **Update check**: on start the app looks for a newer release and offers to open the download page. Installed on
  Windows, it downloads the update and restarts into it instead. The current version is shown bottom right.
- **German and English UI**: follows the system language, switchable in the header.
- Dark title bars, remembers all settings.

## Download

Grab the build for your system from the [latest release](../../releases/latest):

| System | File | First start |
|---|---|---|
| Windows 10/11 | `captureMax-windows.exe` | Run it, it works portable. SmartScreen may warn about an unknown publisher: *More info → Run anyway*. Click **Install** (bottom right) to install it for your user, no admin needed: it goes to `%LOCALAPPDATA%\Programs\captureMax`, gets a Start menu entry, updates itself and can be removed under *Settings → Apps*. |
| macOS 12+ (Apple Silicon) | `captureMax-macos.dmg` | Open it, drag captureMax onto Applications, then **right-click → Open** once (the app is not notarized). Allow camera and microphone access. |
| Linux (x86-64, glibc 2.35+) | `captureMax-linux.tar.gz` | `tar -xzf captureMax-linux.tar.gz && ./captureMax`. Needs `libxcb-cursor0` and `libpulse0` (or PipeWire's Pulse layer). |

## Usage

1. **VIDEO**: pick the device, resolution and FPS.
2. **AUDIO**: pick the input (usually the capture card, or *Off*) and your speakers or headset.
3. Click **Start**. Stop with the red button or by closing the live window.

| Key | Action |
|---|---|
| `F` / `F11` / double-click | Fullscreen on / off |
| `Esc` | Leave fullscreen |
| `M` | Mute / unmute |
| `↑` / `↓` | Volume ± 5 % |

The status bar (and the info overlay) shows the real resolution and frame rate.

## Run from source

Python 3.12:

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.txt        # Windows: .venv\Scripts\pip ...
.venv/bin/python capturemax.py
.venv/bin/python -m unittest discover tests      # logic tests (CI runs them before every build)
```

## Build locally

```sh
pip install pyinstaller==6.22.3 pillow
pyinstaller --noconfirm captureMax.spec
```

The output goes to `dist/`: `captureMax.exe` on Windows, `captureMax.app` on macOS, `captureMax` on Linux.
PyInstaller can't cross-compile, so each system builds its own version.

## Releasing

[`.github/workflows/release.yml`](.github/workflows/release.yml) builds and smoke-tests all three systems on every
push and pull request. Pushing a version tag also publishes a GitHub release with the three downloads and generated
notes:

```sh
git tag v0.1.1
git push origin v0.1.1
```

The workflow writes the tag into `VERSION` in `capturemax.py` (source runs show `dev` and skip the update check).
Versions follow [semantic versioning](https://semver.org) (`vMAJOR.MINOR.PATCH`). `main` and `v*` tags are
protected by rulesets: changes from others come in as pull requests that need green builds.

## Contributing

Bug reports, ideas and pull requests are welcome, see [CONTRIBUTING.md](CONTRIBUTING.md). Questions go to
[Discussions](../../discussions), security issues to [SECURITY.md](SECURITY.md).

## Troubleshooting

| Problem | Fix |
|---|---|
| Webcam stays around 20 fps | Turn **Auto exposure** off and lower **Exposure** (for example 1/64 s). The picture gets darker, but the frame rate goes up. |
| "No picture from device" | Another app (OBS, Teams, Discord) is using the device. Close it, or use that app's virtual camera. |
| macOS shows a black picture | Allow camera access in *System Settings → Privacy & Security → Camera*. |
| Exposure control greyed out | macOS offers no exposure control for USB cameras. Some Linux cameras don't either. |
| Exposure controls missing (Windows) | The device reports no camera control, so it's treated as a capture card. Capture cards pass the source's picture through and have no exposure. |
| Audio and video out of sync | Raise **Delay** until they match. |
| High CPU load | Without a usable GPU (some remote-desktop sessions, missing graphics driver) the live view falls back to CPU drawing. Update the graphics driver. |

## License

[MIT](LICENSE)
