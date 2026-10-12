import json
from unittest.mock import Mock

import pandas as pd
import pytest
from typer.testing import CliRunner

from carbon_scheduler.cli import app
from carbon_scheduler.config import Settings
from carbon_scheduler.ingest.pipeline import run_ingest
from carbon_scheduler.ingest.store import read_hourly
from carbon_scheduler.ingest.validate import QualityReport


def client_with_data():
    client = Mock()

    def fetch(route, *, start, end, **kwargs):
        hours = pd.date_range(start, end, freq="h")
        category = "type" if route.endswith("region-data") else "fueltype"
        codes = ["D", "DF", "NG", "TI"] if category == "type" else ["SUN"]
        return [
            {"period": hour.strftime("%Y-%m-%dT%H"), category: code, "value": "100"}
            for hour in hours
            for code in codes
        ]

    client.fetch_route.side_effect = fetch
    return client


def settings(tmp_path):
    return Settings(_env_file=None, data_dir=tmp_path, eia_api_key=None)


def test_ingest_is_idempotent(tmp_path):
    client = client_with_data()
    config = settings(tmp_path)
    run_ingest("CISO", "2024-01-01T00", "2024-01-04T00", config, client)
    path = tmp_path / "interim/CISO/hourly.parquet"
    before = path.read_bytes()
    raw_path = tmp_path / "raw/CISO/hourly.parquet"
    raw_before = raw_path.read_bytes()
    report_path = tmp_path / "interim/CISO/quality-report.json"
    report_before = report_path.read_bytes()
    original = read_hourly("CISO", "interim", tmp_path)
    run_ingest("CISO", "2024-01-01T00", "2024-01-04T00", config, client)
    assert path.read_bytes() == before
    assert raw_path.read_bytes() == raw_before
    assert report_path.read_bytes() == report_before
    assert not (tmp_path / "processed").exists()
    pd.testing.assert_frame_equal(original, read_hourly("CISO", "interim", tmp_path))
    assert client.fetch_route.call_args.kwargs["start"] == "2024-01-02T00"
    client.close.assert_not_called()


def test_revision_null_replaces_and_old_fuel_columns_retained(tmp_path):
    client = client_with_data()
    config = settings(tmp_path)
    run_ingest("CISO", "2024-01-01T00", "2024-01-04T00", config, client)
    fetch = client.fetch_route.side_effect

    def revised(route, **kwargs):
        rows = fetch(route, **kwargs)
        if route.endswith("region-data"):
            rows.append({"period": "2024-01-04T00", "type": "D", "value": None})
        else:
            for row in rows:
                row["fueltype"] = "WND"
        return rows

    client.fetch_route.side_effect = revised
    report = run_ingest("CISO", "2024-01-01T00", "2024-01-04T00", config, client)
    frame = read_hourly("CISO", "raw", tmp_path)
    assert pd.isna(frame.iloc[-1]["demand_mwh"])
    assert pd.isna(frame.iloc[-1]["gen_sun_mwh"])
    assert frame.iloc[0]["gen_sun_mwh"] == 100  # noqa: PLR2004
    assert "gen_wnd_mwh" in frame
    assert report.n_duplicates == 1


def test_backfill_and_historical_end_preserve_existing(tmp_path):
    config = settings(tmp_path)
    client = client_with_data()
    run_ingest("CISO", "2024-01-02T00", "2024-01-04T00", config, client)
    run_ingest("CISO", "2024-01-01T00", "2024-01-02T00", config, client)
    assert client.fetch_route.call_args.kwargs["start"] == "2024-01-01T00"
    frame = read_hourly("CISO", "raw", tmp_path)
    assert frame.index.min() == pd.Timestamp("2024-01-01", tz="UTC")
    assert frame.index.max() == pd.Timestamp("2024-01-04", tz="UTC")


def test_empty_api_requested_bounds_are_missing(tmp_path):
    client = Mock()
    client.fetch_route.return_value = []
    report = run_ingest("CISO", "2024-01-01T00", "2024-01-02T00", settings(tmp_path), client)
    assert report.n_rows == 25  # noqa: PLR2004
    assert report.gap_fraction == 1
    persisted = json.loads((tmp_path / "interim/CISO/quality-report.json").read_text())
    assert persisted["g2_pass"] is False


def test_invalid_bounds(tmp_path):
    with pytest.raises(ValueError, match="start"):
        run_ingest("CISO", "2024-01-02T00", "2024-01-01T00", settings(tmp_path), Mock())


