# Carbon-Aware Energy Scheduler — Design Spec

Date: 2026-10-11 · Status: draft for review · Owner: Gihan

## 1. Problem and purpose

Electricity from the grid is not equally "clean" at every hour: carbon intensity (gCO2e emitted per kWh) swings with the generation mix (solar at noon, gas at night). Flexible loads (EV charging, ML training, batch jobs) can shift in time to cut emissions, but only if someone can **forecast** the next 48 hours **with honest uncertainty** and turn that forecast into a **decision**.

This project builds that end to end from free public data: ingest → forecast demand and carbon intensity with calibrated intervals → recommend when to run a flexible job → serve via API → monitor drift.

Purpose for the owner: a data science internship portfolio piece that shows probabilistic forecasting, decision-making under uncertainty, honest evaluation, deployment and monitoring.

## 2. Scope

### MVP (plans 01–07)
- One balancing authority: **CISO** (California ISO). Data: 2021-01-01 → present, hourly.
- Targets: `demand_mwh` and `carbon_intensity_g_per_kwh`, horizons 1..48 h.
- Point forecast (median) plus 80% prediction interval (conformalized quantile regression).
- Scheduler: given a job (duration, power, earliest start, deadline), recommend a start time and report expected emissions vs "run now".
- Replay backtest of the scheduler on historical data (realized savings, regret vs oracle).
- FastAPI service in Docker; runs offline from a baked demo snapshot (no API key needed to demo).

### v1 (plans 08–11)
- Weather features (Open-Meteo), drift and coverage monitoring, scheduled automation (GitHub Actions), second region (ERCO) as a generalization check, portfolio documentation.

### Non-goals
- No real-time streaming, no database server, no auth, no UI beyond OpenAPI docs, no deep learning, no multi-region optimisation, no marginal-emissions modelling, no commercial use.

## 3. Data sources (all free)

| Source | Use | Access | Notes |
|---|---|---|---|
| EIA Open Data API v2, route `electricity/rto/region-data` | demand (D), day-ahead demand forecast (DF), net generation (NG), interchange (TI) | free key via `EIA_API_KEY` | JSON capped at 5,000 rows/page → paginate |
| EIA API v2, route `electricity/rto/fuel-type-data` | net generation by fuel | same key | fuel codes verified by live probe (plan 02, Task 1) |
| EIA-930 bulk CSV/XLSX | fallback for history | no key | not used in MVP |
| IPCC AR5 lifecycle emission medians; separately sourced POST oil proxy | emission factors | static YAML in repo | per-fuel source attribution; technology mappings and limitations documented (plan 03) |
| Open-Meteo archive + forecast | weather features (v1 only) | no key, non-commercial, CC BY 4.0 attribution | plan 08 |

**Verified EIA facts** (live probe 2026-10-12; sanitized API v2.1.14 fixtures in `tests/fixtures/eia/`): `frequency=hourly` is explicitly UTC and periods use `YYYY-MM-DDTHH` (`%Y-%m-%dT%H`). Region facets are `respondent`, `type`; fuel facets are `respondent`, `fueltype`. Metric codes are `D`, `DF`, `NG`, `TI`. The fuel facet endpoint lists 16 distinct codes: `BAT`, `COL`, `GEO`, `NG`, `NUC`, `OES`, `OIL`, `OTH`, `PS`, `SNB`, `SUN`, `UES`, `UNK`, `WAT`, `WNB`, `WND`; repeated IDs have different display labels, so deduplicate IDs. The CISO 2024 sample has eight fuel codes (`COL`, `NG`, `NUC`, `OIL`, `OTH`, `SUN`, `WAT`, `WND`). Values and `response.total` are strings. Both start and end are inclusive: 2024-01-01T00 through 2024-01-02T00 has 25 hours, 100 regional rows and 200 fuel rows. Units are megawatthours. No revision identifier occurs in the sampled rows; incremental refresh treats new observations as replacements. Null handling remains defensive and will be covered by synthetic tests. A further live probe verified ascending secondary sorts on `respondent` and `type`/`fueltype`; pagination uses these after `period` to make same-hour category ordering deterministic.

