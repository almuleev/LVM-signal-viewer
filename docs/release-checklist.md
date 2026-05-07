# Release Checklist

Use this checklist before publishing a new release of **LVM Signal Viewer**.

## Code and Quality

- [ ] `python -m compileall .` passes.
- [ ] `pytest` passes.
- [ ] Manual smoke test done with sample `.lvm` file.
- [ ] No generated artifacts committed (`build/`, `dist/`, `__pycache__/`).

## Versioning and Docs

- [ ] Update `CHANGELOG.md` under `Unreleased`.
- [ ] Move release notes into a version section with date.
- [ ] Confirm README reflects current features and limitations.
- [ ] Confirm no unsupported formats are claimed as supported input.

## Build and Package

- [ ] Build Windows artifact via `LVM_Viewer.spec`.
- [ ] Launch executable and test core controls.
- [ ] Verify `Save PNG` and `Save CSV` exports.
- [ ] Verify app starts in empty mode and `Open file` works.

## GitHub Release

- [ ] Create annotated tag (for example `v0.9.0`).
- [ ] Create Release notes from changelog.
- [ ] Upload Windows build artifact(s).
- [ ] Mark as latest release.

## Post-release

- [ ] Add/update screenshot or demo GIF in `docs/assets/`.
- [ ] Share release in relevant communities.
- [ ] Monitor issues for regressions during first 48 hours.
