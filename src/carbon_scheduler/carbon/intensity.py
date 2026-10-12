"""Compute a lifecycle proxy from observed, factor-covered generation."""

import re

import numpy as np
import pandas as pd

from carbon_scheduler.carbon.factors import EmissionFactors, check_coverage


def compute_intensity(df: pd.DataFrame, factors: EmissionFactors) -> pd.Series:
    """Weight factors by positive observed generation, without imputing missing data.

    This describes the covered observed mix, rather than true whole-grid intensity.
    Excluded fuels contribute neither emissions nor generation to this proxy.
    """
    fuel_columns = {
        column: match.group(1)
        for column in df.columns
        if isinstance(column, str) and (match := re.fullmatch(r"gen_(.+)_mwh", column))
    }
    check_coverage(factors, fuel_columns.values())
    result = pd.Series(np.nan, index=df.index, dtype="float64", name="carbon_intensity_g_per_kwh")
    if not fuel_columns:
        return result

    generation = df[list(fuel_columns)]
    if not generation.empty and any(
        not pd.api.types.is_numeric_dtype(dtype) or pd.api.types.is_bool_dtype(dtype)
        for dtype in generation.dtypes
    ):
        raise ValueError(f"Generation must be numeric in fuel columns: {', '.join(fuel_columns)}")
    numeric = generation.astype("float64")
    if np.isinf(numeric.to_numpy()).any():
        raise ValueError(
            f"Generation must be finite or missing in fuel columns: {', '.join(fuel_columns)}"
        )

    included = [column for column, fuel in fuel_columns.items() if fuel in factors.factors]
    if not included:
        return result
    weights = numeric[included].clip(lower=0)
    denominator = weights.sum(axis=1, min_count=1)
    factor_values = pd.Series(
        {column: factors.factors[fuel_columns[column]] for column in included}
    )
    numerator = weights.mul(factor_values).sum(axis=1, min_count=1)
    intensity = numerator.div(denominator.where(denominator > 0))
    intensity.name = result.name
    return intensity.astype("float64")
