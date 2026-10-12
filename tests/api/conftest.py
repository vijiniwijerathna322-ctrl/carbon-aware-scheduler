"""Real small artifact integration and immutable snapshot contract."""

import numpy as np
import pandas as pd
import pytest

from carbon_scheduler.config import Settings
from carbon_scheduler.ingest.store import write_hourly
from carbon_scheduler.models.training import train_region


@pytest.fixture(scope="module")
def trained_settings(tmp_path_factory):
    root = tmp_path_factory.mktemp("api-models")
    index = pd.date_range(
        "2024-01-01", periods=150 * 24, freq="h", tz="UTC", name="period"
    ).as_unit("ns")
    hours = np.arange(len(index))
    frame = pd.DataFrame(
        {
            "demand_mwh": 100.0 + hours % 24,
            "gen_ng_mwh": 50.0 + hours % 24,
            "gen_sun_mwh": np.maximum(np.sin(hours / 24 * 2 * np.pi), 0) * 20,
        },
        index=index,
    )
    settings = Settings(
        _env_file=None, data_dir=root / "data", models_dir=root / "models", demo_mode=True
    )
    write_hourly(frame, "CISO", "raw", settings.data_dir)
    train_region("CISO", settings, lgbm_params={"n_estimators": 5})
    # Snapshot tails can differ by target; the carbon model retains its fit_end.
    extra = frame.iloc[-2:].copy()
    extra.index = extra.index + pd.Timedelta(hours=2)
    extra.loc[extra.index[-1], ["gen_ng_mwh", "gen_sun_mwh"]] = np.nan
    write_hourly(pd.concat([frame, extra]), "CISO", "raw", settings.data_dir)
    return settings
