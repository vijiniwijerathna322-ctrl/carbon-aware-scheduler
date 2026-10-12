"""Record sanitized EIA shape fixtures, without displaying the configured key."""

import json
from pathlib import Path
from typing import Any

import httpx

from carbon_scheduler.config import Settings

ROOT = Path(__file__).resolve().parents[1]
ROUTES = {"region_data": "region-data", "fuel_type_data": "fuel-type-data"}


def sanitize(value: Any, key: str) -> Any:
    """Remove credentials even from API-echoed request URLs."""
    if isinstance(value, dict):
        return {name: sanitize(item, key) for name, item in value.items() if name != "api_key"}
    if isinstance(value, list):
        return [sanitize(item, key) for item in value]
    return value.replace(key, "REDACTED") if isinstance(value, str) else value


def main() -> None:
    key = Settings().require_eia_key()
    destination = ROOT / "tests/fixtures/eia"
    destination.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=60) as http:
        for name, route in ROUTES.items():
            base = f"https://api.eia.gov/v2/electricity/rto/{route}/"
            requests = {
                f"route_meta_{name}.json": (base, {}),
                f"{name}_page.json": (
                    base + "data/",
                    {
                        "frequency": "hourly",
                        "data[0]": "value",
                        "facets[respondent][]": "CISO",
                        "start": "2024-01-01T00",
                        "end": "2024-01-02T00",
                        "length": "5000",
                        "sort[0][column]": "period",
                        "sort[0][direction]": "asc",
                    },
                ),
            }
            facet = "type" if name == "region_data" else "fueltype"
            requests[f"facet_{facet}.json"] = (base + f"facet/{facet}/", {})
            for filename, (url, parameters) in requests.items():
                try:
                    response = http.get(url, params={"api_key": key, **parameters})
                except httpx.HTTPError:
                    raise SystemExit(
                        "EIA probe network request failed; credentials hidden."
                    ) from None
                if response.status_code != httpx.codes.OK:
                    raise SystemExit(f"EIA probe returned HTTP {response.status_code}.")
                payload = sanitize(response.json(), key)
                (destination / filename).write_text(json.dumps(payload, indent=2) + "\n")
                body = payload.get("response", {})
                rows = body.get("data", [])
                summary = {"file": filename, "total": body.get("total")}
                if isinstance(rows, list) and rows:
                    summary.update(first=rows[0], last=rows[-1])
                elif "facets" in body:
                    summary["facets"] = body["facets"]
                print(json.dumps(summary))


if __name__ == "__main__":
    main()
