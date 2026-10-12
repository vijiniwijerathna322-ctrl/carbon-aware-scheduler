# ADR 0016: Exploratory weather covariates and conservative serving

## Context

Plan 08 investigates temperature, cloud cover, shortwave radiation and 100 m wind.
The checked-in probe fixtures record actual UTC requests and responses. January
2021 Historical Forecast returned 48 rows but no finite 100 m wind values; the
2025 probe returned all four variables. Archive and live probes returned all four.
The [Historical Forecast documentation](https://open-meteo.com/en/docs/historical-forecast-api)
describes seamless history stitched from model runs. It is not an issue-vintage
48-hour forecast panel. Historical coverage alone cannot establish availability
at each energy forecast issue. [Previous Runs](https://open-meteo.com/en/docs/previous-runs-api)
is a separate product with variable/model-dependent historical coverage.

## Decision

Use archive/reanalysis only for an explicitly exploratory hindsight ablation.
Verify the previously evaluated weather-free baseline's input hashes, parameters,
calibration window, seed, issue/target keys and labels before reusing its results.
Publish both targets' paired metrics and never promote a model from this ablation.
Operational validation requires weather vintages available at each issue and a
fresh holdout. The generic single-index exogenous frame is suitable for this
exploration; an issue/target panel is still needed for genuine vintage training.

CISO uses Los Angeles (0.5), San Francisco (0.3) and Fresno (0.2). These are
illustrative geographic weights, not measured load shares. Units are Celsius,
percent, W/m² and km/h. Weighted missingness is retained: a missing contributing
point yields NaN, with no silent filling or weight renormalization. Forecast
caches expire at one hour; historical caches are keyed by point/source/date range.

Keep `current.json` pointing to the weather-free fallback. An optional
`models/<region>/<target>/weather.json` contains `{"version": "...", "approved": true}`.
Its artifact must carry `exog_source=issue_vintage_forecast`, raw energy provenance,
compatible carbon factors and a fitting cutoff no later than the snapshot issue.
Approval is a manual evidence gate, not inferred from a filename or metrics.
No such production variant is approved by this plan.

Serving requires all 48 weather target hours and a timezone-aware `received_at`
no later than the reported issue time. A newly fetched response after that time
therefore falls back rather than silently adding future information. Live serving
requests explicit `start_hour`/`end_hour` covering energy issue+1 through issue+48;
plain `forecast_hours=48` would start at the provider's current hour. A matching
forecast cache must have been prepared by the issue time (for example through
pre-issue prefetch). A future operational design must supply that acquisition
workflow and reconcile weather issuance with the energy issue convention.

Demo variants, when explicitly supplied, read
`data/weather/<region>_forecast.parquet` and never request the network. The shipped
demo has no weather variant or weather snapshot because the production decision
is to retain the existing baseline. Forecast and schedule responses expose
fallback notes; `/v1/models/current` identifies the model actually serving.

A live explicit-range probe on 2026-10-12 returned 48 hours with all four
variables finite; the corresponding request-window contract has a fixture test.

On 8,756 paired demand points, weather MAE fell from 1253.69 to 1085.81 MWh,
but coverage fell from 77.35% to 76.34%, below the overall G4 lower bound.
This also rejects demand promotion on the measured interval-quality criterion.
On 8,710 paired intensity points, weather MAE rose from 33.41 to 37.63
gCO2e/kWh (+12.64%) and coverage fell from 71.57% to 70.45%. Thus this
weather configuration also worsened carbon accuracy and interval coverage.
The [full ablation](../results/ablation-weather.md) publishes every horizon bucket.

## Consequences

Optional weather outages do not make the baseline unhealthy. Synthetic tests
verify approved live/demo paths and exact baseline equality for network failure,
future weather, missing weather and unapproved variants. These tests establish
software behavior, not operational model validity. Archive target weather at
prediction time remains hindsight information even with chronological energy
splits. Carbon's existing G4 miss remains a disclosed limitation.

Weather data attribution: [Open-Meteo](https://open-meteo.com/), CC BY 4.0.
The public API is for non-commercial use under its
[terms](https://open-meteo.com/en/terms); requests are bounded and cached.
