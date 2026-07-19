# Real-Data Onboarding Guide
_For a teammate adding the first real indicator file. Time to first output: ~10 minutes._

---

## What the pipeline expects

Each indicator is a **tidy CSV** with exactly three columns:

```
district_id,value,year
```

| Column | Type | Meaning |
|--------|------|---------|
| `district_id` | string / integer | The `dt_code` from the 2011 Census GeoJSON — the canonical join key. Find valid values in `pipeline/crosswalk/district_crosswalk.csv` column `canonical_district_id`. |
| `value` | number | The indicator value for that district in that year. Leave blank (empty field) if missing — the pipeline imputes. |
| `year` | integer | One of `2011`, `2016`, `2021`. Include all three years if available; the pipeline uses 2011 as the base year and 2016/2021 for CAGR forecasting. |

**One row = one (district, year) observation.** A file with 710 districts × 3 years = 2130 rows.

---

## Filled example — `health_insurance_cov` (NFHS-5)

```
district_id,value,year
168,34.7,2021
168,21.3,2016
168,8.9,2011
271,12.4,2021
271,7.1,2016
271,2.8,2011
495,67.2,2021
...
```

`168` = Hamirpur (Uttar Pradesh), `271` = Peren (Nagaland). Values are the indicator measurement for that district-year. Missing values are left as empty:

```
495,,2011
```

---

## Step-by-step: adding one indicator

### Step 1 — Reconcile your district names

Your data source (NFHS-5, NHP, Census) probably uses different district-name spellings than the 2011 Census GeoJSON. Run the reconciler first:

```bash
python pipeline/crosswalk/reconcile.py \
    your_raw_data.csv \
    --name-col district_name \
    --output pipeline/config/reconciliation_<source>.md
```

This outputs exact matches, fuzzy matches (inspect these!), and a `manual_overrides.csv` snippet for anything unmatched. Fix names before building your CSV.

### Step 2 — Drop the CSV file

Place your CSV at the path listed in `index_config.yaml` for that indicator:

```
pipeline/raw/indicators/<indicator_id>.csv
```

Example: `pipeline/raw/indicators/health_insurance_cov.csv`

Use the template as a starting point:

```
pipeline/raw/templates/health_insurance_cov_TEMPLATE.csv
```

The template has the correct headers and 3 sample district rows pre-filled. Paste your values into the `value` column for each `district_id × year` row.

### Step 3 — Flip status to READY

Open `pipeline/config/index_config.yaml`. Find the indicator block and change `status: TODO` to `status: READY`:

```yaml
- id: health_insurance_cov
  label: "Health insurance / Ayushman coverage (%)"
  ...
  status: READY        # ← change this line
```

### Step 4 — Rerun the pipeline

```bash
python pipeline/run_pipeline.py
```

The pipeline runs a preflight check on startup — if your file is missing or the config is invalid it will say so clearly. On success it writes `data/scores.json` and `data/clusters.json`.

### Step 5 — Verify

Check `pipeline/reports/output/join_coverage.md` for the indicator's district coverage, and `pipeline/reports/output/missingness.md` for imputation rates. Acceptable: < 20% missing before imputation.

---

## District name reconciliation (critical for real data)

**Real data sources use different spellings.** NFHS-5 uses its own district list; NHP uses another. Do not skip Step 1. Examples of mismatches the reconciler handles:

| Source name | Canonical name | Match type |
|-------------|----------------|------------|
| West Kameng | West Kameng | exact |
| Bangalore Urban | Bengaluru Urban | fuzzy (92) |
| Bilaspur (HP) | Bilaspur | fuzzy (85) |
| Lahaul-Spiti | Lahaul and Spiti | fuzzy (88) |

Matches below 80 confidence go into the unmatched list — add those to `pipeline/config/manual_overrides.csv`.

---

## Template files

Ready-to-fill templates for all 12 indicators are in `pipeline/raw/templates/`. Each template has:
- Correct CSV headers
- 3 pre-filled sample `district_id` rows (Hamirpur/168, Peren/271, Daman/495)
- Year rows for 2011, 2016, 2021

| Template file | Indicator | Source to check |
|--------------|-----------|-----------------|
| `pop_elderly_pct_TEMPLATE.csv` | Population 60+ (%) | Census 2011 / SRS |
| `chronic_disease_prev_TEMPLATE.csv` | Chronic disease prevalence | NFHS-5 |
| `hosp_bed_density_TEMPLATE.csv` | Hospital beds per 10k | NHP / HMIS 2022 |
| `per_capita_nsdp_TEMPLATE.csv` | Per-capita NSDP (₹) | RBI / MoSPI |
| `health_insurance_cov_TEMPLATE.csv` | Health insurance coverage | NFHS-5 |
| `oope_pct_hhexp_TEMPLATE.csv` | OOPE as % HH expenditure | NFHS-5 / NSS |
| `pharmacy_density_TEMPLATE.csv` | Pharmacies per 100k | Drug Controller / NHP |
| `road_connectivity_TEMPLATE.csv` | Road connectivity index | PMGSY / MoRD |
| `urban_pop_pct_TEMPLATE.csv` | Urban population (%) | Census 2011 |
| `pop_growth_rate_TEMPLATE.csv` | Population CAGR 2001–2011 | Census 2001 & 2011 |
| `health_infra_growth_TEMPLATE.csv` | Health infrastructure growth | HMIS / Rural Health Stats |
| `literacy_rate_TEMPLATE.csv` | Effective literacy rate | Census 2011 |

---

## What happens to missing values

The pipeline imputes in order:
1. **Hierarchical fallback** — fully-missing districts get the state median.
2. **KNN (k=5)** — partial missing filled from 5 nearest-neighbour districts.
3. **MICE pass** — one IterativeImputer pass to sharpen estimates.

After imputation, 0% missing is expected. Check `missingness.md` to confirm.

---

## FAQ

**Q: My source has only 2021 data, not 2011 or 2016.**  
A: Include only 2021 rows. The CAGR forecast will be less reliable (flat extrapolation) but the current-year score is unaffected. Note this in the indicator's `notes:` field in the config.

**Q: My source uses state-level data, not district-level.**  
A: Do not use it directly. State data disaggregated to districts can bias results. Flag in the config comment and seek district-level alternatives.

**Q: I have district data but no dt_code.**  
A: Run `reconcile.py` with the district names column. It will match names to `dt_code` via the crosswalk.

**Q: The pipeline fails on startup.**  
A: It runs a preflight check. Read the error message — it will say exactly which indicator file is missing or which weights don't sum to 1.
