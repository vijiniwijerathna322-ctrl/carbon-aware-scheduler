import json
from pathlib import Path

import pandas as pd
import pytest

from carbon_scheduler.ingest.store import write_hourly
from carbon_scheduler.models import registry


def _frame(value):
    return pd.DataFrame(
        {"demand_mwh": [value]},
        index=pd.date_range("2024-01-01", periods=1, freq="h", tz="UTC", name="period").astype(
            "datetime64[ns, UTC]"
        ),
    )


def test_failed_write_leaves_previous_file_intact(tmp_path, monkeypatch):
    path = write_hourly(_frame(1.0), "CISO", "raw", tmp_path)
    previous = path.read_bytes()

    def interrupted_write(self, destination, **kwargs):
        Path(destination).write_bytes(b"partial parquet")
        raise OSError("disk write interrupted")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", interrupted_write)
    with pytest.raises(OSError, match="interrupted"):
        write_hourly(_frame(2.0), "CISO", "raw", tmp_path)
    assert path.read_bytes() == previous
    assert list(path.parent.iterdir()) == [path]


def test_no_temp_files_left_after_success(tmp_path):
    path = write_hourly(_frame(1.0), "CISO", "raw", tmp_path)
    replacement = _frame(2.0)
    write_hourly(replacement, "CISO", "raw", tmp_path)
    pd.testing.assert_frame_equal(pd.read_parquet(path), replacement, check_freq=False)
    assert list(path.parent.iterdir()) == [path]


@pytest.mark.parametrize("operation", ["store", "pointer"])
def test_failed_replace_preserves_previous_file_and_cleans_temp(tmp_path, monkeypatch, operation):
    if operation == "store":
        path = write_hourly(_frame(1.0), "CISO", "raw", tmp_path)
    else:
        path = tmp_path / "current.json"
        registry._atomic_json(path, {"version": "previous"})
    previous = path.read_bytes()

    def failed_replace(source, destination):
        assert Path(source).is_file()
        assert Path(destination).read_bytes() == previous
        raise OSError("replace interrupted")

    monkeypatch.setattr(registry.os, "replace", failed_replace)
    with pytest.raises(OSError, match="interrupted"):
        if operation == "store":
            write_hourly(_frame(2.0), "CISO", "raw", tmp_path)
        else:
            registry._atomic_json(path, {"version": "candidate"})
    assert path.read_bytes() == previous
    assert list(path.parent.iterdir()) == [path]


def test_pointer_success_leaves_no_temp_files(tmp_path):
    path = tmp_path / "current.json"
    registry._atomic_json(path, {"version": "previous"})
    registry._atomic_json(path, {"version": "candidate"})
    assert json.loads(path.read_text(encoding="utf-8")) == {"version": "candidate"}
    assert list(tmp_path.iterdir()) == [path]


def test_interrupted_pointer_write_preserves_previous_file(tmp_path, monkeypatch):
    path = tmp_path / "current.json"
    registry._atomic_json(path, {"version": "previous"})
    previous = path.read_bytes()

    def interrupted_write(destination, content, **kwargs):
        destination.write_bytes(b"partial json")
        raise OSError("pointer write interrupted")

    monkeypatch.setattr(Path, "write_text", interrupted_write)
    with pytest.raises(OSError, match="interrupted"):
        registry._atomic_json(path, {"version": "candidate"})
    assert path.read_bytes() == previous
    assert list(tmp_path.iterdir()) == [path]
