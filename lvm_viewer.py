import os
import sys
import tkinter as tk
from tkinter import filedialog

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button, Slider

# GENERAL SETTINGS
FILE = ""  # File is selected through a dialog
FPS = 60  # Values above 100 are usually not recommended
STEP = 20  # Seek step
INITIAL_WINDOW_SIZE = 0.2  # Initial view window size (20% of full time range)
update_zoom_fn = None
draw_frame_fn = None


# FILE SELECTION
def select_file(exit_on_cancel=True):
    """Open a file selection dialog."""
    root = tk.Tk()
    root.withdraw()  # Hide root window
    root.attributes("-topmost", True)  # Keep dialog above other windows

    file_path = filedialog.askopenfilename(
        title="Select an LVM file to analyze",
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


# LVM FILE READING
def read_lvm_file(file_path):
    print(f"Reading LVM file: {os.path.basename(file_path)}")

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.readlines()
    except Exception as e:
        print(f"File read error: {e}")
        return pd.DataFrame()

    # Find all header terminators.
    header_ends = []
    for i, line in enumerate(content):
        if "***End_of_Header***" in line:
            header_ends.append(i)

    if header_ends:
        print(
            f"Header end markers found: {len(header_ends)} "
            f"(first: {header_ends[0]}, last: {header_ends[-1]})"
        )
    else:
        print("Header end markers found: 0")

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

    def is_metadata_line(line):
        first_cell = line.split("\t", 1)[0].strip()
        return first_cell in metadata_keys

    # Build parse windows after each header end marker.
    if header_ends:
        windows = []
        for i, header_end in enumerate(header_ends):
            start = header_end + 1
            end = header_ends[i + 1] if i + 1 < len(header_ends) else len(content)
            windows.append((start, end))
    else:
        windows = [(0, len(content))]

    # Collect all data rows from all windows.
    data_lines = []
    section_hits = 0
    for section_idx, (start, end) in enumerate(windows, start=1):
        found_data_in_section = False

        for line_index in range(start, end):
            line = content[line_index].strip()
            if not line or line.startswith("***") or is_metadata_line(line):
                continue

            # Normalize decimal commas and split by tabs.
            line_clean = line.replace(",", ".")
            parts = line_clean.split("\t")
            parts = [p.strip() for p in parts if p.strip()]

            # Keep only numeric values.
            numeric_parts = []
            for part in parts:
                try:
                    num = float(part)
                    numeric_parts.append(num)
                except ValueError:
                    continue

            # Minimum expected shape: time + one value.
            if len(numeric_parts) >= 2:
                if not found_data_in_section:
                    print(
                        f"Numeric data found in section {section_idx} at line {line_index}: "
                        f"{numeric_parts[:2]}..."
                    )
                    found_data_in_section = True
                    section_hits += 1
                data_lines.append(numeric_parts)

    print(f"Sections with numeric data: {section_hits}")

    print(f"Collected {len(data_lines)} data rows")

    if not data_lines:
        print("No numeric data found")
        return pd.DataFrame()

    # Build a DataFrame from collected rows.
    max_cols = max(len(row) for row in data_lines)
    print(f"Maximum column count: {max_cols}")

    all_data = []
    for i in range(max_cols):
        column_data = []
        for row in data_lines:
            if i < len(row):
                column_data.append(row[i])
            else:
                column_data.append(np.nan)
        all_data.append(column_data)

    data_dict = {"Time": all_data[0]}  # First column is time.
    for i in range(1, len(all_data)):
        if not all(np.isnan(x) for x in all_data[i]):
            data_dict[f"Channel_{i}"] = all_data[i]

    df = pd.DataFrame(data_dict)
    df = df.dropna(subset=["Time"])

    print(f"DataFrame created with {len(df)} rows and {len(df.columns)} columns")
    print(f"Columns: {list(df.columns)}")
    return df


def prepare_loaded_data(df):
    """Normalize loaded data and validate minimum structure."""
    if df.empty:
        return None

    prepared = df.copy()
    prepared["Time"] = pd.to_numeric(prepared["Time"], errors="coerce")
    prepared = prepared.dropna(subset=["Time"])
    if prepared.empty:
        print("No valid numeric timestamps after parsing.")
        return None

    time_values = prepared["Time"].to_numpy()
    channel_frame = prepared.drop(columns=["Time"])
    if len(channel_frame.columns) == 0:
        print("No data channels available for display.")
        return None

    return prepared, time_values, channel_frame, len(prepared)


# RELOAD DATA WITH A NEW FILE
def reload_with_new_file(event=None):
    """Reload viewer data from a newly selected file."""
    global FILE, df, time, channels, n, current_frame, is_playing, current_center

    new_file = select_file(exit_on_cancel=False)
    if not new_file:
        return

    FILE = new_file
    print(f"Loading new file: {FILE}")

    new_df = read_lvm_file(FILE)
    prepared = prepare_loaded_data(new_df)
    if prepared is None:
        print("Failed to prepare data from the new file.")
        return

    df, time, channels, n = prepared
    print(f"Loaded {len(channels.columns)} channels, {n} samples")
    print(f"Time range: {time[0]} - {time[-1]}")

    # Reset playback state.
    current_frame[0] = 0
    is_playing[0] = True
    current_center[0] = time[0] + (time[-1] - time[0]) * INITIAL_WINDOW_SIZE * 0.8

    # Refresh plot and labels.
    update_plot_data()
    if callable(update_zoom_fn):
        update_zoom_fn(zoom_level[0])
    if callable(draw_frame_fn):
        draw_frame_fn()
    update_info_text()


def update_plot_data():
    """Refresh plotted data after file switch."""
    global lines, ax

    for line in lines:
        line.remove()
    lines = []

    for c in channels.columns:
        line, = ax.plot([], [], label=c, linewidth=1)
        lines.append(line)

    ax.legend(loc="upper right")

    y_min = channels.min().min()
    y_max = channels.max().max()
    y_range = y_max - y_min
    if y_range == 0:
        y_range = 1
    y_margin = y_range * 0.1
    ax.set_ylim(y_min - y_margin, y_max + y_margin)


def update_info_text():
    """Update informational labels."""
    global info_text_obj, controls_text_obj, file_info_obj

    if "info_text_obj" in globals():
        info_text_obj.remove()
    if "file_info_obj" in globals():
        file_info_obj.remove()

    info_text = (
        f"Channels: {len(channels.columns)} | "
        f"Samples: {n} | "
        f"Duration: {time[-1] - time[0]:.3f}s | "
        f"Zoom: {zoom_level[0]}%"
    )
    info_text_obj = plt.figtext(0.05, 0.95, info_text, fontsize=10, ha="left")

    file_info = f"File: {os.path.basename(FILE)}"
    file_info_obj = plt.figtext(0.05, 0.98, file_info, fontsize=10, ha="left", weight="bold")


# MAIN PROGRAM
def main():
    global FILE, df, time, channels, n, lines, ax, fig, update_zoom_fn, draw_frame_fn
    global current_frame, is_playing, current_center, zoom_level
    global info_text_obj, controls_text_obj, file_info_obj

    FILE = select_file()

    raw_df = read_lvm_file(FILE)
    prepared = prepare_loaded_data(raw_df)
    if prepared is None:
        print("Failed to prepare data from file.")
        sys.exit()

    df, time, channels, n = prepared
    print(f"Loaded {len(channels.columns)} channels, {n} samples")
    print(f"Time range: {time[0]} - {time[-1]}")

    fig, ax = plt.subplots(figsize=(14, 8))
    lines = [ax.plot([], [], label=c, linewidth=1)[0] for c in channels.columns]

    time_range = time[-1] - time[0]
    if time_range == 0:
        time_range = 1

    # Global playback state.
    current_frame = [0]
    is_playing = [True]
    slider_lock = [False]
    window_size = [time_range * INITIAL_WINDOW_SIZE]
    zoom_level = [50]

    # Initial window center.
    initial_center = time[0] + window_size[0] * 0.8
    current_center = [initial_center]

    def update_zoom(val):
        zoom_level[0] = val
        min_zoom = 0.01
        max_zoom = 1.0
        exponent = 3.0
        normalized_val = zoom_level[0] / 100.0
        scale_factor = min_zoom + (max_zoom - min_zoom) * (normalized_val ** exponent)
        window_size[0] = time_range * scale_factor
        update_display_window()
        draw_frame()

    def update_display_window():
        half_window = window_size[0] / 2
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

        ax.set_xlim(window_start, window_end)

    y_min = channels.min().min()
    y_max = channels.max().max()
    y_range = y_max - y_min
    if y_range == 0:
        y_range = 1
    y_margin = y_range * 0.1
    ax.set_ylim(y_min - y_margin, y_max + y_margin)

    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Value (V)")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)
    plt.subplots_adjust(bottom=0.3)

    def draw_frame():
        if n == 0:
            return

        start_idx = max(0, np.searchsorted(time, ax.get_xlim()[0]) - 10)
        end_idx = min(n, np.searchsorted(time, ax.get_xlim()[1]) + 10)

        for i, c in enumerate(channels.columns):
            lines[i].set_data(time[start_idx:end_idx], channels[c].iloc[start_idx:end_idx])

        if not slider_lock[0] and n > 1:
            old_val = time_slider.val
            new_val = current_frame[0] / (n - 1)
            if abs(old_val - new_val) > 1e-6:
                time_slider.eventson = False
                time_slider.set_val(new_val)
                time_slider.eventson = True

        fig.canvas.draw_idle()

    update_zoom_fn = update_zoom
    draw_frame_fn = draw_frame

    def update(_):
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

    btn_back = Button(ax_back, "Back")
    btn_play = Button(ax_play, "Play")
    btn_stop = Button(ax_stop, "Pause")
    btn_forw = Button(ax_forw, "Forward")
    btn_open = Button(ax_open, "Open")

    def play(event):
        if current_frame[0] >= n - 1:
            current_frame[0] = 0
            current_center[0] = time[0] + window_size[0] * 0.8
            update_display_window()
            draw_frame()
        is_playing[0] = True
        print("Playback")

    def stop(event):
        is_playing[0] = False
        print("Paused")

    def rewind(event):
        is_playing[0] = False
        current_frame[0] = max(0, current_frame[0] - STEP)
        if current_frame[0] < n:
            current_time = time[current_frame[0]]
            current_center[0] = current_time + window_size[0] * 0.3
            update_display_window()
        draw_frame()
        print(f"Step back: frame {current_frame[0]}")

    def forward(event):
        is_playing[0] = False
        current_frame[0] = min(n - 1, current_frame[0] + STEP)
        if current_frame[0] < n:
            current_time = time[current_frame[0]]
            current_center[0] = current_time + window_size[0] * 0.3
            update_display_window()
        draw_frame()
        print(f"Step forward: frame {current_frame[0]}")

    btn_play.on_clicked(play)
    btn_stop.on_clicked(stop)
    btn_back.on_clicked(rewind)
    btn_forw.on_clicked(forward)
    btn_open.on_clicked(reload_with_new_file)

    # Time slider.
    ax_time_slider = plt.axes([0.1, 0.12, 0.7, 0.03])
    time_slider = Slider(ax_time_slider, "Time", 0.0, 1.0, valinit=0.0)

    def on_time_slider(val):
        if is_playing[0] or n <= 1:
            return
        slider_lock[0] = True
        current_frame[0] = int(val * (n - 1))
        if current_frame[0] < n:
            current_time = time[current_frame[0]]
            current_center[0] = current_time + window_size[0] * 0.3
            update_display_window()
            draw_frame()
        slider_lock[0] = False

    time_slider.on_changed(on_time_slider)

    # Zoom slider.
    ax_zoom_slider = plt.axes([0.1, 0.06, 0.7, 0.03])
    zoom_slider = Slider(ax_zoom_slider, "Zoom", 1, 100, valinit=50, valfmt="%d%%")
    zoom_slider.on_changed(update_zoom)

    # Keyboard handling.
    def on_key_press(event):
        if event.key == " ":
            if current_frame[0] >= n - 1:
                current_frame[0] = 0
                current_center[0] = time[0] + window_size[0] * 0.8
                update_display_window()
                draw_frame()
            is_playing[0] = not is_playing[0]
            print("Playback" if is_playing[0] else "Paused")
        elif event.key == "left":
            is_playing[0] = False
            current_frame[0] = max(0, current_frame[0] - STEP)
            if current_frame[0] < n:
                current_time = time[current_frame[0]]
                current_center[0] = current_time + window_size[0] * 0.3
                update_display_window()
            draw_frame()
            print(f"Step back: frame {current_frame[0]}")
        elif event.key == "right":
            is_playing[0] = False
            current_frame[0] = min(n - 1, current_frame[0] + STEP)
            if current_frame[0] < n:
                current_time = time[current_frame[0]]
                current_center[0] = current_time + window_size[0] * 0.3
                update_display_window()
            draw_frame()
            print(f"Step forward: frame {current_frame[0]}")
        elif event.key == "home":
            is_playing[0] = False
            current_frame[0] = 0
            current_center[0] = time[0] + window_size[0] * 0.8
            update_display_window()
            draw_frame()
            print("Jumped to start")
        elif event.key == "end":
            is_playing[0] = False
            current_frame[0] = n - 1
            current_center[0] = time[-1] - window_size[0] * 0.5
            update_display_window()
            draw_frame()
            print("Jumped to end")
        elif event.key == "up":
            new_zoom = min(100, zoom_level[0] + 5)
            zoom_slider.set_val(new_zoom)
        elif event.key == "down":
            new_zoom = max(1, zoom_level[0] - 5)
            zoom_slider.set_val(new_zoom)
        elif event.key in ("ctrl+o", "cmd+o"):
            reload_with_new_file()

    fig.canvas.mpl_connect("key_press_event", on_key_press)

    # Data and control info.
    update_info_text()
    controls_text = (
        "Controls: Space - pause/play, Left/Right - seek, Up/Down - zoom, "
        "Home/End - start/end, Ctrl+O/Cmd+O - open file"
    )
    controls_text_obj = plt.figtext(0.05, 0.92, controls_text, fontsize=9, ha="left", style="italic")

    ani = FuncAnimation(fig, update, interval=1000 / FPS, blit=False, cache_frame_data=False)
    update_zoom(50)
    draw_frame()

    plt.gcf().canvas.manager.set_window_title(f"LVM Data Viewer - {os.path.basename(FILE)}")
    plt.show()


if __name__ == "__main__":
    main()
