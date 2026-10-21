<p align="center"><img src="assets/icon.png" width="96" alt="captureMax icon"></p>

<h1 align="center">captureMax</h1>

<p align="center">Low-latency live viewer for capture cards and webcams on Windows. No OBS, no VLC, one exe.</p>

![captureMax settings window](docs/screenshot.png)

## Features

- **Live video** from any DirectShow device (USB capture cards, webcams), up to 1080p.
- **Audio monitoring**: plays the capture card's audio input on any output (WASAPI). Volume and self-mute
  are live. Muting only affects what you hear, so other apps recording the device are not affected.
- **Hover controls**: move the mouse over the live window to show volume, mute and a settings button.
- **Low latency** by default, with an optional delay (0–2000 ms) to sync video and audio.
- **Webcam tuning**: manual exposure for higher frame rates in low light.
- Follows Windows dark mode (dark title bars) and remembers all settings in `settings.json` next to the exe.

## Requirements

- Windows 10 or 11
- To run from source: Python 3.12

## Usage

1. Download `captureMax.exe` from the [latest release](../../releases/latest) and start it.
2. **VIDEO**: pick the device, resolution and FPS. Keep **MJPG** on for USB devices.
3. **AUDIO**: pick the input (usually the capture card) and your speakers/headset.
4. Click **Start**. Close the live window or press `Esc` to stop.

The status bar shows the real resolution and frame rate the device delivers.

## Run from source

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python capturemax.py
```

## Build the exe locally

```powershell
pip install pyinstaller==6.22.3
pyinstaller --onefile --windowed --name captureMax --icon assets/icon.ico --add-data "assets;assets" capturemax.py
```

The result is `dist/captureMax.exe`.

## Releasing

Releases are built by GitHub Actions ([`.github/workflows/release.yml`](.github/workflows/release.yml)).
Pushing a version tag builds the exe and publishes a GitHub release with generated notes:

```powershell
git tag v0.0.2
git push origin v0.0.2
```

Versions follow [semantic versioning](https://semver.org) (`vMAJOR.MINOR.PATCH`).

## Troubleshooting

| Problem | Fix |
|---|---|
| Very low FPS (1–10) on a USB device | Turn **MJPG** on. Without it, USB 2 can only carry about 5 fps of raw 1080p video. |
| Webcam stays around 20 fps | Turn **Auto-Belichtung** off and lower **Belichtung** (for example -6). The picture gets darker, but the frame rate goes up. |
| "Video-Device nicht zu öffnen" | Another app (OBS, Teams, Discord) is using the device. Close it, or use that app's virtual camera. |
| New device is missing from the list | Click the refresh button next to the status bar. |
| Audio and video out of sync | Raise **Verzögerung** until they match. |

## License

[MIT](LICENSE)
