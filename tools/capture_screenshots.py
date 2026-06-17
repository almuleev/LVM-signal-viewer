"""Render real screenshots of LVM Signal Viewer for the README and docs.

The whole UI (plot, sliders, buttons, legend, help text) is drawn inside a
single Matplotlib figure, so rendering that figure with the Agg backend yields
a pixel-faithful screenshot of the app without opening a window or touching the
desktop. Run this whenever the UI changes to refresh the images under
``docs/assets``.

Usage:
    python tools/capture_screenshots.py [output_dir]

Default output_dir is ``docs/assets``.
"""

import os
import sys

import matplotlib

matplotlib.use("Agg")  # headless render, must be set before pyplot is imported
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import lvm_viewer as lv  # noqa: E402

DPI = 110
SAMPLE = os.path.join(ROOT, "lvm_files_for_tests", "test.lvm")


def _save(fig, path):
    fig.savefig(path, dpi=DPI, facecolor=fig.get_facecolor(), bbox_inches=None)
    print(f"saved {path}  ({fig.get_size_inches()[0] * DPI:.0f}x"
          f"{fig.get_size_inches()[1] * DPI:.0f}px)")
    plt.close(fig)


def capture_empty(out_dir):
    """Empty start screen with the Open file / Open sample entry points."""
    lv.show_empty_viewer()
    fig = lv.active_ui_refs["fig"]
    _save(fig, os.path.join(out_dir, "empty-start.png"))


def capture_viewer(out_dir, x_mode="time", channels="first", name="screenshot.png"):
    """Main viewer with the bundled sample file loaded.

    x_mode:   "time" or "freq" (Hz spectrum view).
    channels: "first" (default single channel) or "all".
    """
    lv.main(initial_file=SAMPLE)
    fig = lv.fig

    if channels == "all":
        lv.channel_visibility[:] = [True] * len(lv.channel_visibility)

    if x_mode == "freq":
        # Flip the X-axis mode the same way the M hotkey / Mode button does.
        lv.active_ui_refs["set_axis_mode"]("freq")

    if callable(lv.draw_frame_fn):
        lv.draw_frame_fn()
    fig.canvas.draw()
    _save(fig, os.path.join(out_dir, name))


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs", "assets")
    os.makedirs(out_dir, exist_ok=True)

    # Keep the run non-interactive: never block on show(), never pop the range dialog.
    plt.show = lambda *a, **k: None
    lv.select_processing_range = lambda tv: (float(tv[0]), float(tv[-1]))

    capture_empty(out_dir)
    capture_viewer(out_dir, x_mode="time", channels="first", name="screenshot.png")
    capture_viewer(out_dir, x_mode="freq", channels="first", name="screenshot-hz.png")


if __name__ == "__main__":
    main()
