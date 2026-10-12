# ruff: noqa: PLR2004
import json

import numpy as np
import pandas as pd
import pytest

from carbon_scheduler.models.forecast_model import ForecastModel
from carbon_scheduler.models.registry import (
    ModelIncompatibleError,
    ModelNotFoundError,
    load_model,
    read_metadata,
    save_model,
)


@pytest.fixture(scope="module")
def fitted():
    data = pd.Series(
        100 + np.arange(150 * 24) % 24,
        index=pd.date_range("2024-01-01", periods=150 * 24, freq="h", tz="UTC"),
    )
    model = ForecastModel("demand_mwh", "UTC", lgbm_params={"n_estimators": 10})
    model.fit(data, data.index[-1])
    return model, data


def test_roundtrip_and_spec_metadata(fitted, tmp_path):
    model, data = fitted
    saved = save_model(model, "CISO", tmp_path)
    loaded = load_model("CISO", "demand_mwh", tmp_path)
    pd.testing.assert_frame_equal(
        model.predict(data, data.index[-1]), loaded.predict(data, data.index[-1])
    )
    metadata = read_metadata("CISO", "demand_mwh", tmp_path)
    for key in (
        "region",
        "target",
        "trained_at",
        "data_start",
        "data_end",
        "train_end",
        "calibration_end",
        "alpha",
        "feature_columns",
        "metrics",
        "versions",
        "git_sha",
        "model_sha256",
    ):
        assert key in metadata
    assert saved.joinpath("model.joblib").exists()


def test_second_save_updates_unique_pointer_without_overwriting(fitted, tmp_path):
    model, _ = fitted
    first = save_model(model, "CISO", tmp_path)
    second = save_model(model, "CISO", tmp_path)
    assert first != second
    pointer = json.loads((second.parent / "current.json").read_text())
    assert pointer["version"] == second.name
    assert first.exists()


def test_missing_deleted_and_incompatible_models(fitted, tmp_path):
    with pytest.raises(ModelNotFoundError, match="train"):
        load_model("CISO", "demand_mwh", tmp_path)
    path = save_model(fitted[0], "CISO", tmp_path)
    metadata_path = path / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["feature_columns"] = ["old_feature"]
    metadata_path.write_text(json.dumps(metadata))
    with pytest.raises(ModelIncompatibleError, match="feature_columns"):
        load_model("CISO", "demand_mwh", tmp_path)
    path.joinpath("model.joblib").unlink()
    with pytest.raises(ModelNotFoundError, match="train"):
        load_model("CISO", "demand_mwh", tmp_path)


def test_path_escape_and_corrupt_pickle_rejected_before_load(fitted, tmp_path):
    with pytest.raises(ModelIncompatibleError, match="version"):
        load_model("CISO", "demand_mwh", tmp_path, version="../../outside")
    path = save_model(fitted[0], "CISO", tmp_path)
    path.joinpath("model.joblib").write_bytes(b"corrupted")
    with pytest.raises(ModelIncompatibleError, match="digest"):
        load_model("CISO", "demand_mwh", tmp_path)
