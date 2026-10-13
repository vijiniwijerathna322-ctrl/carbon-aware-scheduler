"Render a native API walkthrough from real responses; no browser/Docker recording claim."

import argparse
import json
import textwrap
from pathlib import Path
from tempfile import TemporaryDirectory

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from matplotlib.animation import FuncAnimation, PillowWriter  # noqa: E402

from carbon_scheduler.api.main import create_app  # noqa: E402
from carbon_scheduler.api.service import ForecastService  # noqa: E402
from carbon_scheduler.config import PROJECT_ROOT, Settings  # noqa: E402
from carbon_scheduler.monitoring.report import build_monitor_report, write_monitor_report  # noqa: E402


def capture_walkthrough():
    demo = PROJECT_ROOT / "demo"
    manifest = json.loads((demo / "manifest.json").read_text())
    with TemporaryDirectory(prefix="carbon-demo-") as directory:
        settings = Settings(
            _env_file=None,
            eia_api_key=None,
            demo_mode=True,
            data_dir=demo / "data",
            models_dir=demo / "models",
            reports_dir=Path(directory),
        )
        service = ForecastService(settings, manifest["region"])
        report = build_monitor_report(
            manifest["region"], settings, now=pd.Timestamp(manifest["data_end"]).to_pydatetime()
        )
        write_monitor_report(report, settings.reports_dir)
        with TestClient(create_app(lambda: service)) as client:
            health = client.get("/healthz")
            forecast = client.get("/v1/forecast?horizon=6")
            health.raise_for_status()
            forecast.raise_for_status()
            payload = forecast.json()
            issue = pd.Timestamp(payload["issue_time"])
            job = {
                "duration_hours": 2,
                "power_kw": 7,
                "deadline": (issue + pd.Timedelta(hours=24)).isoformat(),
            }
            schedule = client.post("/v1/schedule", json=job)
            schedule.raise_for_status()
            monitoring = client.get("/v1/monitoring/status")
            monitoring.raise_for_status()
            return {
                "health": health.json(),
                "forecast": payload,
                "job": job,
                "schedule": schedule.json(),
                "monitoring": monitoring.json(),
            }


WRAP_WIDTH = 100


def record_demo(output: Path) -> None:
    payload = capture_walkthrough()
    forecast, result, report = payload["forecast"], payload["schedule"], payload["monitoring"]
    selected = {
        key: forecast[key] for key in ("region", "issue_time", "data_as_of", "model_version")
    }
    selected["first_point"] = forecast["points"][0]
    frames = [
        (
            "A real native API walkthrough",
            (
                "No EIA key is used. This is a rendered walkthrough of real TestCl"
                "ient responses, not a browser or Docker screen recording. The tra"
                "cked CISO snapshot is historical."
            ),
        ),
        (
            "Health check",
            json.dumps(payload["health"], indent=2)
            + (
                "\n\nDemo mode accepts its frozen historical snapshot. Health is ser"
                "vice readiness, not evidence of interval calibration."
            ),
        ),
        (
            "Six-hour forecast request",
            json.dumps(selected, indent=2)
            + "\n\nNominal intervals; carbon held-out coverage missed its gate.",
        ),
        (
            "A flexible job with a deadline",
            json.dumps(payload["job"], indent=2)
            + (
                "\n\nThe request has no future actual values. Whole-hour feasibility"
                " and deadline constraints define the choices."
            ),
        ),
        ("A real scheduling recommendation", json.dumps(result["recommendation"], indent=2)),
        (
            "Post-fit monitoring",
            json.dumps({"status": report["status"], "coverage": report["coverage"]}, indent=2)
            + "\n\nPost-fit coverage stays insufficient_data; unavailable is not healthy.",
        ),
        (
            "Read the limitations with the results",
            (
                "Average observed generation proxy; imports ignored. Latest revisi"
                "ons and zero observation latency. Nominal pointwise bounds are no"
                "t job-level guarantees. Illustrative replay savings are not measu"
                "red avoided emissions."
            ),
        ),
        (
            "Reproduce and inspect",
            (
                "Run the offline README demo, inspect the model card and datasheet"
                ", regenerate figures from raw held-out reports. Live ERCO/automat"
                "ion acceptance remains pending; no production-deployment claim is"
                " made."
            ),
        ),
    ]
    fig = plt.figure(figsize=(12, 6.5), facecolor="#10202c")
    heading = fig.text(0.06, 0.89, "", color="#56b4e9", fontsize=20, weight="bold")
    body = fig.text(0.06, 0.78, "", color="white", fontsize=12, va="top", family="monospace")
    footer = fig.text(0.06, 0.045, "", color="#cccccc", fontsize=10)

    def update(index):
        title, content = frames[index]
        heading.set_text(title)
        body.set_text(
            "\n".join(
                textwrap.fill(line, width=WRAP_WIDTH) if len(line) > WRAP_WIDTH else line
                for line in content.splitlines()
            )[:2400]
        )
        footer.set_text(
            f"{index + 1}/{len(frames)} | Native API responses | Frozen historical CISO demo"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    (output.parent / "responses.json").write_text(json.dumps(payload, indent=2) + "\n")
    animation = FuncAnimation(fig, update, frames=len(frames), interval=8000)
    animation.save(output, writer=PillowWriter(fps=0.125), dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("docs/demo/native-walkthrough.gif"))
    record_demo(parser.parse_args().output)
