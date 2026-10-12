"""Build a complete UTC hourly frame from normalized EIA observations."""

import pandas as pd

REGION_COLUMNS = {
    "D": "demand_mwh",
    "DF": "demand_forecast_mwh",
    "NG": "net_generation_mwh",
    "TI": "net_interchange_mwh",
}


def _validate_period(frame: pd.DataFrame) -> None:
    periods = frame["period"]
    if str(periods.dtype) != "datetime64[ns, UTC]":
        raise ValueError("period must have datetime64[ns, UTC] dtype")
    if periods.isna().any() or not periods.eq(periods.dt.floor("h")).all():
        raise ValueError("period must contain valid whole UTC hours")


def to_hourly_frame(region: pd.DataFrame, fuel: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Pivot observations, keeping the last revision even when its value is null.

    Missing source columns and hours remain NaN for downstream quality checks.
    The time span includes all observations, including unknown regional types.
    """
    _validate_period(region)
    _validate_period(fuel)
    periods = pd.concat([region["period"], fuel["period"]], ignore_index=True)
    index = (
        pd.DatetimeIndex([], dtype="datetime64[ns, UTC]", name="period")
        if periods.empty
        else pd.date_range(periods.min(), periods.max(), freq="h", name="period")
    )
    region_rows = region.drop_duplicates(["period", "type"], keep="last")
    fuel_rows = fuel.drop_duplicates(["period", "fueltype"], keep="last")
    duplicates = len(region) - len(region_rows) + len(fuel) - len(fuel_rows)
    region_wide = (
        region_rows[region_rows["type"].isin(REGION_COLUMNS)]
        .pivot(index="period", columns="type", values="value")
        .rename(columns=REGION_COLUMNS)
        .reindex(index=index, columns=list(REGION_COLUMNS.values()))
    )
    fuel_codes = sorted(fuel_rows["fueltype"].unique())
    fuel_wide = (
        fuel_rows.pivot(index="period", columns="fueltype", values="value")
        .reindex(index=index, columns=fuel_codes)
        .rename(columns={code: f"gen_{code.lower()}_mwh" for code in fuel_codes})
    )
    result = pd.concat([region_wide, fuel_wide], axis=1).astype("float64")
    result.columns.name = None
    return result, duplicates
