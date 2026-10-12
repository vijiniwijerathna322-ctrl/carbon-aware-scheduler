"""Record small public API probes, including unavailable historical coverage."""

import json
from pathlib import Path

import httpx

VARIABLES = "temperature_2m,cloud_cover,shortwave_radiation,wind_speed_100m"


def main() -> None:
    root = Path("tests/fixtures/open_meteo")
    root.mkdir(parents=True, exist_ok=True)
    cases = {
        "archive": ("https://archive-api.open-meteo.com/v1/archive", "2021-01-01"),
        "historical_forecast": (
            "https://historical-forecast-api.open-meteo.com/v1/forecast",
            "2021-01-01",
        ),
        "historical_forecast_recent": (
            "https://historical-forecast-api.open-meteo.com/v1/forecast",
            "2025-01-01",
        ),
        "forecast": ("https://api.open-meteo.com/v1/forecast", None),
    }
    with httpx.Client(timeout=60) as client:
        for name, (url, start) in cases.items():
            params: dict[str, str | float | int] = {
                "latitude": 36.74,
                "longitude": -119.78,
                "hourly": VARIABLES,
                "timezone": "UTC",
                "wind_speed_unit": "kmh",
            }
            if start is None:
                params["forecast_hours"] = 48
            else:
                params.update(start_date=start, end_date=start[:-2] + "02")
            response = client.get(url, params=params)
            try:
                payload = response.json()
            except ValueError:
                payload = {"error": True, "reason": "non-JSON response"}
            (root / f"{name}.json").write_text(
                json.dumps(payload, indent=2) + "\n", encoding="utf-8"
            )
            (root / f"{name}.request.json").write_text(
                json.dumps({"url": url, "params": params, "status": response.status_code}, indent=2)
                + "\n",
                encoding="utf-8",
            )
            print(
                name,
                response.status_code,
                len(payload.get("hourly", {}).get("time", [])),
                payload.get("reason", ""),
            )


if __name__ == "__main__":
    main()
