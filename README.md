# UK School League Tables

A single-page ranking of every mainstream primary and secondary school in
England, computed from the Department for Education's annual performance
tables. The page is fully self-contained: open `index.html` in any browser
(including straight from the file system) and it works — no server, no build
step, no dependencies.

Coverage: **4,067 secondary** (KS4) and **15,056 primary** (KS2) schools.
Quick filters for Greater Manchester (10 boroughs) and Greater London (33
boroughs), plus an "All England" view; instant search by school name across
the full national dataset.

---

## Repository contents

| Path                       | Purpose                                                                      |
| -------------------------- | ---------------------------------------------------------------------------- |
| `index.html`               | The app. Open it in a browser. Contains the data inlined as JSON.            |
| `build_data.py`            | Pre-processor — turns the DfE CSVs into the inlined JSON and updates `index.html`. |
| `england_ks4final.csv`     | DfE raw secondary (KS4) performance table.                                   |
| `england_ks2final.csv`     | DfE raw primary (KS2) performance table.                                     |
| `data/secondary.json`      | Debug artifact — same payload that gets inlined into `index.html`.           |
| `data/primary.json`        | Debug artifact — same payload that gets inlined into `index.html`.           |

---

## Running the app

```sh
open index.html
```

That's it. The data is embedded in the file; no fetch, no server, no
dependencies. Everything runs locally in the browser.

---

## Updating the data with `build_data.py`

You only need to run this when the source DfE CSVs change (typically once a
year, when the new performance tables are published).

```sh
# 1. Download the latest DfE national CSVs and put them at the repo root:
#      england_ks4final.csv   (KS4 / secondary GCSE)
#      england_ks2final.csv   (KS2 / primary SATs)
#
# 2. Regenerate the inlined data + JSON artifacts:
python3 build_data.py
```

What it does:

1. **Reads** `england_ks4final.csv` and `england_ks2final.csv`.
2. **Filters** to mainstream schools (`RECTYPE == '1'`) with valid scores in
   every input metric. Suppression markers (`SUPP`, `NE`, `NP`, `..`) are
   treated as missing and drop the row.
3. **Classifies** each school: Grammar (selective admissions), Independent
   (private), or Non-selective; appends gender (Boys/Girls) and religious
   affiliation (RC/CofE/Jewish/Muslim/Hindu/Sikh/Methodist/Quaker) where
   present.
4. **Maps** the DfE LEA code to a borough/area name and tags Greater
   Manchester / Greater London / other.
5. **Computes** the ranking scores (see *Ranking algorithms* below).
6. **Writes** `data/secondary.json` + `data/primary.json` for inspection.
7. **Injects** both JSON payloads into `index.html` between marker comments
   (`<!-- BEGIN-DATA-SECONDARY -->` ... `<!-- END-DATA-SECONDARY -->`, and
   the same for `PRIMARY`). The HTML around the markers is untouched.

Requirements: Python 3 stdlib only. No `pip install` needed.

---

## Ranking algorithms

### Secondary — School Quality Score (SQS)

A single 0–∞ composite score where **100 = exactly the England average**.
Numbers above 100 mean above-average performance, scaled linearly.

```
SQS = (A8_norm     × 0.35)
    + (EM_norm     × 0.30)
    + (EBaccAPS_norm × 0.20)
    + (EBaccEnt_norm × 0.15)

where each _norm = (School value / England average) × 100
```

England averages used (DfE-published, 2024/25 data year):

| Metric       | England avg |
| ------------ | ----------- |
| Attainment 8 | 46.1        |
| Grade 5+ Eng & Maths | 45.4% |
| EBacc APS    | 4.09        |
| EBacc Entry  | 40.5%       |

Interpretation bands:

| SQS range  | Meaning            |
| ---------- | ------------------ |
| 180+       | Exceptional        |
| 160–179    | Outstanding        |
| 140–159    | Well above average |
| 120–139    | Above average      |
| < 120      | Near / below avg   |

### Primary — three percentile indices

KS2 doesn't have a single headline metric, so the page offers **three
different rankings**, selected via the "Rank by" dropdown. Each is scored
on a 0–100 scale where the England average sits around 49.

Inputs are **national percentiles** (rank against all ~15,000 England
primaries, midrank handling for ties): a percentile of 75 means the school
is ahead of 75% of primaries on that measure.

