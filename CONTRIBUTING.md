# Contributing

Thanks for your interest in improving this project.

## Before You Start

- Read [README.md](README.md) for project scope and limitations.
- For significant feature ideas, open an issue first to discuss direction and fit.

## Local Setup

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

Run:

```bash
python lvm_viewer.py
```

Optional startup file:

```bash
python lvm_viewer.py path\to\file.lvm
```

## Validation Before PR

Run:

```bash
python -m compileall .
```

If tests are available in your environment:

```bash
pytest
```

## Pull Requests

- Keep changes focused and small.
- Update docs when behavior changes.
- Do not claim support for data formats that are not implemented.
- Include a short validation note in your PR description (what you tested).
- Do not commit generated build outputs (`build/`, `dist/`, `__pycache__/`).

## Reporting Bugs

Please include:

- OS and Python version
- Steps to reproduce
- Expected behavior
- Actual behavior
- Sample input details (without sensitive data)

## Code Style

- Prefer readable, straightforward Python.
- Avoid adding heavy dependencies unless clearly necessary.
- Keep user-facing naming consistent: `LVM Signal Viewer`.
