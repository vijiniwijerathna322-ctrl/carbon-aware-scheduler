"""Normalize the verified EIA hourly routes into typed long frames."""

import re
from typing import Any

import pandas as pd

from carbon_scheduler.ingest.eia_client import EiaClient

REGION_DATA_ROUTE = "electricity/rto/region-data"
FUEL_TYPE_ROUTE = "electricity/rto/fuel-type-data"
PERIOD_FORMAT = "%Y-%m-%dT%H"


def _frame(rows: list[dict[str, Any]], category: str) -> pd.DataFrame:
    periods = [row["period"] for row in rows]
    if any(
        not isinstance(period, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}", period) is None
        for period in periods
    ):
        raise ValueError("EIA period must use the verified UTC YYYY-MM-DDTHH format")
    try:
        timestamps = pd.to_datetime(periods, format=PERIOD_FORMAT, utc=True).astype(
            "datetime64[ns, UTC]"
        )
    except ValueError:
        raise ValueError("EIA period contains an invalid UTC hour") from None
    return pd.DataFrame(
        {
            "period": timestamps,
            category: pd.Series([row[category] for row in rows], dtype="str"),
            "value": pd.to_numeric(
                pd.Series([row["value"] for row in rows], dtype="object"), errors="coerce"
            ).astype("float64"),
        }
    )


def fetch_region_data(client: EiaClient, respondent: str, start: str, end: str) -> pd.DataFrame:
    """Fetch demand, forecast, net generation and interchange rows in UTC."""
    return _frame(
        client.fetch_route(
            REGION_DATA_ROUTE, facets={"respondent": [respondent]}, start=start, end=end
        ),
        "type",
    )


def fetch_fuel_type_data(client: EiaClient, respondent: str, start: str, end: str) -> pd.DataFrame:
    """Fetch generation rows for all available fuel categories in UTC."""
    return _frame(
        client.fetch_route(
            FUEL_TYPE_ROUTE, facets={"respondent": [respondent]}, start=start, end=end
        ),
        "fueltype",
    )