**Verified Open-Meteo facts (2026-10-12):** archive
`https://archive-api.open-meteo.com/v1/archive`, live
`https://api.open-meteo.com/v1/forecast` and historical forecast
`https://historical-forecast-api.open-meteo.com/v1/forecast` returned HTTP 200
in the checked-in probes. Request `timezone=UTC` and `wind_speed_unit=kmh`;
`temperature_2m`, `cloud_cover`, `shortwave_radiation`, `wind_speed_100m`
return units Celsius, percent, W/m² and km/h. January 2021 historical forecast
had no finite 100 m wind values, although other variables were populated;
January 2025 had all four. Seamless historical forecast is not an issue-vintage
48-hour panel. Plan 08 therefore publishes archive weather as an explicitly
exploratory hindsight ablation and retains weather-free production models.
See [ADR 0016](../docs/adr/0016-weather-provenance-and-fallback.md).


## 4. Key decisions

| # | Decision | Why |
|---|---|---|
| D1 | Carbon intensity is an **observed generation-mix lifecycle proxy**: `Σ(max(observed gen_f, 0) × EF_f) / Σ max(observed gen_f, 0)` over factor-covered fuels; storage/hybrid, unknown and unresolved OTH excluded; imports ignored | Partial mixes retain missing observations and carry coverage/missing/clipping diagnostics. IPCC technology medians plus a separately attributed historical UK oil proxy are transparent assumptions; consumption-based and marginal emissions are out of scope |
| D2 | One **global** LightGBM model per target with `horizon` as a feature, not 48 models | Fewer artifacts, shared strength across horizons |
| D3 | Features use only information available at issue time. Seasonal anchors: `y[t+h-24·ceil(h/24)]`, `y[t+h-168·ceil(h/168)]` | Prevents leakage; fixes lag meaning for every horizon |
| D4 | Intervals via **conformalized quantile regression** (CQR), calibrated on a chronologically later window, per horizon bucket (1–6, 7–24, 25–48) | Distribution-free, finite-sample coverage under exchangeability; honest about drift |
| D5 | Splits are chronological only; evaluation by rolling-origin backtest on pointwise raw targets with physical fit/predict truncation | Time-series integrity; retrospective interpolation and centered cleaning are excluded from real model evaluation |
| D6 | Storage: Parquet files under `data/{raw,interim,processed}/{region}/`; no database | YAGNI |
| D7 | Scheduler strategies: `median` (minimise expected emissions) and `upper` (risk-averse, minimise the upper bound). Non-interruptible first; interruptible is a stretch task | Shows decision-under-uncertainty trade-off |
| D8 | Demo image bakes a small data snapshot and trained model; live refresh is optional | Anyone can run it with no key |
| D9 | Own implementations for conformal, PSI/KS drift and metrics (≈30–60 lines each) with tests; Evidently only for an optional HTML report | Fewer fragile dependencies, shows understanding |
| D10 | Config via env/`pydantic-settings`; region metadata in `config/regions.yaml` | 12-factor |

## 5. Architecture

```
EIA API ──► ingest ──► interim/{region}/hourly.parquet ──► carbon ──► processed/{region}/hourly.parquet
                                                                        │
                            features ◄──────────────────────────────────┘
                               │
                    LightGBM quantiles ─► CQR calibration ─► models/{region}/{target}/current/
                                                                        │
                    FastAPI (/v1/forecast, /v1/schedule) ◄─ ForecastService ─┘
                         │                                              │
                    scheduler (optimizer)                      monitoring (drift, coverage)
```

Package: `src/carbon_scheduler/{config,logging,cli}.py` and subpackages `ingest/ carbon/ features/ models/ scheduler/ api/ monitoring/`.

## 6. Data contracts

