import pandas as pd
import pytest

from carbon_scheduler.ingest.store import read_hourly, write_hourly


def test_write_read_roundtrip_preserves_index_tz_and_dtypes(tmp_path):
    frame = pd.DataFrame(
        {"demand_mwh": [1.0, float("nan")]},
        index=pd.date_range("2024-01-01", periods=2, freq="h", tz="UTC", name="period").astype(
            "datetime64[ns, UTC]"
        ),
    )
    path = write_hourly(frame, "CISO", "interim", tmp_path)
    original = path.read_bytes()
    pd.testing.assert_frame_equal(read_hourly("CISO", "interim", tmp_path), frame, check_freq=False)
    write_hourly(frame, "CISO", "interim", tmp_path)
    assert path.read_bytes() == original


def test_invalid_stage_and_region_rejected(tmp_path):
    with pytest.raises(ValueError):
        read_hourly("CISO", "bad", tmp_path)
    with pytest.raises(ValueError):
        read_hourly("../CISO", "interim", tmp_path)


def test_missing_store_explains_ingest(tmp_path):
    with pytest.raises(FileNotFoundError, match="ingest"):
        read_hourly("CISO", "interim", tmp_path)


def test_naive_index_rejected(tmp_path):
    frame = pd.DataFrame({"value": [1.0]}, index=pd.date_range("2024-01-01", periods=1))
    with pytest.raises(ValueError, match="UTC"):
        write_hourly(frame, "CISO", "raw", tmp_path)
