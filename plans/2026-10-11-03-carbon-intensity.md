# 03 Carbon Intensity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn per-fuel hourly generation into a documented, tested `carbon_intensity_g_per_kwh` series and a processed dataset ready for modelling.

**Architecture:** Emission factors live in a validated YAML file; a pure function computes generation-weighted intensity; a `build-dataset` step reads interim data, adds the series and writes processed data.

**Tech Stack:** pandas, pyyaml, pydantic (factor schema).

**Spec:** `docs/superpowers/specs/2026-10-11-carbon-aware-scheduler-design.md` (decision D1)

## Global Constraints

- Intensity unit gCO2e/kWh; generation unit MWh (ratio is unit-consistent)
- Generation-based intensity: `Σ(gen_f × EF_f) / Σ gen_f`; storage (`bat`, `ps`, `snb`) and `unk`/unknown excluded from numerator and denominator; imports ignored (documented limitation)
- Emission factors: IPCC AR5 lifecycle medians (starting values: coal 820, natural gas 490, oil 650, nuclear 12, solar 48, wind 11, hydro 24, geothermal 38, biomass 230) — **verify against the source before publishing**; the `other` fuel code must be handled explicitly, not guessed
- Gate per task: ruff, format check, mypy, pytest; Conventional Commits

## Review Focus

- A fuel code in the data with no factor and not in the exclusion list → loud error, never silently zero
- Hour with zero or NaN total generation → NaN intensity, not 0 or inf
- Negative generation for a fuel (data glitch or storage) must not produce intensity outside [min EF, max EF]
- Intensity must always lie between the smallest and largest factor among included fuels
- Changing a factor in YAML changes the output (no hidden hard-coding)

---

### Task 1: Emission factors file and loader

**Files:**
- Create: `config/emission_factors.yaml`, `src/carbon_scheduler/carbon/__init__.py`, `src/carbon_scheduler/carbon/factors.py`
- Test: `tests/carbon/test_factors.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class EmissionFactors: factors: Mapping[str, float]; excluded: frozenset[str]; source: str`
  - `def load_emission_factors(path: Path) -> EmissionFactors` — keys are lower-case EIA fuel codes confirmed in plan 02 Task 1; validation: values > 0, no key both in `factors` and `excluded`
  - `def check_coverage(factors: EmissionFactors, fuel_codes: Iterable[str]) -> None` raising `UnknownFuelError` listing the uncovered codes

- [ ] **Step 1: Failing tests:** `test_loads_valid_file`, `test_rejects_non_positive_factor`, `test_rejects_overlap_between_factors_and_excluded`, `test_unknown_fuel_raises_and_names_code`
- [ ] **Step 2: Run:** `uv run pytest tests/carbon/test_factors.py -v` → FAIL
- [ ] **Step 3: Implement.** YAML includes `source:` (citation string for IPCC AR5 WGIII Annex III) and a comment on each value. **Manual check:** open the cited table and confirm each number; fix the file if any differs.
- [ ] **Step 4: Run** → PASS
- [ ] **Step 5: Commit** `feat(carbon): emission factors config and loader`

### Task 2: Generation-weighted carbon intensity

**Files:**
- Create: `src/carbon_scheduler/carbon/intensity.py`
- Test: `tests/carbon/test_intensity.py`

**Interfaces:**
- Consumes: `EmissionFactors`, the hourly frame (columns `gen_<fuel>_mwh`)
- Produces: `def compute_intensity(df: pd.DataFrame, factors: EmissionFactors) -> pd.Series` — name `carbon_intensity_g_per_kwh`, same index as `df`

- [ ] **Step 1: Failing tests:**
  - `test_pure_coal_equals_coal_factor` (only `gen_col_mwh` > 0 → 820)
  - `test_half_coal_half_solar_is_mean` → (820+48)/2 = 434
  - `test_storage_and_unknown_excluded`
  - `test_zero_total_generation_is_nan`
  - `test_negative_generation_clipped_to_zero_for_weighting`
  - `test_bounded_by_min_and_max_factor` (random mixes, assert bounds)
  - `test_changing_factor_changes_output`
- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement** vectorised: clip included fuels at 0, weights = gen / row sum, intensity = Σ weights × EF; call `check_coverage` on the frame's fuel columns first.
- [ ] **Step 4: Run** → PASS
- [ ] **Step 5: Commit** `feat(carbon): generation-weighted carbon intensity`

### Task 3: `build-dataset` command and EDA

**Files:**
- Create: `src/carbon_scheduler/carbon/dataset.py`, `notebooks/01_eda.ipynb` (not tested), `docs/adr/0001-generation-based-intensity.md`
- Modify: `src/carbon_scheduler/cli.py` (add `build-dataset`)
- Test: `tests/carbon/test_dataset.py`

**Interfaces:**
- Produces:
  - `def build_dataset(region: str, settings: Settings, factors_path: Path = Path("config/emission_factors.yaml")) -> Path` — reads interim, appends `carbon_intensity_g_per_kwh`, writes processed; returns the path
  - CLI: `carbon-scheduler build-dataset --region CISO`

- [ ] **Step 1: Failing tests:** `test_build_dataset_adds_intensity_column_and_keeps_index`, `test_build_dataset_missing_interim_gives_actionable_error`, `test_build_dataset_is_idempotent`
- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS
- [ ] **Step 5: EDA notebook (manual):** plot daily/weekly profiles of demand and intensity, missingness heatmap, distribution of intensity by hour of day and season. Write 5–8 bullet findings at the top of the notebook (these feed feature ideas and the README).
- [ ] **Step 6: Write ADR 0001** (context D1, the formula, limitations: imports, storage, lifecycle vs combustion factors).
- [ ] **Step 7: Commit** `feat(carbon): build-dataset command, EDA notebook and ADR`

## Definition of Done

- [ ] `data/processed/CISO/hourly.parquet` has `carbon_intensity_g_per_kwh`, values plausible (CISO typically about 100–350 g/kWh; investigate anything outside)
- [ ] EDA findings written; ADR 0001 committed
- [ ] Quality gate green; master plan status updated
