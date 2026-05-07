import os
from pathlib import Path
import uuid

import numpy as np

os.environ.setdefault("MPLBACKEND", "Agg")

import lvm_viewer as viewer


ROOT_DIR = Path(__file__).resolve().parents[1]
SAMPLES_DIR = ROOT_DIR / "lvm_files_for_tests"


def test_read_lvm_file_from_sample():
    sample_path = SAMPLES_DIR / "test.lvm"
    df = viewer.read_lvm_file(str(sample_path))

    assert not df.empty
    assert "Time" in df.columns
    assert len(df.columns) >= 2


def test_prepare_and_range_selection():
    sample_path = SAMPLES_DIR / "test.lvm"
    df = viewer.read_lvm_file(str(sample_path))
    prepared = viewer.prepare_loaded_data(df)

    assert prepared is not None
    prepared_df, time_values, channels, count = prepared
    assert count == len(prepared_df)
    assert len(time_values) == count
    assert len(channels) == count
    assert len(channels.columns) >= 1

    start = float(time_values[count // 4])
    end = float(time_values[count // 2])
    subset = viewer.apply_processing_range(prepared, start, end)
    assert subset is not None

    _, subset_time, subset_channels, subset_count = subset
    assert subset_count == len(subset_time)
    assert subset_count == len(subset_channels)
    assert float(subset_time[0]) >= start - 1e-12
    assert float(subset_time[-1]) <= end + 1e-12


def test_parser_preserves_column_alignment_with_missing_cell():
    sample_content = "\n".join(
        [
            "LabVIEW Measurement",
            "Writer_Version\t2",
            "Reader_Version\t2",
            "Separator\tTab",
            "Decimal_Separator\t.",
            "***End_of_Header***",
            "Time\tA\tB",
            "0.0\t1.0\t10.0",
            "0.1\t\t20.0",
        ]
    )
    tmp_dir = ROOT_DIR / "tests" / "_tmp"
    tmp_dir.mkdir(exist_ok=True)
    lvm_path = tmp_dir / f"missing_middle_value_{uuid.uuid4().hex}.lvm"
    try:
        lvm_path.write_text(sample_content, encoding="utf-8")
        df = viewer.read_lvm_file(str(lvm_path))

        assert list(df.columns) == ["Time", "Channel_1", "Channel_2"]
        assert len(df) == 2
        assert np.isnan(float(df.loc[1, "Channel_1"]))
        assert float(df.loc[1, "Channel_2"]) == 20.0
    finally:
        if lvm_path.exists():
            try:
                lvm_path.unlink()
            except OSError:
                pass


def test_cli_file_argument_validation():
    sample_path = (SAMPLES_DIR / "test.lvm").resolve()
    resolved, message = viewer.parse_cli_file_argument(
        ["lvm_viewer.py", str(sample_path)]
    )
    assert resolved == str(sample_path)
    assert message is None

    resolved, message = viewer.parse_cli_file_argument(["lvm_viewer.py", "--help"])
    assert resolved is None
    assert message == "help"

    resolved, message = viewer.parse_cli_file_argument(
        ["lvm_viewer.py", "missing_file.lvm"]
    )
    assert resolved is None
    assert message is not None
