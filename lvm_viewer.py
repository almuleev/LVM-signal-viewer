import os
import sys
import hashlib
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button, CheckButtons, Slider, TextBox

# GENERAL SETTINGS
FILE = ""  # File is selected through a dialog
FPS = 60  # Values above 100 are usually not recommended
STEP = 20  # Seek step
INITIAL_WINDOW_SIZE = 0.2  # Initial view window size (20% of full time range)
PARSER_VERBOSE = False  # Detailed section-level parser logging
MAX_RENDER_POINTS = 6000  # Max points per visible line for responsive rendering
MAX_FFT_SAMPLES = 8192  # Max samples used for spectrum calculation in Hz mode
CACHE_VERSION = 2  # Bump if cached payload format changes
UI_SYNC_FRAME_STRIDE = 4  # Update heavy UI widgets every N frames during playback
ANIMATION_DEFAULT_ENABLED = True
PERF_PROFILES = {
    "fast": {
        "fps": 24,
        "render_points": 2500,
        "fft_samples": 4096,
        "ui_sync_stride": 8,
        "label": "Fast",
    },
    "balanced": {
        "fps": 36,
        "render_points": 4500,
        "fft_samples": 8192,
        "ui_sync_stride": 4,
        "label": "Balanced",
    },
    "quality": {
        "fps": 60,
        "render_points": 8000,
        "fft_samples": 16384,
        "ui_sync_stride": 2,
        "label": "Quality",
    },
}
DEFAULT_PERF_PROFILE = "balanced"
time_range_ref = [1.0]
channel_visibility = []
channel_data_arrays = []
refresh_channel_controls_fn = None
apply_channel_visibility_fn = None
update_zoom_fn = None
draw_frame_fn = None
clear_probe_fn = None
status_text_obj = None
is_loading_data = False
info_text_obj = None
file_info_obj = None
window_percent_ref = [0.0]
edge_anchor_ref = ["none"]  # "left", "right", "none"
data_revision_ref = [0]  # Incremented on each successful data load/reload


# FILE SELECTION
def select_file(exit_on_cancel=True):
    """Open a file selection dialog."""
    root = tk.Tk()
    root.withdraw()  # Hide root window
    root.attributes("-topmost", True)  # Keep dialog above other windows

    file_path = filedialog.askopenfilename(
        title="Select .lvm or .txt file to analyze",
        filetypes=[
            ("LVM files", "*.lvm"),
            ("Text files", "*.txt"),
            ("All files", "*.*"),
        ],
    )
    root.destroy()

    if not file_path:
        if exit_on_cancel:
            print("No file selected. Exiting.")
            sys.exit()
        print("File selection canceled.")
        return None

    return file_path


def select_processing_range(time_values):
    """Ask user which time range should be processed and displayed."""
    if len(time_values) == 0:
        return None

    full_start = float(time_values[0])
    full_end = float(time_values[-1])
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    prompt = (
        "Choose time fragment to process.\n"
        f"Available: {full_start:.9g} .. {full_end:.9g} s\n\n"
        "Leave value unchanged to keep full range."
    )

    def parse_number(value_text, default_value):
        text = (value_text or "").strip()
        if not text:
            return float(default_value)
        return float(text.replace(",", "."))

    try:
        while True:
            from_text = simpledialog.askstring(
                "Processing Range",
                prompt + "\n\nFrom time (s):",
                initialvalue=f"{full_start:.9g}",
                parent=root,
            )
            if from_text is None:
                return None

            to_text = simpledialog.askstring(
                "Processing Range",
                prompt + "\n\nTo time (s):",
                initialvalue=f"{full_end:.9g}",
                parent=root,
            )
            if to_text is None:
                return None

            try:
                start = parse_number(from_text, full_start)
                end = parse_number(to_text, full_end)
            except ValueError:
                messagebox.showerror(
                    "Invalid input",
                    "Invalid number format. Use decimal values.",
                    parent=root,
                )
                continue

            if start > end:
                start, end = end, start
            start = max(full_start, min(full_end, start))
            end = max(full_start, min(full_end, end))
            if end <= start:
                messagebox.showerror(
                    "Invalid range",
                    "Range is too small. Increase the interval.",
                    parent=root,
                )
                continue
            return start, end
    finally:
        root.destroy()


def apply_processing_range(prepared, range_start, range_end):
    """Return subset of prepared data for the selected time range."""
    prepared_df, time_values, channel_frame, _ = prepared

    if range_end < range_start:
        range_start, range_end = range_end, range_start

    # Time is monotonic after `prepare_loaded_data`, so use index slicing.
    # This is much faster and avoids heavy boolean masking on large DataFrames.
    start_idx = int(np.searchsorted(time_values, float(range_start), side="left"))
    end_idx = int(np.searchsorted(time_values, float(range_end), side="right"))
    if end_idx <= start_idx:
        return None

    subset_df = prepared_df.iloc[start_idx:end_idx].reset_index(drop=True)
    subset_time = time_values[start_idx:end_idx].copy()
    subset_channels = channel_frame.iloc[start_idx:end_idx].reset_index(drop=True)
    if len(subset_df) == 0 or len(subset_channels.columns) == 0:
        return None

    return subset_df, subset_time, subset_channels, len(subset_df)


