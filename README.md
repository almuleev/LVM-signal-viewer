# LVM Signal Viewer

A lightweight desktop tool for opening and interactively reviewing LabVIEW Measurement (`.lvm`) time-series files.

## Motivation

Many LVM files are easiest to inspect visually before deeper analysis. This tool focuses on quick local exploration: open a file, view all channels, navigate the timeline, and inspect signal behavior without writing custom scripts each time.

## Features

- Open `.lvm` and `.txt` files through a file dialog.
- Parse numeric tab-separated time-series data after LVM headers.
- Collect data across repeated LVM sections (including `Multi_Headings` exports).
- Handle decimal commas by converting them to decimal points.
- Display all detected channels on one interactive plot.
- Playback controls: play/pause, step backward/forward, jump to start/end.
- Time scrub slider and zoom slider.
- Keyboard shortcuts for navigation and zoom.
- Open another file in the same session (`Ctrl+O` / `Cmd+O` or the Open button).

## Installation

### Requirements

- Python 3.10+ recommended
- Desktop environment with GUI support (Tkinter + Matplotlib backend)

### Setup

```bash
python -m venv .venv
```

On Windows:

```bash
.venv\Scripts\activate
```

On macOS/Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Run the viewer:

```bash
python lvm_viewer.py
```

At startup, a file picker opens. Choose an `.lvm` file and the interactive viewer starts.

Main controls:

- `Space`: play/pause
- `Left` / `Right`: step backward/forward
- `Home` / `End`: jump to start/end
- `Up` / `Down`: zoom in/out
- `Ctrl+O` / `Cmd+O`: open another file

## Limitations

- Desktop GUI tool only (no command-line batch processing).
- Expects tab-separated numeric data where the first numeric column is time.
- Parsing is heuristic-based for mixed/irregular LVM exports and may not cover every vendor-specific variant.
- Entire dataset is loaded into memory.
- No automated test suite is included yet.

## Possible Future Improvements

- Optional command-line file argument to bypass the file dialog.
- Optional channel selection and visibility toggles.
- Export selected ranges/channels to CSV.
- Basic automated tests for parser behavior.
- UI localization options.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).

## Maintenance Notice

This project is provided as an open-source tool. Issues, suggestions, and pull requests are welcome, but active maintenance and feature development are not guaranteed.
