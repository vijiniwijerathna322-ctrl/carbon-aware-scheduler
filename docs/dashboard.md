# Local Streamlit dashboard

The Streamlit frontend reads the existing FastAPI service. It provides forecasts,
a scheduling form, CSV export and recorded monitoring status. It never trains or
promotes a model. The optional `ui` dependency group does not enter the API image.

From the repository root in PowerShell, install the frozen environment:

```powershell
.\.tools\uv.exe --cache-dir .uv-cache sync --frozen --group ui
```

In terminal 1, start the key-free demo backend:

```powershell
$env:CARBON_DATA_DIR="demo/data"
$env:CARBON_MODELS_DIR="demo/models"
$env:DEMO_MODE="1"
.\.tools\uv.exe --cache-dir .uv-cache run --frozen uvicorn carbon_scheduler.api.main:app --host 127.0.0.1 --port 8000
```

In terminal 2, start the dashboard:

```powershell
.\.tools\uv.exe --cache-dir .uv-cache run --frozen --group ui streamlit run streamlit_app.py --server.address 127.0.0.1
```

Open http://localhost:8501. Keep both terminals running and press Ctrl+C in each
to stop. No EIA key is required for demo mode. If `uv` is on PATH you may use
`uv` instead of the bundled executable; `make ui` is also available.

The sidebar defaults to http://127.0.0.1:8000. `CARBON_API_URL` can set a different
initial backend URL. The served region and timestamps come from the API, not the
wall clock. Scheduling deadlines are relative to the first forecast hour, and
the form validates duration against available time before submitting.

The frontend displays API errors, stale/unavailable model status, and an absent
monitoring report distinctly. The demo's 404 monitor response is expected and is
not a healthy monitoring claim. A returned monitor report can be historical;
its generation timestamp is displayed. Interval endpoints are nominal pointwise
bounds; savings are an average generation-proxy estimate, not certified avoided
emissions.

UI checks (requires the optional group):

```powershell
.\.tools\uv.exe --cache-dir .uv-cache run --frozen --group ui pytest tests/ui -q --no-cov
```
