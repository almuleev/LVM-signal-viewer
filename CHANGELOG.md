# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project follows Semantic Versioning.

## [Unreleased]

- No changes yet.

## [0.8.6] - 2026-05-04

### Added

- Local prepared-data cache (`.lvmcache.npz`) stored next to source LVM files.
- Channel visibility panel with first-channel-only default activation.
- Probe tool for single-point value inspection on visible data.
- Time/Frequency axis mode switch (`X: Time` / `X: Hz`) with FFT-based spectrum view.
- Animation toggle (`Anim: On/Off`) for lower CPU usage on weak machines.
- Position and window inputs (`Position (%)`, `Window (%)`) with Enter-to-apply behavior.
- Loading/status messages in UI for file load and processing stages.
- Public release documentation (`README.md`, `LICENSE`, `CONTRIBUTING.md`).
- GitHub collaboration templates for issues and pull requests.
- Repository `.gitignore` for Python, build outputs, and OS/editor artifacts.

### Fixed

- Timeline movement dead zones during certain zoom states.
- Edge anchoring bug where zooming after selecting timeline 0%/100% moved window away from boundary.
- Plot overdraw artifacts caused by non-monotonic time sections.
- Duplicate time-column channels incorrectly displayed as signal channels.
- Global hotkeys firing while typing into input boxes.
- File reload flow now correctly uses in-scope render callbacks.
- `Ctrl+O` / `Cmd+O` shortcut handling now uses Matplotlib key strings.
- Canceling file selection during reload no longer exits the whole app.

### Changed

- Controls/help text now rendered in multiple lines to avoid overlap in smaller windows.
- UI labels updated for clearer navigation semantics (`Timeline`, `Detail`, `Position (%)`, `Window (%)`).
- Rendering path optimized to reduce per-frame UI updates and repeated expensive operations.
- Repository cleaned from generated build/distribution artifacts and archive metadata.
- Source files moved to repository root for standard open-source layout.
- Viewer source (`lvm_viewer.py`) translated to English for comments, labels, and runtime messages.

## [0.1.0] - 2026-05-03

### Added

- Initial public version of the interactive LVM time-series viewer.
- Multi-channel plotting with playback, scrubbing, and zoom controls.
