from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from carbon_scheduler.carbon.factors import (
    EmissionFactors,
    UnknownFuelError,
    check_coverage,
    load_emission_factors,
)


def write_config(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "factors.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_load_valid_factors(tmp_path):
    result = load_emission_factors(
        write_config(tmp_path, "factors: {ng: 490, wnd: 11}\nexcluded: [bat]\nsource: Study\n")
    )
    assert result.factors == {"ng": 490.0, "wnd": 11.0}
    assert result.excluded == frozenset({"bat"})
    assert result.source == "Study"
    check_coverage(result, iter(["ng", "bat", "wnd"]))


@pytest.mark.parametrize("value", ["0", "-1", ".nan", ".inf", "-.inf", "true", "'490'"])
def test_reject_invalid_factor(tmp_path, value):
    with pytest.raises(ValueError, match="emission factors"):
        load_emission_factors(
            write_config(tmp_path, f"factors: {{ng: {value}}}\nexcluded: []\nsource: Study\n")
        )


@pytest.mark.parametrize(
    "text",
    [
        "factors: {ng: 490}\nexcluded: [ng]\nsource: Study",
        "factors: {NG: 490}\nexcluded: []\nsource: Study",
        "factors: {ng: 490}\nexcluded: [bad-code]\nsource: Study",
        "factors: {}\nexcluded: []\nsource: Study",
        "factors: {ng: 490}\nexcluded: []\nsource: '   '",
        "factors: {ng: 490}\nexcluded: []",
        "[]",
        "factors: [",
        "!!python/object:builtins.object {}",
    ],
)
def test_reject_invalid_schema(tmp_path, text):
    with pytest.raises(ValueError, match="emission factors"):
        load_emission_factors(write_config(tmp_path, text))


def test_unknown_fuels_are_all_reported_sorted():
    factors = EmissionFactors({"ng": 490}, frozenset({"bat"}), "Study")
    with pytest.raises(UnknownFuelError, match="aaa, zzz"):
        check_coverage(factors, ["zzz", "ng", "aaa", "bat", "zzz"])


def test_factors_are_immutable_and_copy_input():
    values = {"ng": 490.0}
    factors = EmissionFactors(values, frozenset(), "Study")
    values["ng"] = 1
    assert factors.factors == {"ng": 490}
    with pytest.raises(TypeError):
        factors.factors["ng"] = 1
    with pytest.raises(FrozenInstanceError):
        factors.source = "changed"


def test_default_config_resolves_from_project_root(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    result = load_emission_factors(Path("config/emission_factors.yaml"))
    assert result.factors == {
        "col": 820,
        "ng": 490,
        "nuc": 12,
        "sun": 48,
        "wnd": 11,
        "wat": 24,
        "geo": 38,
        "oil": 650,
    }
    assert result.excluded == frozenset({"bat", "ps", "snb", "wnb", "oes", "ues", "unk", "oth"})
    assert "IPCC" in result.source
    assert "POSTnote" in result.source