# LVM FILE READING
def read_lvm_file(file_path):
    print(f"Reading LVM file: {os.path.basename(file_path)}")

    metadata_keys = {
        "LabVIEW Measurement",
        "Writer_Version",
        "Reader_Version",
        "Separator",
        "Decimal_Separator",
        "Multi_Headings",
        "X_Columns",
        "Time_Pref",
        "Operator",
        "Date",
        "Time",
        "Channels",
        "Samples",
        "Y_Unit_Label",
        "X_Dimension",
        "X0",
        "Delta_X",
    }
    nan_value = float("nan")

    def is_metadata_line(line):
        first_cell = line.partition("\t")[0].strip()
        return first_cell in metadata_keys

    # Stream parse rows and build columns incrementally to avoid keeping a full
    # in-memory copy of the source file.
    columns = []
    column_has_non_nan = []
    row_count = 0

    header_count = 0
    first_header_line = None
    last_header_line = None
    current_section_idx = 0
    section_hits = 0

    section_has_data = False

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line_index, raw_line in enumerate(f):
                line = raw_line.strip()
                if not line:
                    continue

                if line.startswith("***End_of_Header***"):
                    header_count += 1
                    if first_header_line is None:
                        first_header_line = line_index
                    last_header_line = line_index
                    current_section_idx = header_count
                    section_has_data = False
                    continue

                if line.startswith("***") or is_metadata_line(line):
                    continue

                # Normalize decimal commas and split by tabs.
                line_clean = line.replace(",", ".")
                parts = line_clean.split("\t")

                # Preserve tab positions: invalid/missing cells become NaN instead
                # of being dropped, so channel alignment is not shifted.
                parsed_parts = []
                numeric_value_count = 0
                for part in parts:
                    part = part.strip()
                    if not part:
                        parsed_parts.append(nan_value)
                        continue
                    try:
                        value = float(part)
                    except ValueError:
                        parsed_parts.append(nan_value)
                        continue
                    parsed_parts.append(value)
                    numeric_value_count += 1

                part_count = len(parsed_parts)
                if numeric_value_count < 2:
                    continue

                if not section_has_data:
                    section_has_data = True
                    section_hits += 1
                    if PARSER_VERBOSE:
                        print(
                            f"Numeric data found in section {current_section_idx} at line {line_index}: "
                            f"{parsed_parts[:2]}..."
                        )

                # Dynamically widen the column store when needed.
                col_count = len(columns)
                if part_count > col_count:
                    additional_cols = part_count - col_count
                    for _ in range(additional_cols):
                        columns.append([nan_value] * row_count)
                        column_has_non_nan.append(False)
                    col_count = len(columns)

                # Fast path: fixed-width rows (most common in LVM data sections).
                if part_count == col_count:
                    for col_idx, value in enumerate(parsed_parts):
                        columns[col_idx].append(value)
                        if value == value:  # Fast NaN check.
                            column_has_non_nan[col_idx] = True
                else:
                    for col_idx, value in enumerate(parsed_parts):
                        columns[col_idx].append(value)
                        if value == value:
                            column_has_non_nan[col_idx] = True
                    for col_idx in range(part_count, col_count):
                        columns[col_idx].append(nan_value)
                row_count += 1
    except Exception as e:
        print(f"File read error: {e}")
        return pd.DataFrame()

    if header_count:
        if PARSER_VERBOSE:
            print(
                f"Header end markers found: {header_count} "
                f"(first: {first_header_line}, last: {last_header_line})"
            )
        else:
            print(f"Header end markers found: {header_count}")
    else:
        print("Header end markers found: 0")

    print(f"Sections with numeric data: {section_hits}")

    print(f"Collected {row_count} data rows")

    if row_count == 0 or not columns:
        print("No numeric data found")
        return pd.DataFrame()

    # Build DataFrame from the assembled columns.
    max_cols = len(columns)
    print(f"Maximum column count: {max_cols}")
    data_dict = {"Time": columns[0]}  # First column is time.
    for i in range(1, max_cols):
        if i < len(column_has_non_nan) and column_has_non_nan[i]:
            data_dict[f"Channel_{i}"] = columns[i]

    df = pd.DataFrame(data_dict)
    df = df.dropna(subset=["Time"])

    print(f"DataFrame created with {len(df)} rows and {len(df.columns)} columns")
    print(f"Columns: {list(df.columns)}")
    return df


def get_cache_dir():
    """Return platform-appropriate cache directory for this app."""
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA") or os.path.expanduser(
            "~/AppData/Local"
        )
        return os.path.join(root, "LVMReader", "cache")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Caches/LVMReader")
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        return os.path.join(xdg_cache, "lvm-reader")
    return os.path.expanduser("~/.cache/lvm-reader")


def get_cache_path(file_path):
    """Return canonical cache file path in the app cache directory."""
    cache_dir = get_cache_dir()
    os.makedirs(cache_dir, exist_ok=True)
    abs_path = os.path.abspath(file_path)
    path_hash = hashlib.sha1(abs_path.encode("utf-8", errors="ignore")).hexdigest()[:12]
    base_name = os.path.basename(file_path)
    return os.path.join(cache_dir, f"{base_name}.{path_hash}.lvmcache.npz")


def get_legacy_cache_path(file_path):
    """Return legacy sidecar cache path kept for backward compatibility."""
    directory = os.path.dirname(file_path)
    base_name = os.path.basename(file_path)
    return os.path.join(directory, f"{base_name}.lvmcache.npz")


def load_prepared_data_from_cache(file_path):
    """Load prepared data tuple from a local .npz cache if it is valid."""
    canonical_cache_path = get_cache_path(file_path)
    legacy_cache_path = get_legacy_cache_path(file_path)
    source_stat = os.stat(file_path)

    def load_from_path(path):
        with np.load(path, allow_pickle=False) as cached:
            if int(cached["cache_version"]) != CACHE_VERSION:
                return None
            if int(cached["source_size"]) != int(source_stat.st_size):
                return None
            if int(cached["source_mtime_ns"]) != int(source_stat.st_mtime_ns):
                return None

            time_raw = cached["time_raw"]
            time_values = cached["time_values"]
            channel_names = cached["channel_names"].tolist()
            channel_data = cached["channel_data"]

        if channel_data.ndim == 1:
            channel_data = channel_data.reshape(-1, 1)

        channels_frame = pd.DataFrame(channel_data, columns=channel_names)
        prepared_df = pd.concat([pd.Series(time_raw, name="Time"), channels_frame], axis=1)

        if channels_frame.empty or len(time_values) == 0:
            return None
        if len(channels_frame) != len(time_values):
            return None
        return prepared_df, time_values, channels_frame, len(prepared_df)

    try:
        if os.path.exists(canonical_cache_path):
            prepared = load_from_path(canonical_cache_path)
            if prepared is not None:
                print(f"Loaded from cache: {os.path.basename(canonical_cache_path)}")
                return prepared

        if os.path.exists(legacy_cache_path):
            prepared = load_from_path(legacy_cache_path)
            if prepared is not None:
                print(f"Loaded from legacy cache: {os.path.basename(legacy_cache_path)}")
                # One-time migration to canonical cache location.
                save_prepared_data_to_cache(file_path, prepared)
                try:
                    os.remove(legacy_cache_path)
                    print("Legacy sidecar cache moved to app cache directory.")
                except OSError:
                    pass
                return prepared
        return None
    except Exception as e:
        print(f"Cache load error: {e}")
        return None


def save_prepared_data_to_cache(file_path, prepared_tuple):
    """Save prepared data tuple to a local .npz cache next to source file."""
    cache_path = get_cache_path(file_path)
    prepared_df, time_values, channel_frame, _ = prepared_tuple

    try:
        source_stat = os.stat(file_path)
        np.savez_compressed(
            cache_path,
            cache_version=np.array(CACHE_VERSION, dtype=np.int64),
            source_size=np.array(source_stat.st_size, dtype=np.int64),
            source_mtime_ns=np.array(source_stat.st_mtime_ns, dtype=np.int64),
            time_raw=prepared_df["Time"].to_numpy(dtype=float, copy=False),
            time_values=np.asarray(time_values, dtype=float),
            channel_names=np.asarray(channel_frame.columns, dtype="U"),
            channel_data=channel_frame.to_numpy(dtype=float, copy=False),
        )
        print(f"Cache saved: {os.path.basename(cache_path)}")
    except Exception as e:
        print(f"Cache save skipped: {e}")


