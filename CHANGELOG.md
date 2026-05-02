# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project follows Semantic Versioning.

## [Unreleased]

### Added

- Public release documentation (`README.md`, `LICENSE`, `CONTRIBUTING.md`).
- GitHub collaboration templates for issues and pull requests.
- Repository `.gitignore` for Python, build outputs, and OS/editor artifacts.

### Fixed

- File reload flow now correctly uses in-scope render callbacks.
- `Ctrl+O` / `Cmd+O` shortcut handling now uses Matplotlib key strings.
- Canceling file selection during reload no longer exits the whole app.

### Changed

- Repository cleaned from generated build/distribution artifacts and archive metadata.
- Source files moved to repository root for standard open-source layout.
- Viewer source (`lvm_viewer.py`) translated to English for comments, labels, and runtime messages.

## [0.1.0] - 2026-05-03

### Added

- Initial public version of the interactive LVM time-series viewer.
- Multi-channel plotting with playback, scrubbing, and zoom controls.
