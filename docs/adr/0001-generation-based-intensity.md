# ADR 0001: Generation-based lifecycle intensity

## Context

Decision D1 needs an hourly carbon proxy from EIA-930 generation. The dataset
contains incomplete fuel observations, negative values, and heterogeneous OTH
generation. Imports have no origin-specific emissions information.

## Decision

Use the sum of observed positive generation times its lifecycle emission factor,
divided by the sum of observed positive generation for factor-covered fuels.
MWh weights cancel, producing gCO2e/kWh. Factors and source citations live in
`config/emission_factors.yaml`; uncovered codes raise an error.

Exclude storage, integrated storage, unknown codes and OTH from both sums.
Clip negative observed generation to zero for weighting and count it. Preserve
missing observations; partial mixes use only observed generation. No included
positive generation produces NaN. Do not infer historical geothermal generation
or map OTH to biomass.

Store covered/excluded positive generation, observed coverage fraction, missing
included fuel-cell counts and negative fuel-cell counts alongside intensity.
The report lists absent factor codes, actual included/excluded codes, factors,
citations and SHA-256 digests of input Parquet and factor YAML. Equal reruns
preserve output bytes and modification times.

## Consequences

This is a proxy for the covered observed generation mix, rather than consumption
intensity. Imports and exports are not attributed. Lifecycle factors include
upstream and construction emissions and must not be described as direct stack
emissions. Oil uses a separately sourced historical UK average proxy.

Observed coverage does not measure the share of true generation when data is
missing. GEO reporting begins late in this history, so most earlier rows have
partial fuel coverage. Interpolated interim values retain ingestion provenance
in the interim quality report; carbon missing-cell counts describe the cleaned
input, not every original upstream gap. Excluding OTH can materially lower or
raise the proxy. Values outside the rough 100–350 g/kWh range are investigated
with fuel shares rather than clipped. The theoretical bounds are the smallest
and largest configured factors in each observed mix.

The dataset and JSON report are each replaced atomically; they are not a
transactional pair. After an interrupted build, rerun the command to reconcile
them before using the processed snapshot.
