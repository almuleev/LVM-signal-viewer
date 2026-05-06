# LVM-signal-viewer

Simple desktop app to open, plot, and inspect LabVIEW .lvm measurement files without writing scripts.

## Motivation

Large LVM exports are often hard to inspect quickly in spreadsheets. This tool is focused on practical day-to-day analysis: open a file, navigate signals, switch between time and frequency views, and probe exact values from visible traces.

## Features

- Open `.lvm` and `.txt` files from a file dialog.
- Parse numeric sections from multi-header LVM exports.
- Auto-drop pseudo-channels that duplicate the time axis.
- Monotonic time reconstruction for sectioned (`Multi_Headings`) files.
- Interactive channel visibility panel (default: first channel enabled).
- Pre-processing time-range selection (`From` / `To`) before rendering.
- Timeline navigation with `Timeline` slider, `Position (%)` and `Window (%)` inputs, and playback controls (`Play`, `Pause`, `Back`, `Forward`).
- Optional animation on/off toggle for performance (`Anim: On/Off`).
- Performance profiles (`Fast`, `Balanced`, `Quality`) for weaker/stronger machines.
- Dual X-axis mode: `X: Time` (seconds) and `X: Hz` (FFT spectrum for current visible window).
- Point probe tool (`Probe`) to click and read exact values.
- Local app cache (`.lvmcache.npz`) in the OS cache directory for faster reopen.

## Installation

### Requirements

- Python 3.10+
- Desktop environment with GUI support (Tkinter + Matplotlib backend)

### Setup

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Run:

```bash
python lvm_viewer.py
```

Select an input file in the dialog. The viewer opens paused by default.

Keyboard shortcuts:

- `Space`: play/pause
- `Left` / `Right`: step back/forward
- `Home` / `End`: jump to start/end
- `Up` / `Down`: change detail
- `A`: animation on/off
- `M`: switch `Time/Hz` mode
- `V`: probe on/off
- `Esc`: clear probe marker
- `Ctrl+O` / `Cmd+O`: open another file

## Limitations

- Desktop GUI tool only (no CLI batch mode).
- Expects tab-separated numeric data with time in first numeric column.
- Very large files still require noticeable first parse time before cache exists.
- FFT view is window-based and intended for quick inspection, not full spectral diagnostics.
- No automated test suite yet.

## Possible Future Improvements

- Optional CLI file path input (`python lvm_viewer.py <file>`).
- Export visible range/channels to CSV.
- Optional presets for FFT windowing/averaging.
- Automated parser and UI smoke tests.

## License

MIT License. See [LICENSE](LICENSE).

## Maintenance Notice

This project is provided as an open-source tool. Issues, suggestions, and pull requests are welcome, but active maintenance and feature development are not guaranteed.
