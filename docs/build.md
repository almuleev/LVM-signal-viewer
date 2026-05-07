# Build Guide

This document explains how to run and package **LVM Signal Viewer**.

## Prerequisites

- Python 3.10+
- Desktop GUI environment (Tkinter available)
- `pip`

## Run from Source

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

Install dependencies and run:

```bash
pip install -r requirements.txt
python lvm_viewer.py
```

Optional startup file:

```bash
python lvm_viewer.py path\to\file.lvm
```

## Build Windows Executable (PyInstaller)

1. Activate virtual environment.
2. Install PyInstaller.
3. Build from spec.

```bash
pip install pyinstaller
pyinstaller --clean --noconfirm LVM_Viewer.spec
```

Build outputs:

- `dist/`
- `build/`

These folders are ignored by `.gitignore` and should not be committed.

## Quick Smoke Test for Build

After build, verify:

1. App opens in empty mode.
2. `Open file` works.
3. `.lvm` sample loads and renders.
4. Timeline/zoom controls respond.
5. `Save PNG` and `Save CSV` exports work.

## Troubleshooting

- If startup fails with missing modules, reinstall dependencies in a clean virtual environment.
- If parser fails, validate the file is `.lvm` or tab-separated `.txt` with numeric columns.
- If UI feels unresponsive on large files, switch performance profile to `Fast`.
