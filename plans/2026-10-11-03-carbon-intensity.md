# 03 Carbon Intensity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn per-fuel hourly generation into a documented, tested `carbon_intensity_g_per_kwh` series and a processed dataset ready for modelling.

**Architecture:** Emission factors live in a validated YAML file; a pure function computes generation-weighted intensity; a `build-dataset` step reads interim data, adds the series and writes processed data.

**Tech Stack:** pandas, pyyaml, pydantic (factor schema).

**Spec:** `specs/2026-10-11-carbon-aware-scheduler-design.md` (decision D1)

## Global Constraints

- Intensity unit gCO2e/kWh; generation unit MWh (ratio is unit-consistent)
- Generation-based proxy: `Σ(observed positive gen_f × EF_f) / Σ observed positive gen_f` over covered fuel columns. Missing observations stay missing; partial observed mixes are computed with explicit coverage/missing diagnostics, while all-missing or zero included generation yields NaN. Imports are ignored.
- Exclude storage and integrated storage codes `bat`, `ps`, `snb`, `wnb`, `oes`, unknown/ambiguous `ues`, `unk`, and heterogeneous/confidential `oth`, from numerator and denominator. Do not assign biomass to `oth`.
- Source-verified factors: IPCC AR5 WGIII Annex III Table A.III.2 lifecycle medians (coal 820, gas 490, nuclear 12, utility PV 48, onshore wind 11, hydro 24, geothermal 38). Oil 650 is separately attributed to POSTnote 268 (2006), p. 2, a historical UK average proxy, not an IPCC median. Dedicated biomass 230 has no separate confirmed EIA-930 code and is not mapped.
- Gate per task: ruff, format check, mypy, pytest; Conventional Commits

## Review Focus

- A fuel code in the data with no factor and not in the exclusion list → loud error, never silently zero
- Hour with zero or all-missing included generation → NaN intensity, not 0 or inf; a partial observed mix is accompanied by diagnostics, never labelled complete
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
  - `def load_emission_factors(path: Path) -> EmissionFactors` — relative paths resolve from project root; keys are lower-case fuel identifiers. Validation: finite non-boolean values > 0, nonempty source, no key both in `factors` and `excluded`; frozen data cannot be mutated through the mapping.
  - `def check_coverage(factors: EmissionFactors, fuel_codes: Iterable[str]) -> None` raising `UnknownFuelError` listing the uncovered codes

- [x] **Step 1: Failing tests:** `test_loads_valid_file`, `test_rejects_non_positive_factor`, `test_rejects_overlap_between_factors_and_excluded`, `test_unknown_fuel_raises_and_names_code`
- [x] **Step 2: Run:** `uv run pytest tests/carbon/test_factors.py -v` → FAIL
- [x] **Step 3: Implement.** YAML includes `source:` (citations for IPCC AR5 WGIII Annex III and the separately sourced oil proxy) and a comment on each value. **Manual check:** open the cited table and confirm each number; fix the file if any differs.
- [x] **Step 4: Run** → PASS
- [x] **Step 5: Commit** `feat(carbon): emission factors config and loader`

Task 1 verification: inspected the final published IPCC PDF, printed p. 1335
(PDF page 7), Table A.III.2 and footnotes. All seven configured IPCC medians match;
oil is absent from that table and is explicitly sourced from POSTnote 268 p. 2.
Biomass 230 applies to dedicated energy crops/residues and is not assigned to OTH.
Recorded RED before implementation, then 20 factor tests passed; full local gate
112 passed, one live test deselected, 97.18% coverage. Spec review passed.

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
- [ ] **Step 3: Implement** vectorised: clip observed included fuels at 0, weights = gen / row sum (`min_count=1`), intensity = Σ weights × EF; call `check_coverage` on all frame fuel columns first. Reject infinite/non-numeric generation; preserve input and index. Partial missing mixes use observed values, not inferred zero; all-missing/zero/no-included mixes return float NaN.
- [ ] **Step 4: Run** → PASS
- [ ] **Step 5: Commit** `feat(carbon): generation-weighted carbon intensity`

### Task 3: `build-dataset` command and EDA

**Files:**
- Create: `src/carbon_scheduler/carbon/dataset.py`, `notebooks/01_eda.ipynb` (not tested), `docs/adr/0001-generation-based-intensity.md`
- Modify: `src/carbon_scheduler/cli.py` (add `build-dataset`)
- Test: `tests/carbon/test_dataset.py`

**Interfaces:**
- Produces:
  - `def build_dataset(region: str, settings: Settings, factors_path: Path = Path("config/emission_factors.yaml")) -> Path` — reads interim, appends `carbon_intensity_g_per_kwh`, writes processed; returns the path. Also appends `carbon_covered_generation_mwh`, `carbon_excluded_generation_mwh`, `carbon_observed_coverage_fraction` (covered / total observed positive fuel generation), `carbon_missing_fuel_count` (missing cells in present included fuel columns), and `carbon_negative_generation_count` (negative observed fuel cells clipped for positive-generation weighting). Observed coverage is not coverage of true unobserved generation. Writes a carbon quality/provenance report with factors, source, included/excluded codes, aggregate diagnostics and input/factors digests; identical reruns preserve bytes. Relative factors paths resolve from project root. No API key required.
  - CLI: `carbon-scheduler build-dataset --region CISO`

- [ ] **Step 1: Failing tests:** `test_build_dataset_adds_intensity_column_and_keeps_index`, `test_build_dataset_missing_interim_gives_actionable_error`, `test_build_dataset_is_idempotent`
- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS
- [ ] **Step 5: EDA notebook (manual):** plot daily/weekly profiles of demand and intensity, missingness heatmap, distribution of intensity by hour of day and season. Use local region time for calendar profiles, UTC storage unchanged. Write 5–8 measured bullet findings at the top; execute every cell on real processed data and inspect rendered figures. Add a locked optional `eda` dependency group for matplotlib and notebook execution.
- [ ] **Step 6: Write ADR 0001** (context D1, the formula, limitations: imports, storage, lifecycle vs combustion factors).
- [ ] **Step 7: Commit** `feat(carbon): build-dataset command, EDA notebook and ADR`

## Definition of Done

- [ ] `data/processed/CISO/hourly.parquet` has `carbon_intensity_g_per_kwh`, values plausible (CISO typically about 100–350 g/kWh; investigate anything outside)
- [ ] EDA findings written; ADR 0001 committed
- [ ] Quality gate green; master plan status updated