def prepare_loaded_data(df):
    """Validate parsed data and return plotting-ready structures."""
    if df.empty:
        return None

    if "Time" not in df.columns:
        print("Missing required 'Time' column.")
        return None

    # `read_lvm_file` already produces numeric values and drops invalid `Time`.
    prepared = df
    raw_time = prepared["Time"].to_numpy(dtype=float)
    time_values = raw_time.copy()
    if len(time_values) == 0:
        print("No valid timestamps after parsing.")
        return None

    # Build a monotonic plotting timeline to avoid zig-zag artifacts when
    # Multi_Headings sections reset local time back to the start.
    if len(time_values) > 1:
        diffs = np.diff(time_values)
        positive_diffs = diffs[diffs > 0]
        fallback_step = float(np.median(positive_diffs)) if positive_diffs.size else 1e-6
        if fallback_step <= 0:
            fallback_step = 1e-6

        offset = 0.0
        for i in range(1, len(time_values)):
            candidate = raw_time[i] + offset
            if candidate < time_values[i - 1]:
                offset = time_values[i - 1] + fallback_step - raw_time[i]
                candidate = raw_time[i] + offset
            time_values[i] = candidate

    channel_frame = prepared.drop(columns=["Time"])

    # Drop pseudo-channels that are actually duplicated X/time columns.
    duplicate_time_channels = []

    def is_duplicate_time_column(col_values, ref_time):
        valid_mask = np.isfinite(col_values) & np.isfinite(ref_time)
        if not valid_mask.any():
            return False

        valid_idx = np.flatnonzero(valid_mask)
        sample_size = min(2048, valid_idx.size)
        if sample_size == 0:
            return False

        if valid_idx.size > sample_size:
            sample_idx = valid_idx[
                np.linspace(0, valid_idx.size - 1, sample_size, dtype=int)
            ]
        else:
            sample_idx = valid_idx

        # Fast reject using sampled points, then exact check for positives.
        if not np.allclose(
            col_values[sample_idx],
            ref_time[sample_idx],
            rtol=1e-9,
            atol=1e-12,
        ):
            return False

        return np.allclose(
            col_values[valid_idx],
            ref_time[valid_idx],
            rtol=1e-9,
            atol=1e-12,
        )

    for col in channel_frame.columns:
        col_values = channel_frame[col].to_numpy(dtype=float)
        if is_duplicate_time_column(col_values, raw_time):
            duplicate_time_channels.append(col)

    if duplicate_time_channels:
        channel_frame = channel_frame.drop(columns=duplicate_time_channels)
        prepared = prepared.loc[:, ["Time", *channel_frame.columns]]
        print(
            "Dropped time-axis duplicate channels: "
            f"{', '.join(duplicate_time_channels)}"
        )

    if len(channel_frame.columns) == 0:
        print("No data channels available for display.")
        return None

    return prepared, time_values, channel_frame, len(prepared)


# RELOAD DATA WITH A NEW FILE
def reload_with_new_file(event=None):
    """Reload viewer data from a newly selected file."""
    global FILE, time, channels, n, current_frame, is_playing, current_center, time_range_ref
    global channel_data_arrays, is_loading_data

    if is_loading_data:
        return
    new_file = select_file(exit_on_cancel=False)
    if not new_file:
        return

    print(f"Loading new file: {new_file}")
    is_loading_data = True
    set_status_text("Loading file...", color="tab:orange", redraw=True)
    try:
        prepared = load_prepared_data_from_cache(new_file)
        if prepared is None:
            new_df = read_lvm_file(new_file)
            set_status_text("Processing data...", color="tab:orange", redraw=True)
            prepared = prepare_loaded_data(new_df)
            if prepared is not None:
                set_status_text("Saving cache...", color="tab:orange", redraw=True)
                save_prepared_data_to_cache(new_file, prepared)
        else:
            set_status_text("Loaded from cache", color="tab:green", redraw=True)

        if prepared is None:
            print("Failed to prepare data from the new file.")
            set_status_text("Load failed", color="tab:red", redraw=True)
            return

        set_status_text("Select processing range...", color="tab:orange", redraw=True)
        selected_range = select_processing_range(prepared[1])
        if selected_range is None:
            print("Processing range selection canceled.")
            set_status_text("Range selection canceled", color="tab:orange", redraw=True)
            return
        prepared = apply_processing_range(prepared, selected_range[0], selected_range[1])
        if prepared is None:
            print("Selected range has no data.")
            set_status_text("Selected range has no data", color="tab:red", redraw=True)
            return

        FILE = new_file
        _, time, channels, n = prepared
        channel_data_arrays = [
            channels[col].to_numpy(dtype=float, copy=False) for col in channels.columns
        ]
        data_revision_ref[0] += 1
        print(f"Loaded {len(channels.columns)} channels, {n} samples")
        print(f"Time range: {time[0]} - {time[-1]}")

        new_time_range = time[-1] - time[0]
        if new_time_range == 0:
            new_time_range = 1
        time_range_ref[0] = new_time_range

        # Reset playback state.
        current_frame[0] = 0
        is_playing[0] = False
        edge_anchor_ref[0] = "none"
        current_center[0] = time[0] + (time[-1] - time[0]) * INITIAL_WINDOW_SIZE * 0.8
        if callable(clear_probe_fn):
            clear_probe_fn()

        # Refresh plot and labels.
        update_plot_data()
        if callable(update_zoom_fn):
            update_zoom_fn(zoom_level[0])
        if callable(draw_frame_fn):
            draw_frame_fn()
        update_info_text()
        set_status_text("Ready", color="tab:green", redraw=True)
    finally:
        is_loading_data = False


def update_plot_data():
    """Refresh plotted data after file switch."""
    global lines, ax, channel_visibility

    for line in lines:
        line.remove()
    lines = []

    for c in channels.columns:
        line, = ax.plot([], [], label=c, linewidth=1)
        lines.append(line)

    # By default keep only the first channel active after load/reload.
    channel_visibility = [i == 0 for i in range(len(channels.columns))]

    if callable(refresh_channel_controls_fn):
        refresh_channel_controls_fn()
    if callable(apply_channel_visibility_fn):
        apply_channel_visibility_fn()


def update_info_text():
    """Update informational labels."""
    global info_text_obj, file_info_obj, channel_visibility, window_percent_ref

    visible_channels = 0
    if channel_visibility and len(channel_visibility) == len(channels.columns):
        visible_channels = sum(1 for is_visible in channel_visibility if is_visible)
    else:
        visible_channels = len(channels.columns)

    window_percent = float(window_percent_ref[0])

    info_text = (
        f"Channels: {len(channels.columns)} | "
        f"Visible: {visible_channels} | "
        f"Samples: {n} | "
        f"Duration: {time[-1] - time[0]:.3f}s | "
        f"Window: {window_percent:.1f}%"
    )
    if info_text_obj is None:
        info_text_obj = plt.figtext(0.05, 0.957, info_text, fontsize=10, ha="left")
    else:
        info_text_obj.set_text(info_text)

    file_name = os.path.basename(FILE)
    if len(file_name) > 64:
        file_name = "..." + file_name[-61:]
    file_info = f"File: {file_name}"
    if file_info_obj is None:
        file_info_obj = plt.figtext(
            0.05, 0.985, file_info, fontsize=10, ha="left", weight="bold"
        )
    else:
        file_info_obj.set_text(file_info)


def set_status_text(message, color="dimgray", redraw=False):
    """Update or create a small status text in the figure."""
    global status_text_obj, fig

    if "fig" not in globals():
        return

    if status_text_obj is None:
        status_text_obj = plt.figtext(
            0.99, 0.985, message, fontsize=10, ha="right", va="top", color=color
        )
    else:
        status_text_obj.set_text(message)
        status_text_obj.set_color(color)

    if redraw and fig.canvas is not None:
        fig.canvas.draw_idle()
        plt.pause(0.001)


