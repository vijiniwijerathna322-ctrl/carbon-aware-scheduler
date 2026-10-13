# Dataset datasheet

## Source and collection

EIA-930 hourly balancing-authority demand, demand forecasts, net generation, interchange and fuel generation are collected through the EIA v2 API. The measured CISO snapshot spans 2021-01-01 00:00 through 2026-10-12 05:00 UTC: 50,646 hourly rows. Files and model metadata retain source digests. API credentials are excluded from version control, demo assets and reports. ERCO collection and real held-out evaluation completed on GitHub runners; see [regional results](results/second-region-erco.md) for source provenance and failed demand coverage acceptance.

## Observed quality

The recorded ingestion QualityReport contains 0 negative-demand values, 0 detected demand spikes, 109 interpolated cells, 623 hours missing at least one of the four core region series and 44,595 remaining missing cells across columns. The reported row gap fraction is 0.01230107. Geothermal accounts for 43,472 missing cells because its first observed column value is 2025-12-16 09:00 UTC; structural column history must not be confused with an outage of the entire grid. Fuel/net-generation observations end 23 hours before demand in this snapshot.

These are counts for the cleaned interim ingestion snapshot, not claims that forecasting used interpolated observations. The raw-target forecasting/backtest path applies pointwise validity rules, preserves missing values and avoids retrospective interpolation and centered spike filters. Carbon intensity is calculated only from the available covered generation mix; missing included fuel values and excluded generation are separately counted. Unknown fuel codes raise an error rather than receiving a guessed factor.

## Carbon construction

The lifecycle proxy is the generation-weighted average of configured technology factors in gCO2e/kWh. IPCC AR5 WGIII Annex III lifecycle medians supply coal, gas, nuclear, solar, wind, hydro and geothermal. Oil uses the separately attributed historical UK proxy from POSTnote 268. [Factor configuration](../config/emission_factors.yaml) records exact values, exclusions and source links. Imports, heterogeneous other fuels and storage charging mix are not resolved. This dataset cannot identify marginal emissions or certify load-shifting carbon offsets.

## Revisions, availability and updates

The API supplies latest revisions, not the actual values visible to a historical operator at each forecast issue. Backtests assume zero observation latency; model evaluation is chronologically separated, but publication-vintage uncertainty remains. Incremental ingestion refreshes an overlap window and writes complete hourly snapshots atomically. It may checkpoint complete yearly route pairs before a later upstream failure; incomplete serialization never replaces a prior valid file. Live CISO refresh validated ingestion, diagnostic retention and alert issue creation; the monitor reported alert and insufficient post-fit performance support. Healthy operational acceptance remains pending.

## Reuse and attribution

EIA data retains its source attribution and reuse conditions; code licensing does not relicense data. Open-Meteo weather inputs are attributed under CC BY 4.0, with its service-use conditions applying separately. Weather archives were used only for exploratory ablation; production models remain weather-free. IPCC and POST source publications retain their own rights. All external source definitions and preprocessing decisions should accompany derivative figures and proxy claims.

## References and reproducibility

See [point forecast results](results/backtest-point.md), [CQR results](results/backtest-cqr.md), [scheduling replay](results/schedule-backtest.md), [weather ablation](results/ablation-weather.md) and ADRs 0001, 0005 and 0011. Re-run ingestion/build-dataset with an EIA key to produce fresh quality diagnostics; retain the snapshot hash when comparing runs. Raw, processed and model files are local ignored artifacts; the tracked demo is an explicit bounded public snapshot.

The [committed quality snapshot](results/data-quality.json) preserves the ingestion counts used above.