```
API (Academic Performance Index — default)
  = (Expected%ile × 0.40) + (Higher%ile × 0.40)
  + (Reading%ile × 0.10) + (Maths%ile   × 0.10)

GRI (Grammar School Readiness)
  = (Higher%ile  × 0.50) + (Reading%ile × 0.25) + (Maths%ile × 0.25)

11+ Readiness (within the school's own Local Authority)
  = (Higher_LA  × 0.50) + (Reading_LA  × 0.25) + (Maths_LA  × 0.25)
```

For 11+, each input is min-max normalised 0–100 **within the LA** instead
of nationally. LAs with fewer than 3 schools yield no 11+ score (the
normalisation isn't meaningful at that size).

Interpretation bands (apply to API / GRI / 11+ identically):

| Score range | Meaning            |
| ----------- | ------------------ |
| 80+         | Top tier           |
| 65–79       | Well above average |
| 50–64       | Above average      |
| 35–49       | Around / below avg |
| < 35        | Lower tier         |

---

## Reading the data columns

Every row in either table carries: school name, area (borough or town),
school type (e.g. "Grammar · Boys (CofE)"), the ranking score badge, and
four metric columns specific to the phase.

### Secondary table

| Column                | Field   | DfE source        | What it measures                                                                                       |
| --------------------- | ------- | ----------------- | ------------------------------------------------------------------------------------------------------ |
| **SQS ★**             | (computed) | — | Composite ranking score (see formula above). 100 = England average. Color-banded.                       |
| **Attainment 8**      | `a8`    | `ATT8SCR`         | Average GCSE point score across 8 subjects per pupil. Broadest headline measure.                       |
| **Gr.5+ Eng & Maths** | `em`    | `PTL2BASICS_95`   | % of pupils achieving Grade 5+ in BOTH English and Maths GCSE — the strong-pass benchmark.             |
| **EBacc APS**         | `aps`   | `EBACCAPS`        | Average point score across 5 EBacc pillars (English, Maths, sciences, humanities, language). Depth.    |
| **EBacc Entry**       | `ent`   | `PTEBACC_E_PTQ_EE`| % of pupils entered for the full EBacc combination. Signal of academic ambition.                       |

### Primary table

| Column                | Field   | DfE source        | What it measures                                                                                       |
| --------------------- | ------- | ----------------- | ------------------------------------------------------------------------------------------------------ |
| **API / GRI / 11+ ★** | (computed) | — | Selected index score (see formulas above). 0–100 scale. Color-banded.                                  |
| **RWM Expected**      | `rwm`   | `PTRWM_EXP`       | % of pupils reaching the expected standard in reading, writing AND maths combined. Breadth incl. writing. |
| **RWM Higher**        | `hs`    | `PTRWM_HIGH`      | % of pupils working at "greater depth" across all three. Stretch measure for the most able.            |
| **Reading SS**        | `read`  | `READ_AVERAGE`    | Average KS2 reading scaled score (typically 80–120, 100 = expected). Depth in literacy.                |
| **Maths SS**          | `maths` | `MAT_AVERAGE`     | Average KS2 maths scaled score (typically 80–120, 100 = expected). Depth in numeracy.                  |

### Internal fields (in the JSON, not visible on the page)

| Field        | Meaning                                                                              |
| ------------ | ------------------------------------------------------------------------------------ |
| `name`, `area`, `type`, `lea` | School name, borough/town, classification, DfE LEA code (3-digit).  |
| `region`     | One of `manchester`, `london`, `other` — drives the region-tab filter.               |
| `priv`       | Present and `true` for independent / non-maintained schools (KS4 only).              |
| `pe, ph, pr, pm` | National percentiles for RWM-expected / RWM-higher / reading SS / maths SS.      |
| `lh, lr, lm` | Per-LA min-max-normalised values (the 11+ Readiness inputs). `null` for tiny LAs.    |
| `_lc`        | Pre-lowercased name; populated at runtime to make the search filter allocation-free. |

---

## Data source and currency

DfE Performance Tables — England:
[https://www.gov.uk/government/collections/statistics-school-and-college-performance-tables](https://www.gov.uk/government/collections/statistics-school-and-college-performance-tables)

The CSV files in this repo are the published 2024/25 datasets (released in
the 2025 performance tables cycle). All percentile ranks and league
standings are computed against that snapshot.
