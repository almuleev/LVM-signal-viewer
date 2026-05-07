# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project follows Semantic Versioning.

## [Unreleased]

### Added

- Optional CLI startup file argument: `python lvm_viewer.py <path_to_lvm_or_txt>`.
- Export current plot as PNG (`Save PNG` button, `Ctrl+S`/`Cmd+S`).
- Export current visible data range as CSV (`Save CSV` button, `Ctrl+E`/`Cmd+E`).
- Basic parser tests and GitHub Actions test workflow.
- Added Russian README translation.
- New documentation set:
  - `docs/build.md`
  - `docs/github-topics.md`
  - `docs/release-checklist.md`
  - `docs/promotion.md`

### Changed

- Project README rewritten as a product-style page with download-first structure.
- Empty-mode startup screen improved with clearer actions and shortcuts.
- User-facing naming aligned to `LVM Signal Viewer` in window titles and docs.
- Default visualization mode set to `Time` for safer first-use behavior.

### Fixed

- Main control buttons could become unresponsive in some non-blocking backend flows (widget references are now retained explicitly).
- Startup/load flow now returns to empty mode on file/range errors instead of hard exit.
- Friendlier parser message when numeric data is not detected.

## [0.8.6] - 2026-05-04

### Added

- Local prepared-data cache (`.lvmcache.npz`) in the OS app cache directory, with legacy sidecar migration.
- Channel visibility panel with first-channel-only default activation.
- Probe tool for single-point value inspection on visible data.
- Time/Frequency axis mode switch (`X: Time` / `X: Hz`) with FFT-based spectrum view.
- Animation toggle (`Anim: On/Off`) for lower CPU usage on weak machines.
- Performance profiles (`Fast`, `Balanced`, `Quality`) for CPU-friendly rendering.
- Position and window inputs (`Position (%)`, `Window (%)`) with Enter-to-apply behavior.
- Pre-processing time-range selection dialog (`From` / `To`) before visualization.
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
- Endless loading after range selection in file-open flow.
- Window percentage mismatch after mode/zoom switches.
- File reload flow now correctly uses in-scope render callbacks.
- `Ctrl+O` / `Cmd+O` shortcut handling now uses Matplotlib key strings.
- Canceling file selection during reload no longer exits the whole app.

### Changed

- Controls/help text now rendered in multiple lines to avoid overlap in smaller windows.
- UI labels updated for clearer navigation semantics (`Timeline`, `Detail`, `Position (%)`, `Window (%)`).
- Rendering path optimized to reduce per-frame UI updates and repeated expensive operations.
- Controls/help text split into multiple lines for consistent fit.
- Repository cleaned from generated build/distribution artifacts and archive metadata.
- Source files moved to repository root for standard open-source layout.
- Viewer source (`lvm_viewer.py`) translated to English for comments, labels, and runtime messages.

## [0.1.0] - 2026-05-03

### Added

- Initial public version of the interactive LVM time-series viewer.
- Multi-channel plotting with playback, scrubbing, and zoom controls.