def show_empty_viewer():
    """Show app window without loaded data and allow opening a file later."""
    fig_empty, ax_empty = plt.subplots(figsize=(14, 8))
    ax_empty.axis("off")
    ax_empty.text(
        0.5,
        0.62,
        "No file selected",
        ha="center",
        va="center",
        fontsize=22,
        weight="bold",
    )
    ax_empty.text(
        0.5,
        0.48,
        "Click 'Open file' to load a .lvm or .txt dataset.",
        ha="center",
        va="center",
        fontsize=12,
        color="dimgray",
    )

    ax_open = plt.axes([0.42, 0.32, 0.16, 0.08])
    btn_open = Button(ax_open, "Open file")

    def on_open(event=None):
        selected_file = select_file(exit_on_cancel=False)
        if not selected_file:
            return
        plt.close(fig_empty)
        main(initial_file=selected_file)

    btn_open.on_clicked(on_open)
    plt.gcf().canvas.manager.set_window_title("LVM Data Viewer - No file")
    plt.show()


# MAIN PROGRAM
def main(initial_file=None):
    global FILE, time, channels, n, lines, ax, fig, update_zoom_fn, draw_frame_fn, time_range_ref
    global channel_visibility, channel_data_arrays, refresh_channel_controls_fn, apply_channel_visibility_fn
    global current_frame, is_playing, current_center, zoom_level
    global info_text_obj, file_info_obj, window_percent_ref
    global clear_probe_fn

    FILE = initial_file
    if not FILE:
        print("Started in empty mode.")
        show_empty_viewer()
        return

    fig, ax = plt.subplots(figsize=(14, 8))
    set_status_text("Loading file...", color="tab:orange", redraw=True)

    prepared = load_prepared_data_from_cache(FILE)
    if prepared is None:
        raw_df = read_lvm_file(FILE)
        set_status_text("Processing data...", color="tab:orange", redraw=True)
        prepared = prepare_loaded_data(raw_df)
        if prepared is not None:
            set_status_text("Saving cache...", color="tab:orange", redraw=True)
            save_prepared_data_to_cache(FILE, prepared)
    else:
        set_status_text("Loaded from cache", color="tab:green", redraw=True)

    if prepared is None:
        print("Failed to prepare data from file.")
        set_status_text("Load failed", color="tab:red", redraw=True)
        sys.exit()

    set_status_text("Select processing range...", color="tab:orange", redraw=True)
    selected_range = select_processing_range(prepared[1])
    if selected_range is None:
        print("Processing range selection canceled. Exiting.")
        sys.exit()
    prepared = apply_processing_range(prepared, selected_range[0], selected_range[1])
    if prepared is None:
        print("Selected range has no data. Exiting.")
        sys.exit()

    _, time, channels, n = prepared
    channel_data_arrays = [
        channels[col].to_numpy(dtype=float, copy=False) for col in channels.columns
    ]
    data_revision_ref[0] += 1
    print(f"Loaded {len(channels.columns)} channels, {n} samples")
    print(f"Time range: {time[0]} - {time[-1]}")

    lines = [ax.plot([], [], label=c, linewidth=1)[0] for c in channels.columns]
    channel_visibility = [i == 0 for i in range(len(channels.columns))]
    channel_control = {"ax": None, "widget": None}
    channel_index_by_label = {name: idx for idx, name in enumerate(channels.columns)}

    time_range = time[-1] - time[0]
    if time_range == 0:
        time_range = 1
    time_range_ref[0] = time_range

    # Global playback state.
    current_frame = [0]
    is_playing = [False]
    edge_anchor_ref[0] = "none"
    edge_anchor = edge_anchor_ref
    animation_enabled = [ANIMATION_DEFAULT_ENABLED]
    x_axis_mode = ["freq"]  # "time" or "freq"
    ani_ref = [None]
    slider_lock = [False]
    last_slider_frame = [-1]
    window_size = [time_range * INITIAL_WINDOW_SIZE]
    zoom_level = [50]
    perf_profile_key = [DEFAULT_PERF_PROFILE]
    fps_ref = [PERF_PROFILES[DEFAULT_PERF_PROFILE]["fps"]]
    render_points_ref = [PERF_PROFILES[DEFAULT_PERF_PROFILE]["render_points"]]
    fft_samples_ref = [PERF_PROFILES[DEFAULT_PERF_PROFILE]["fft_samples"]]
    ui_sync_stride_ref = [PERF_PROFILES[DEFAULT_PERF_PROFILE]["ui_sync_stride"]]
    # Allow deep zoom from Window input below 1% (e.g. 0.5%, 0.1%).
    min_zoom_scale = 0.0001
    max_zoom_scale = 1.0
    zoom_exponent = 3.0

    # Initial window center.
    initial_center = time[0] + window_size[0] * 0.8
    current_center = [initial_center]

    def zoom_to_scale_factor(zoom_value):
        normalized_val = float(zoom_value) / 100.0
        return min_zoom_scale + (max_zoom_scale - min_zoom_scale) * (
            normalized_val ** zoom_exponent
        )

    def scale_factor_to_zoom(scale_factor):
        clamped_scale = min(max_zoom_scale, max(min_zoom_scale, float(scale_factor)))
        normalized = (clamped_scale - min_zoom_scale) / (max_zoom_scale - min_zoom_scale)
        return 100.0 * (normalized ** (1.0 / zoom_exponent))

    def get_timeline_fraction_from_frame():
        """Map current frame to [0..1] timeline fraction."""
        if n <= 1:
            return 0.0
        return min(1.0, max(0.0, float(current_frame[0]) / float(n - 1)))

    def apply_window_position_for_timeline_fraction(timeline_fraction):
        """Place visible window according to timeline position and current zoom."""
        frac = min(1.0, max(0.0, float(timeline_fraction)))
        edge_tol = 1e-6

        if frac <= edge_tol:
            edge_anchor[0] = "left"
            window_start = time[0]
        elif frac >= 1.0 - edge_tol:
            edge_anchor[0] = "right"
            window_start = time[-1] - window_size[0]
        else:
            edge_anchor[0] = "none"
            available_range = max(0.0, (time[-1] - time[0]) - window_size[0])
            if available_range > 1e-12:
                window_start = time[0] + frac * available_range
            else:
                window_start = time[0]

        window_end = window_start + window_size[0]
        current_center[0] = (window_start + window_end) * 0.5

    def update_zoom(val):
        zoom_level[0] = val
        scale_factor = zoom_to_scale_factor(zoom_level[0])
        window_size[0] = time_range_ref[0] * scale_factor
        if time_range_ref[0] > 0:
            window_percent_ref[0] = max(
                0.0, min(100.0, (window_size[0] / time_range_ref[0]) * 100.0)
            )
        else:
            window_percent_ref[0] = 0.0
        apply_window_position_for_timeline_fraction(get_timeline_fraction_from_frame())
        update_display_window()
        draw_frame()

    def get_display_window_bounds():
        if window_size[0] > time_range_ref[0]:
            window_size[0] = time_range_ref[0]
        half_window = window_size[0] / 2

        if edge_anchor[0] == "left":
            window_start = time[0]
            window_end = window_start + window_size[0]
            current_center[0] = window_start + half_window
            return window_start, window_end
        if edge_anchor[0] == "right":
            window_end = time[-1]
            window_start = window_end - window_size[0]
            current_center[0] = window_end - half_window
            return window_start, window_end

        window_start = current_center[0] - half_window
        window_end = current_center[0] + half_window

        if window_start < time[0]:
            window_start = time[0]
            window_end = window_start + window_size[0]
            current_center[0] = window_start + half_window
        if window_end > time[-1]:
            window_end = time[-1]
            window_start = window_end - window_size[0]
            current_center[0] = window_end - half_window

        return window_start, window_end

    def get_display_window_indices():
        window_start, window_end = get_display_window_bounds()
        start_idx = max(0, np.searchsorted(time, window_start) - 10)
        end_idx = min(n, np.searchsorted(time, window_end) + 10)
        return start_idx, end_idx

    def update_display_window():
        window_start, window_end = get_display_window_bounds()
        if x_axis_mode[0] == "time":
            ax.set_xlim(window_start, window_end)

    def seek_to_frame(target_frame, pause_playback=True):
        if n <= 0:
            return
        if pause_playback:
            is_playing[0] = False
        edge_anchor[0] = "none"
        current_frame[0] = int(min(max(0, target_frame), n - 1))
        current_center[0] = time[current_frame[0]]
        update_display_window()
        draw_frame(force_ui_sync=True)

    def shift_frame(delta):
        seek_to_frame(current_frame[0] + int(delta), pause_playback=True)

    def jump_to_start():
        seek_to_frame(0, pause_playback=True)
        if n > 0:
            edge_anchor[0] = "left"
            current_center[0] = time[0] + window_size[0] * 0.8
            update_display_window()
            draw_frame(force_ui_sync=True)

    def jump_to_end():
        seek_to_frame(n - 1, pause_playback=True)
        if n > 0:
            edge_anchor[0] = "right"
            current_center[0] = time[-1] - window_size[0] * 0.5
            update_display_window()
            draw_frame(force_ui_sync=True)

    y_min = channels.min().min()
    y_max = channels.max().max()
    y_range = y_max - y_min
    if y_range == 0:
        y_range = 1
    y_margin = y_range * 0.1
    ax.set_ylim(y_min - y_margin, y_max + y_margin)

    if x_axis_mode[0] == "time":
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Value (V)")
    else:
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel("Amplitude")
    ax.grid(True, alpha=0.3)
    plt.subplots_adjust(bottom=0.3, right=0.8, top=0.82)

    last_ylim = [None]

    def apply_dynamic_ylim(y_min, y_max):
        if not np.isfinite(y_min) or not np.isfinite(y_max):
            return
        y_range = y_max - y_min
        if y_range == 0:
            # Flat signal: keep a small proportional margin around the value.
            flat_margin = max(abs(y_min) * 0.01, 1e-9)
            y_low = y_min - flat_margin
            y_high = y_max + flat_margin
        else:
            y_margin = y_range * 0.1
            y_low = y_min - y_margin
            y_high = y_max + y_margin

        prev_ylim = last_ylim[0]
        if prev_ylim is not None:
            if abs(prev_ylim[0] - y_low) < 1e-12 and abs(prev_ylim[1] - y_high) < 1e-12:
                return

        ax.set_ylim(y_low, y_high)
        last_ylim[0] = (y_low, y_high)

    def update_y_limits_for_visible_channels(start_idx=None, end_idx=None):
        active_indices = [
            i for i, is_visible in enumerate(channel_visibility) if is_visible
        ]
        if not active_indices:
            return

        use_window = (
            start_idx is not None
            and end_idx is not None
            and 0 <= int(start_idx) < int(end_idx) <= n
        )
        y_min = np.inf
        y_max = -np.inf
        for idx in active_indices:
            arr = channel_data_arrays[idx]
            view = arr[start_idx:end_idx] if use_window else arr
            if view.size == 0:
                continue
            local_min = np.nanmin(view)
            local_max = np.nanmax(view)
            if local_min < y_min:
                y_min = local_min
            if local_max > y_max:
                y_max = local_max

        apply_dynamic_ylim(y_min, y_max)

    def apply_channel_visibility():
        for idx, line in enumerate(lines):
            is_visible = idx < len(channel_visibility) and channel_visibility[idx]
            line.set_visible(is_visible)
            if not is_visible:
                line.set_data([], [])

        visible_indices = [
            idx for idx, is_visible in enumerate(channel_visibility) if is_visible
        ]
        if visible_indices:
            ax.legend(
                handles=[lines[idx] for idx in visible_indices],
                labels=[channels.columns[idx] for idx in visible_indices],
                loc="upper right",
            )
        else:
            legend = ax.get_legend()
            if legend is not None:
                legend.remove()

        if x_axis_mode[0] == "time":
            update_y_limits_for_visible_channels()

    def rebuild_channel_controls():
        if channel_control["ax"] is not None:
            channel_control["ax"].remove()

        labels = list(channels.columns)
        channel_index_by_label.clear()
        channel_index_by_label.update({name: idx for idx, name in enumerate(labels)})

        panel_height = min(0.52, 0.04 * max(6, len(labels)))
        panel_top = 0.82
        channel_control["ax"] = plt.axes([0.81, panel_top - panel_height, 0.18, panel_height])
        channel_control["ax"].set_title("Channels", fontsize=9)

        channel_control["widget"] = CheckButtons(
            channel_control["ax"], labels, channel_visibility
        )

        for text in channel_control["widget"].labels:
            text.set_fontsize(8)

        def on_channel_toggle(label):
            idx = channel_index_by_label.get(label)
            if idx is None:
                return
            channel_visibility[idx] = not channel_visibility[idx]
            apply_channel_visibility()
            draw_frame()
            update_info_text()

        channel_control["widget"].on_clicked(on_channel_toggle)

    last_ui_sync_frame = [-int(ui_sync_stride_ref[0])]
    freq_render_cache = {
        "signature": None,
        "freq_view": None,
        "amp_by_channel": {},
        "y_min": np.nan,
        "y_max": np.nan,
        "x_max": 0.0,
    }

    def draw_frame(force_ui_sync=False):
        if n == 0:
            return

        start_idx, end_idx = get_display_window_indices()
        span = max(0, end_idx - start_idx)
        max_points = max(500, int(render_points_ref[0]))

        y_min = np.inf
        y_max = -np.inf

        if x_axis_mode[0] == "time":
            freq_render_cache["signature"] = None
            step = max(1, span // max_points) if span > max_points else 1
            time_view = time[start_idx:end_idx:step]

            for i, _ in enumerate(channels.columns):
                if i < len(channel_visibility) and channel_visibility[i]:
                    y_view = channel_data_arrays[i][start_idx:end_idx:step]
                    lines[i].set_data(time_view, y_view)
                    if y_view.size:
                        local_min = np.nanmin(y_view)
                        local_max = np.nanmax(y_view)
                        if np.isfinite(local_min) and local_min < y_min:
                            y_min = local_min
                        if np.isfinite(local_max) and local_max > y_max:
                            y_max = local_max
                else:
                    lines[i].set_data([], [])
        else:
            if span < 4:
                for line in lines:
                    line.set_data([], [])
                freq_render_cache["signature"] = None
            else:
                visible_indices = tuple(
                    i for i, is_visible in enumerate(channel_visibility) if is_visible
                )
                signature = (int(data_revision_ref[0]), start_idx, end_idx, visible_indices)

                if signature != freq_render_cache["signature"]:
                    max_fft_samples = max(1024, int(fft_samples_ref[0]))
                    if span > max_fft_samples:
                        sample_idx = np.linspace(
                            start_idx, end_idx - 1, max_fft_samples, dtype=int
                        )
                    else:
                        sample_idx = np.arange(start_idx, end_idx, dtype=int)

                    time_view = time[sample_idx]
                    dt = np.diff(time_view)
                    positive_dt = dt[dt > 0]
                    if positive_dt.size == 0:
                        for line in lines:
                            line.set_data([], [])
                        freq_render_cache["signature"] = None
                        apply_dynamic_ylim(y_min, y_max)
                        fig.canvas.draw_idle()
                        return

                    sample_dt = float(np.median(positive_dt))
                    freq_template = np.fft.rfftfreq(time_view.size, d=sample_dt)
                    if freq_template.size == 0:
                        for line in lines:
                            line.set_data([], [])
                        freq_render_cache["signature"] = None
                        apply_dynamic_ylim(y_min, y_max)
                        fig.canvas.draw_idle()
                        return

                    f_step = (
                        max(1, freq_template.size // max_points)
                        if freq_template.size > max_points
                        else 1
                    )
                    freq_view = freq_template[::f_step]
                    amp_by_channel = {}
                    cache_y_min = np.inf
                    cache_y_max = -np.inf

                    for i in visible_indices:
                        y_raw = channel_data_arrays[i][sample_idx]
                        finite_mask = np.isfinite(y_raw)
                        if finite_mask.sum() < 4:
                            continue
                        mean_val = float(np.nanmean(y_raw[finite_mask]))
                        y_clean = np.where(finite_mask, y_raw, mean_val)
                        centered = y_clean - np.mean(y_clean)
                        fft_vals = np.fft.rfft(centered)
                        amp = (2.0 / centered.size) * np.abs(fft_vals)
                        amp_view = amp[::f_step]
                        amp_by_channel[i] = amp_view

                        local_min = np.nanmin(amp_view) if amp_view.size else np.nan
                        local_max = np.nanmax(amp_view) if amp_view.size else np.nan
                        if np.isfinite(local_min) and local_min < cache_y_min:
                            cache_y_min = local_min
                        if np.isfinite(local_max) and local_max > cache_y_max:
                            cache_y_max = local_max

                    freq_render_cache["signature"] = signature
                    freq_render_cache["freq_view"] = freq_view
                    freq_render_cache["amp_by_channel"] = amp_by_channel
                    freq_render_cache["y_min"] = cache_y_min
                    freq_render_cache["y_max"] = cache_y_max
                    freq_render_cache["x_max"] = 0.5 / sample_dt if sample_dt > 0 else 0.0

                freq_view = freq_render_cache["freq_view"]
                amp_by_channel = freq_render_cache["amp_by_channel"]
                for i, _ in enumerate(channels.columns):
                    if i in amp_by_channel:
                        lines[i].set_data(freq_view, amp_by_channel[i])
                    else:
                        lines[i].set_data([], [])

                y_min = freq_render_cache["y_min"]
                y_max = freq_render_cache["y_max"]
                if freq_render_cache["x_max"] > 0:
                    ax.set_xlim(0.0, freq_render_cache["x_max"])

        apply_dynamic_ylim(y_min, y_max)

        should_sync_ui = force_ui_sync or (not is_playing[0]) or (
            current_frame[0] - last_ui_sync_frame[0] >= int(ui_sync_stride_ref[0])
        )
        if should_sync_ui:
            if not slider_lock[0] and n > 1:
                old_val = time_slider.val
                new_val = current_frame[0] / (n - 1)
                if abs(old_val - new_val) > 1e-6:
                    time_slider.eventson = False
                    time_slider.set_val(new_val)
                    time_slider.eventson = True
            update_input_boxes()
            update_info_text()
            last_ui_sync_frame[0] = current_frame[0]

        fig.canvas.draw_idle()

    refresh_channel_controls_fn = rebuild_channel_controls
    apply_channel_visibility_fn = apply_channel_visibility
    update_zoom_fn = update_zoom
    draw_frame_fn = draw_frame
    rebuild_channel_controls()
    apply_channel_visibility()

    def update(_):
        if not animation_enabled[0]:
            return lines

        if is_playing[0] and current_frame[0] < n - 1:
            current_frame[0] += 1

            if current_frame[0] < n:
                current_time = time[min(current_frame[0], n - 1)]
                target_center = current_time + window_size[0] * 0.3
                max_center = time[-1] - window_size[0] * 0.5
                target_center = min(target_center, max_center)
                smoothing_factor = 0.3
                current_center[0] = (
                    current_center[0] * (1 - smoothing_factor)
                    + target_center * smoothing_factor
                )
                update_display_window()

            draw_frame()
        elif current_frame[0] >= n - 1:
            if current_center[0] < time[-1] - window_size[0] * 0.5:
                target_center = time[-1] - window_size[0] * 0.5
                smoothing_factor = 0.2
                current_center[0] = (
                    current_center[0] * (1 - smoothing_factor)
                    + target_center * smoothing_factor
                )
                update_display_window()
                draw_frame()
            else:
                is_playing[0] = False
                print("Reached end of data")
        return lines

    # Time control buttons.
    ax_back = plt.axes([0.1, 0.18, 0.08, 0.06])
    ax_play = plt.axes([0.2, 0.18, 0.08, 0.06])
    ax_stop = plt.axes([0.3, 0.18, 0.08, 0.06])
    ax_forw = plt.axes([0.4, 0.18, 0.08, 0.06])
    ax_open = plt.axes([0.5, 0.18, 0.08, 0.06])
    ax_anim = plt.axes([0.6, 0.18, 0.12, 0.06])
    ax_mode = plt.axes([0.73, 0.18, 0.10, 0.06])
    ax_probe = plt.axes([0.84, 0.18, 0.14, 0.06])
    ax_perf = plt.axes([0.84, 0.24, 0.14, 0.05])

    btn_back = Button(ax_back, "Back")
    btn_play = Button(ax_play, "Play")
    btn_stop = Button(ax_stop, "Pause")
    btn_forw = Button(ax_forw, "Forward")
    btn_open = Button(ax_open, "Open")
    btn_anim = Button(ax_anim, "Anim: On")
    btn_mode = Button(ax_mode, "X: Hz")
    btn_probe = Button(ax_probe, "Probe: Off")
    btn_perf = Button(ax_perf, "Perf: Bal")

    probe_enabled = [False]
    probe_artist = {"point": None, "text": None}

    def clear_probe():
        if probe_artist["point"] is not None:
            try:
                probe_artist["point"].remove()
            except Exception:
                pass
            probe_artist["point"] = None
        if probe_artist["text"] is not None:
            try:
                probe_artist["text"].remove()
            except Exception:
                pass
            probe_artist["text"] = None
        fig.canvas.draw_idle()

    def find_nearest_visible_point(x_target, y_target):
        best = None
        x_span = max(1e-12, abs(ax.get_xlim()[1] - ax.get_xlim()[0]))
        y_span = max(1e-12, abs(ax.get_ylim()[1] - ax.get_ylim()[0]))
        for idx, line in enumerate(lines):
            if not (idx < len(channel_visibility) and channel_visibility[idx]):
                continue
            x_data, y_data = line.get_data()
            x_data = np.asarray(x_data, dtype=float)
            y_data = np.asarray(y_data, dtype=float)
            if len(x_data) == 0:
                continue
            dx = (x_data - x_target) / x_span
            dy = (y_data - y_target) / y_span
            dist2 = dx * dx + dy * dy
            nearest_i = int(np.argmin(dist2))
            score = float(dist2[nearest_i])
            if best is None or score < best["score"]:
                best = {
                    "score": score,
                    "x": float(x_data[nearest_i]),
                    "y": float(y_data[nearest_i]),
                    "channel": channels.columns[idx],
                }
        return best

    def render_probe(hit):
        clear_probe()
        if hit is None:
            set_status_text("No visible point found", color="tab:orange", redraw=False)
            return

        point_artist, = ax.plot(
            [hit["x"]], [hit["y"]], marker="o", markersize=6, color="black", zorder=9
        )
        probe_artist["point"] = point_artist

        if x_axis_mode[0] == "time":
            x_line = f"Time={hit['x']:.9g} s"
        else:
            x_line = f"Freq={hit['x']:.9g} Hz"
        info = f"{hit['channel']}\n{x_line}\nValue={hit['y']:.9g}"
        probe_artist["text"] = ax.text(
            hit["x"],
            hit["y"],
            info,
            fontsize=8,
            ha="left",
            va="bottom",
            bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.85},
            zorder=10,
        )
        set_status_text("Point probed", color="tab:green", redraw=False)
        fig.canvas.draw_idle()

    def on_probe_click(event):
        if not probe_enabled[0]:
            return
        if event.inaxes != ax:
            return
        if event.button == 3:
            clear_probe()
            set_status_text("Probe cleared", color="tab:green", redraw=False)
            return
        if event.button != 1 or event.xdata is None or event.ydata is None:
            return

        hit = find_nearest_visible_point(float(event.xdata), float(event.ydata))
        render_probe(hit)

    def set_probe_enabled(enabled):
        probe_enabled[0] = bool(enabled)
        btn_probe.label.set_text("Probe: On" if enabled else "Probe: Off")
        if not enabled:
            clear_probe()
            set_status_text("Probe disabled", color="tab:orange", redraw=False)
        else:
            set_status_text(
                "Probe enabled: Left click point, Right click to clear",
                color="tab:green",
                redraw=False,
            )
        fig.canvas.draw_idle()

    def toggle_probe(event=None):
        set_probe_enabled(not probe_enabled[0])

    def set_performance_profile(profile_key):
        key = str(profile_key).lower()
        if key not in PERF_PROFILES:
            return
        profile = PERF_PROFILES[key]
        perf_profile_key[0] = key
        fps_ref[0] = int(profile["fps"])
        render_points_ref[0] = int(profile["render_points"])
        fft_samples_ref[0] = int(profile["fft_samples"])
        ui_sync_stride_ref[0] = int(profile["ui_sync_stride"])
        last_ui_sync_frame[0] = -int(ui_sync_stride_ref[0])
        freq_render_cache["signature"] = None

        short_label = {"fast": "Fast", "balanced": "Bal", "quality": "Qual"}.get(
            key, profile["label"]
        )
        btn_perf.label.set_text(f"Perf: {short_label}")

        if ani_ref[0] is not None:
            ani_ref[0].event_source.interval = 1000.0 / max(1, fps_ref[0])

        set_status_text(
            f"Performance: {profile['label']} (FPS={fps_ref[0]})",
            color="tab:green",
            redraw=False,
        )
        draw_frame(force_ui_sync=True)

    def cycle_performance_profile(event=None):
        order = ["fast", "balanced", "quality"]
        try:
            idx = order.index(perf_profile_key[0])
        except ValueError:
            idx = 0
        set_performance_profile(order[(idx + 1) % len(order)])

    def set_animation_enabled(enabled):
        animation_enabled[0] = bool(enabled)
        if animation_enabled[0]:
            btn_anim.label.set_text("Anim: On")
            if ani_ref[0] is not None:
                ani_ref[0].event_source.start()
            set_status_text("Animation enabled", color="tab:green", redraw=False)
        else:
            is_playing[0] = False
            btn_anim.label.set_text("Anim: Off")
            if ani_ref[0] is not None:
                ani_ref[0].event_source.stop()
            set_status_text("Animation disabled", color="tab:orange", redraw=False)
        fig.canvas.draw_idle()

    def set_axis_mode(mode):
        normalized = "freq" if str(mode).lower().startswith("f") else "time"
        if x_axis_mode[0] == normalized:
            return
        clear_probe()
        x_axis_mode[0] = normalized
        if normalized == "time":
            btn_mode.label.set_text("X: Time")
            ax.set_xlabel("Time (s)")
            ax.set_ylabel("Value (V)")
            set_status_text("Time mode", color="tab:green", redraw=False)
            update_display_window()
        else:
            btn_mode.label.set_text("X: Hz")
            ax.set_xlabel("Frequency (Hz)")
            ax.set_ylabel("Amplitude")
            set_status_text("Frequency mode (Hz)", color="tab:green", redraw=False)
        draw_frame(force_ui_sync=True)

    def toggle_axis_mode(event=None):
        if x_axis_mode[0] == "time":
            set_axis_mode("freq")
        else:
            set_axis_mode("time")

    def play(event):
        if not animation_enabled[0]:
            set_status_text("Enable animation first", color="tab:orange", redraw=False)
            return
        if current_frame[0] >= n - 1:
            jump_to_start()
        edge_anchor[0] = "none"
        is_playing[0] = True
        print("Playback")

    def stop(event):
        is_playing[0] = False
        print("Paused")

    def rewind(event):
        shift_frame(-STEP)
        print(f"Step back: frame {current_frame[0]}")

    def forward(event):
        shift_frame(STEP)
        print(f"Step forward: frame {current_frame[0]}")

    def toggle_animation(event=None):
        set_animation_enabled(not animation_enabled[0])

    btn_play.on_clicked(play)
    btn_stop.on_clicked(stop)
    btn_back.on_clicked(rewind)
    btn_forw.on_clicked(forward)
    btn_open.on_clicked(reload_with_new_file)
    btn_anim.on_clicked(toggle_animation)
    btn_mode.on_clicked(toggle_axis_mode)
    btn_probe.on_clicked(toggle_probe)
    btn_perf.on_clicked(cycle_performance_profile)
    clear_probe_fn = clear_probe

    # Time slider.
    ax_time_slider = plt.axes([0.1, 0.12, 0.7, 0.03])
    try:
        time_slider = Slider(
            ax_time_slider, "Timeline", 0.0, 1.0, valinit=0.0, dragging=False
        )
    except TypeError:
        time_slider = Slider(ax_time_slider, "Timeline", 0.0, 1.0, valinit=0.0)
    time_slider.valtext.set_visible(False)

    def on_time_slider(val):
        if n <= 1:
            return

        # Manual timeline interaction should always work and pause playback.
        if is_playing[0]:
            is_playing[0] = False
        target_frame = int(round(val * (n - 1)))
        frame_fraction = (
            float(target_frame) / float(n - 1) if n > 1 else 0.0
        )
        if frame_fraction <= 1e-6:
            new_anchor = "left"
        elif frame_fraction >= 1.0 - 1e-6:
            new_anchor = "right"
        else:
            new_anchor = "none"
        anchor_changed = edge_anchor[0] != new_anchor
        if (
            target_frame == current_frame[0]
            and target_frame == last_slider_frame[0]
            and not anchor_changed
        ):
            return
        edge_anchor[0] = new_anchor
        last_slider_frame[0] = target_frame
        slider_lock[0] = True
        current_frame[0] = target_frame
        if current_frame[0] < n:
            apply_window_position_for_timeline_fraction(
                get_timeline_fraction_from_frame()
            )
            update_display_window()
            draw_frame()
        slider_lock[0] = False

    time_slider.on_changed(on_time_slider)

    # Zoom slider.
    ax_zoom_slider = plt.axes([0.1, 0.06, 0.7, 0.03])
    zoom_slider = Slider(ax_zoom_slider, "Detail", 1, 100, valinit=50, valfmt="%d")
    zoom_slider.valtext.set_visible(False)
    zoom_slider.on_changed(update_zoom)

    # Direct timeline/zoom inputs (apply with Enter).
    text_input_lock = [False]
    last_time_box_value = [None]
    last_zoom_box_value = [None]

    ax_time_input = plt.axes([0.83, 0.12, 0.15, 0.04])
    ax_zoom_input = plt.axes([0.83, 0.06, 0.15, 0.04])
    time_input = TextBox(ax_time_input, "", initial="0.0")
    zoom_input = TextBox(ax_zoom_input, "", initial="20.0")
    ax_time_input.set_title("Position (%)", fontsize=8, pad=1, loc="left")
    ax_zoom_input.set_title("Window (%)", fontsize=8, pad=1, loc="left")

    def set_time_input_value(value):
        if n <= 1:
            position_percent = 0.0
        else:
            position_percent = float(value) / (n - 1) * 100.0
        rounded = round(position_percent, 3)
        if last_time_box_value[0] == rounded:
            return
        text_input_lock[0] = True
        time_input.set_val(f"{rounded:.3f}")
        text_input_lock[0] = False
        last_time_box_value[0] = rounded

    def set_zoom_input_value(value):
        if time_range_ref[0] > 0:
            window_percent = (window_size[0] / time_range_ref[0]) * 100.0
        else:
            window_percent = 0.0
        rounded = round(window_percent, 2)
        if last_zoom_box_value[0] == rounded:
            return
        text_input_lock[0] = True
        zoom_input.set_val(f"{rounded:.2f}")
        text_input_lock[0] = False
        last_zoom_box_value[0] = rounded

    def update_input_boxes():
        if 0 <= current_frame[0] < n:
            set_time_input_value(current_frame[0])
        set_zoom_input_value(zoom_level[0])

    def on_time_input_submit(text):
        if text_input_lock[0] or n <= 1:
            return
        candidate = text.strip().replace(",", ".")
        try:
            target_position_percent = float(candidate)
        except ValueError:
            set_status_text("Invalid position value", color="tab:red", redraw=True)
            update_input_boxes()
            return

        target_position_percent = min(100.0, max(0.0, target_position_percent))
        time_slider.set_val(target_position_percent / 100.0)
        update_input_boxes()
        set_status_text("Ready", color="tab:green", redraw=False)

    def on_zoom_input_submit(text):
        if text_input_lock[0]:
            return
        candidate = text.strip().replace(",", ".")
        try:
            target_window_percent = float(candidate)
        except ValueError:
            set_status_text("Invalid window value", color="tab:red", redraw=True)
            update_input_boxes()
            return

        target_window_percent = min(100.0, max(min_zoom_scale * 100.0, target_window_percent))
        target_zoom = scale_factor_to_zoom(target_window_percent / 100.0)
        zoom_slider.set_val(target_zoom)
        update_input_boxes()
        set_status_text("Ready", color="tab:green", redraw=False)

    time_input.on_submit(on_time_input_submit)
    zoom_input.on_submit(on_zoom_input_submit)

    # Keyboard handling.
    def on_key_press(event):
        # Do not trigger global hotkeys while user edits timeline/zoom inputs.
        if event.inaxes in (ax_time_input, ax_zoom_input):
            return

        if event.key == " ":
            if not animation_enabled[0]:
                set_status_text("Enable animation first", color="tab:orange", redraw=False)
                return
            if current_frame[0] >= n - 1:
                jump_to_start()
            is_playing[0] = not is_playing[0]
            print("Playback" if is_playing[0] else "Paused")
        elif event.key == "left":
            shift_frame(-STEP)
            print(f"Step back: frame {current_frame[0]}")
        elif event.key == "right":
            shift_frame(STEP)
            print(f"Step forward: frame {current_frame[0]}")
        elif event.key == "home":
            jump_to_start()
            print("Jumped to start")
        elif event.key == "end":
            jump_to_end()
            print("Jumped to end")
        elif event.key == "up":
            new_zoom = min(100, zoom_level[0] + 5)
            zoom_slider.set_val(new_zoom)
        elif event.key == "down":
            new_zoom = max(1, zoom_level[0] - 5)
            zoom_slider.set_val(new_zoom)
        elif event.key == "a":
            toggle_animation()
        elif event.key == "m":
            toggle_axis_mode()
        elif event.key == "p":
            cycle_performance_profile()
        elif event.key == "v":
            toggle_probe()
        elif event.key == "escape":
            clear_probe()
        elif event.key in ("ctrl+o", "cmd+o"):
            reload_with_new_file()

    fig.canvas.mpl_connect("button_press_event", on_probe_click)
    fig.canvas.mpl_connect("key_press_event", on_key_press)

    # Data and control info.
    update_info_text()
    controls_text = "\n".join(
        [
            "Controls: Space - pause/play, Left/Right - seek, Up/Down - detail, Home/End - start/end",
            "A - animation on/off, M - time/Hz mode, P - performance profile, V - probe on/off, Esc - clear probe",
            "Ctrl+O/Cmd+O - open file, Channels panel - toggle visibility, Position/Window - Enter",
        ]
    )
    plt.figtext(0.05, 0.915, controls_text, fontsize=8.2, ha="left", style="italic")

    ani_ref[0] = FuncAnimation(
        fig, update, interval=1000 / max(1, fps_ref[0]), blit=False, cache_frame_data=False
    )
    set_performance_profile(DEFAULT_PERF_PROFILE)
    set_animation_enabled(ANIMATION_DEFAULT_ENABLED)
    update_zoom(50)
    draw_frame()
    set_status_text("Ready", color="tab:green", redraw=True)

    plt.gcf().canvas.manager.set_window_title(f"LVM Data Viewer - {os.path.basename(FILE)}")
    plt.show()


if __name__ == "__main__":
    main()
