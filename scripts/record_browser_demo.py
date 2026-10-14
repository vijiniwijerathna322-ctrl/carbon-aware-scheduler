"""Scripted Chromium recording of the real frozen Docker API, without credentials."""

import json
from datetime import datetime, timedelta
from http import HTTPStatus
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    output = Path("reports/browser-demo")
    output.mkdir(parents=True, exist_ok=True)
    responses = {}
    with sync_playwright() as runner:
        browser = runner.chromium.launch()
        context = browser.new_context(
            viewport={"width": 1280, "height": 900}, record_video_dir=str(output)
        )
        page = context.new_page()
        page.goto("http://127.0.0.1:8000/docs")
        page.wait_for_selector(".swagger-ui")
        page.wait_for_timeout(8000)

        def show(title: str, path: str, payload: dict | None = None) -> dict:
            result = page.evaluate(
                """async ({path, payload}) => {
                    const response = await fetch(path, payload ? {
                        method: 'POST', headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(payload)
                    } : {});
                    return {status: response.status, body: await response.json()};
                }""",
                {"path": path, "payload": payload},
            )
            responses[title] = result
            page.evaluate(
                """({title, result}) => {
                    document.body.replaceChildren();
                    const heading = document.createElement('h1'); heading.textContent = title;
                    const note = document.createElement('p');
                    note.textContent = 'Real browser fetch from frozen CISO Docker demo. '
                        + 'Historical timestamps; research release, not production acceptance.';
                    const code = document.createElement('pre');
                    code.textContent = JSON.stringify(result, null, 2);
                    document.body.style.cssText = 'padding:24px;font:18px monospace;'
                        + 'background:#fff;color:#111';
                    document.body.append(heading, note, code);
                }""",
                {"title": title, "result": result},
            )
            page.wait_for_timeout(8000)
            return result

        assert show("Health", "/healthz")["status"] == HTTPStatus.OK
        forecast = show("Six-hour carbon forecast", "/v1/forecast?horizon=6")
        assert forecast["status"] == HTTPStatus.OK
        issue = datetime.fromisoformat(forecast["body"]["issue_time"].replace("Z", "+00:00"))
        schedule = show(
            "Two-hour 7 kW scheduling request",
            "/v1/schedule",
            {
                "duration_hours": 2,
                "power_kw": 7,
                "deadline": (issue + timedelta(hours=24)).isoformat(),
            },
        )
        assert schedule["status"] == HTTPStatus.OK
        assert (
            show("Demo monitoring report absent (expected)", "/v1/monitoring/status")["status"]
            == HTTPStatus.NOT_FOUND
        )
        page.set_content(Path("docs/results/ciso-refresh-validation/monitor_CISO.html").read_text())
        page.wait_for_timeout(8000)
        for name in ("coverage.png", "savings.png"):
            page.goto((Path("docs/figures") / name).resolve().as_uri())
            page.wait_for_timeout(8000)
        context.close()
        browser.close()
    (output / "responses.json").write_text(json.dumps(responses, indent=2) + "\n")


if __name__ == "__main__":
    main()
