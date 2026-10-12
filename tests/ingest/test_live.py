"""Explicit opt-in: downloads full history into an isolated temporary directory."""

import pytest

from carbon_scheduler.config import Settings
from carbon_scheduler.ingest.pipeline import G2_MAX_GAP_FRACTION, run_ingest


@pytest.mark.live
def test_full_history_g2(tmp_path):
    settings = Settings(data_dir=tmp_path)
    report = run_ingest("CISO", "2021-01-01T00", None, settings)
    assert report.n_rows > 0
    assert report.gap_fraction < G2_MAX_GAP_FRACTION