def test_fetch_partitions_calendar_year_without_duplicate_boundary(tmp_path):
    client = client_with_data()
    report = run_ingest("CISO", "2023-12-31T23", "2024-01-01T01", settings(tmp_path), client)
    for route in ("electricity/rto/region-data", "electricity/rto/fuel-type-data"):
        windows = [
            (call.kwargs["start"], call.kwargs["end"])
            for call in client.fetch_route.call_args_list
            if call.args[0] == route
        ]
        assert windows == [
            ("2023-12-31T23", "2023-12-31T23"),
            ("2024-01-01T00", "2024-01-01T01"),
        ]
    assert report.n_rows == 3  # noqa: PLR2004
    assert report.n_duplicates == 0
    assert report.gap_fraction == 0


def test_completed_year_checkpoint_resumes_after_later_failure(tmp_path):
    client = client_with_data()
    fetch = client.fetch_route.side_effect

    def fail_later_year(route, **kwargs):
        if kwargs["start"] == "2024-01-01T00":
            raise RuntimeError("temporary upstream failure")
        return fetch(route, **kwargs)

    client.fetch_route.side_effect = fail_later_year
    with pytest.raises(RuntimeError, match="upstream"):
        run_ingest("CISO", "2023-12-28T00", "2024-01-01T01", settings(tmp_path), client)
    raw = read_hourly("CISO", "raw", tmp_path)
    assert raw.index.max() == pd.Timestamp("2023-12-31T23", tz="UTC")
    assert not (tmp_path / "interim").exists()
    resumed = client_with_data()
    run_ingest("CISO", "2023-12-28T00", "2024-01-01T01", settings(tmp_path), resumed)
    assert resumed.fetch_route.call_args_list[0].kwargs["start"] == "2023-12-29T23"
    assert read_hourly("CISO", "interim", tmp_path).index.min() == raw.index.min()


def test_failed_fuel_route_does_not_checkpoint_half_year(tmp_path):
    client = client_with_data()
    fetch = client.fetch_route.side_effect

    def fail_fuel(route, **kwargs):
        if route.endswith("fuel-type-data"):
            raise RuntimeError("fuel unavailable")
        return fetch(route, **kwargs)

    client.fetch_route.side_effect = fail_fuel
    with pytest.raises(RuntimeError, match="fuel unavailable"):
        run_ingest("CISO", "2023-12-31T23", "2024-01-01T01", settings(tmp_path), client)
    assert not (tmp_path / "raw").exists()
    assert not (tmp_path / "interim").exists()


def test_failed_backfill_preserves_original_cache_and_retry_prefix(tmp_path):
    config = settings(tmp_path)
    run_ingest("CISO", "2024-01-01T00", "2024-01-02T00", config, client_with_data())
    raw_path = tmp_path / "raw/CISO/hourly.parquet"
    original = raw_path.read_bytes()
    client = client_with_data()
    fetch = client.fetch_route.side_effect

    def fail_second_year(route, **kwargs):
        if kwargs["start"] == "2024-01-01T00":
            raise RuntimeError("backfill interrupted")
        return fetch(route, **kwargs)

    client.fetch_route.side_effect = fail_second_year
    with pytest.raises(RuntimeError, match="backfill interrupted"):
        run_ingest("CISO", "2023-12-30T00", "2024-01-02T00", config, client)
    assert raw_path.read_bytes() == original
    resumed = client_with_data()
    run_ingest("CISO", "2023-12-30T00", "2024-01-02T00", config, resumed)
    assert resumed.fetch_route.call_args_list[0].kwargs["start"] == "2023-12-30T00"
    assert read_hourly("CISO", "raw", tmp_path).index.min() == pd.Timestamp(
        "2023-12-30T00", tz="UTC"
    )


def test_cli_ingest_without_key_fails_with_clear_message(monkeypatch, tmp_path):
    monkeypatch.delenv("EIA_API_KEY", raising=False)
    monkeypatch.setattr("carbon_scheduler.cli.get_settings", lambda: settings(tmp_path))
    result = CliRunner().invoke(app, ["ingest", "--end", "2021-01-02T00"])
    assert result.exit_code == 1
    assert "EIA_API_KEY" in result.output
    assert "Traceback" not in result.output


def test_cli_quality_failure_is_nonzero(monkeypatch):
    report = QualityReport(1, 0, 0, 0, 1, 1.0)
    monkeypatch.setattr("carbon_scheduler.cli.run_ingest", lambda *args: report)
    result = CliRunner().invoke(app, ["ingest"])
    assert result.exit_code == 2  # noqa: PLR2004
    assert "G2: FAIL" in result.output