- **Raw observations**: `raw/{region}/hourly.parquet` preserves pre-cleaning values for incremental revisions and audit. Cleaning produces interim output; processed is reserved for carbon intensity (ADR 0006).
- **Hourly frame** (raw/interim/processed): index `DatetimeIndex` tz=UTC, hourly, no gaps (NaN allowed). Columns: `demand_mwh`, `demand_forecast_mwh`, `net_generation_mwh`, `net_interchange_mwh`, `gen_<fuel>_mwh` per fuel. Processed adds `carbon_intensity_g_per_kwh`.
- **Carbon diagnostics** (processed): `carbon_covered_generation_mwh`, `carbon_excluded_generation_mwh`, `carbon_observed_coverage_fraction`, `carbon_missing_fuel_count` (present included columns), and `carbon_negative_generation_count` (all observed fuel columns). Coverage divides covered positive generation by all observed positive fuel generation; it cannot quantify missing amounts. All-missing or zero included totals produce NaN; partial mixes remain explicitly incomplete. GEO before its first reporting date stays missing, and OTH is never assumed to be biomass. Carbon provenance records configuration/source and input/factor digests; no lifecycle factor is presented as a measured hourly emissions rate.
- **Forecast frame**: columns `issue_time`, `target_time` (UTC), `horizon` (int 1..48), `lower`, `median`, `upper`, `target` (`demand_mwh`|`carbon_intensity_g_per_kwh`).
- **Forecast evaluation inputs**: default to raw observations; mask nonpositive demand and recompute carbon pointwise without interpolation or centered filters. Retrospective processed-data evaluation is explicit exploratory mode only. Latest revisions and zero observation latency remain assumptions; historical publication vintages are not reconstructed (ADR 0005).
- **Ingestion quality report**: `gap_fraction` counts hours incomplete in any of the four required regional series; absent required columns count as missing for every hour. `n_remaining_gaps` counts these hours. Interpolation counts filled cells across numeric columns, and remaining missing-cell totals include virtual absent required columns. Fuel missingness, first/last observed UTC ISO timestamps and interior missing counts are diagnostics; G2 does not certify carbon-mix completeness. Cleaning rejects infinite values, flags demand <= 0 and centered 168-hour median/MAD spikes, then fills only complete bounded interior gaps of at most three hours. This retrospective cleaning uses future observations; historical forecast evaluation must avoid leakage. See ADR 0011.
- **Model artifact**: directory with `model.joblib` and `metadata.json` (keys: `region`, `target`, `trained_at`, `data_start`, `data_end`, `train_end`, `calibration_end`, `alpha`, `feature_columns`, `metrics`, `versions`, `git_sha`).

## 7. Evaluation protocol and success targets

Rolling-origin backtest on CISO: last 6 months test, 3 months calibration immediately before, training before that. Issue times every 24 h at 00:00 local.

Targets (reported honestly even if missed):
- Median MAE beats seasonal-naive (168 h) for both targets at every horizon bucket on paired finite predictions and identical realized labels; report full per-model availability separately.
- 80% interval empirical coverage in [77%, 83%] overall and ≥ 70% in every horizon bucket.
- Scheduler replay: mean realized emissions savings vs run-now > 0; report regret vs oracle and the `median` vs `upper` strategy trade-off.

## 8. Engineering standards

- Python ≥3.11,<3.13, `src/` layout, `uv` with committed lockfile, `pyproject.toml` single config.
- `ruff` (lint+format), `mypy` strict on `src`, `pytest` + coverage ≥ 80%.
- Test pyramid: unit (no network) → fixture-based integration → opt-in `live` tests.
- TDD per task, one logical commit per task, Conventional Commits.
- Architecture Decision Records in `docs/adr/` for D1–D10 as they are implemented.
- Secrets only via env; `.env.example` committed, `.env` ignored. Logs never contain keys.
- Docker: multi-stage, non-root user, healthcheck, pinned base image, `.dockerignore`.
- Reproducibility: fixed seeds, pinned deps, data version recorded in model metadata.
- Data licence and attribution recorded in README (EIA reuse policy; Open-Meteo CC BY 4.0).

## 9. Risks

| Risk | Mitigation |
|---|---|
| EIA data anomalies (spikes, negatives, gaps, revisions) | validation + quality report; 48 h overlap on incremental ingest |
| EIA rate limits unpublished | pagination, retry with backoff, request throttle, bulk-file fallback |
| Leakage via weather (archive vs forecast) | document; ablation; prefer historical-forecast data if available |
| Generation-based intensity ignores imports | document in model card; sensitivity note |
| Free hosting terms change | local Docker + recorded demo is the baseline deliverable |
| Scope creep | MVP line after plan 07; anything else is v1 |

Monitoring implementation of D9: post-fit daily replay only, one latest eligible forecast per realized hour, minimum 100 finite observations, earlier configuration-matched held-out MAE baseline, explicit insufficient data and source provenance. PSI/KS/binomial diagnostics are heuristic under serial dependence and seasonality; see ADR 0017. Approved weather variants require forecast-vintage logs before monitoring replay.
