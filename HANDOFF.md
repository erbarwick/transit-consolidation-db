# Project Handoff & Maintenance Guide

This guide is for the **Transit Consolidation Database (SB1)** project. It explains how to add new consolidation cases, update datasets, rebuild the SQLite database (`transit.db`), and publish updates to the web viewer.

---

## 1. Quick Workflow Summary

```
                       ┌─────────────────────────┐
                       │   cases_metadata.csv    │ (Case list & event dates)
                       └────────────┬────────────┘
                                    │
                                    ▼
┌─────────────────────────┐   ┌───────────────┐   ┌──────────────────────────┐
│  Data Folder (e.g. data/)│──>│  build_db.py  │──>│ transit.db (Full, 430 MB)│
│  - CON-001/             │   │  (or R runner)│   │ transit_core.db (5.7 MB) │
│  - CON-002/             │   └───────────────┘   └─────────────┬────────────┘
│  - CON-017 [New case]   │                                     │
└─────────────────────────┘                                     ▼
                                                  ┌──────────────────────────┐
                                                  │ GitHub Pages Web Viewer  │
                                                  │ & GitHub Releases Asset  │
                                                  └──────────────────────────┘
```

---

## 2. How to Add a New Consolidation Case (4 Steps)

### Step 1: Add the Case to `cases_metadata.csv`
Open [`cases_metadata.csv`](cases_metadata.csv) in Excel, RStudio, or any text editor. Add a new row:

| Column | Example | Description |
|---|---|---|
| `case_id` | `CON-017` | Unique identifier. |
| `folder` | `Pierce Transit Merger (PT)` | Exact name of the case folder in the data directory. |
| `name` | `Pierce Transit (Agency A + Agency B -> Successor)` | Descriptive name. |
| `short_name` | `pierce` | Short lowercase slug. |
| `date` | `2018-07-01` | Date of legal consolidation (`YYYY-MM-DD`). |
| `year` | `2018` | Calendar year of consolidation (event year). |
| `predecessors` | `Agency A (NTD 12345); Agency B (NTD 67890)` | Predecessor agencies and NTD IDs. |
| `successor` | `Successor Agency (NTD 12345)` | Successor transit agency and NTD ID. |
| `alias` | *(optional)* | Any alternative candidate code (e.g., `CAND-009`). |

### Step 2: Create the Case Folder
1. Duplicate the [`_case_template`](_case_template/) folder.
2. Rename the new folder to match the `folder` column specified in `cases_metadata.csv`.
3. Move it into your source data directory (e.g. `data/`).

### Step 3: Add Data Files
Place raw files into the new case directory matching standard naming conventions:

* **In the case root directory:**
  * `*_ntd.xlsx`: NTD monthly ridership and service workbooks (sheets: `UPT`, `VRM`, `VRH`, `VOMS`).
  * `*_opexp.xlsx`: Annual operating expenses workbook (sheet: `OpExp`).
  * `*_annual_financial.xlsx`: Annual NTD financial forms (sheet: `Annual_Metrics`).
* **In the `ACS/` subfolder:**
  * `*_data_long.csv`: ACS 5-Year estimates (long format).
  * `*_codebook.csv`: ACS variable codebook.
  * `*_wide_by_code.csv`: Wide ACS profile tables (DP02, DP03, DP04, DP05).
* **In the `LEHD/` subfolder:**
  * `*_lodes_*.csv`: LEHD LODES annual workplace employment.
  * `*_qwi_*.csv` (or `.xlsx`): Quarterly Workforce Indicators.
* **In the `Combined Data/` subfolder (Optional):**
  * `*master_panel*.xlsx`: Human-curated annual master panel workbook (sheet: `Panel_Annual`).
  *(Note: If no manual panel is provided, the pipeline automatically synthesizes all master panel rows from the raw tables!)*

### Step 4: Rebuild the Database

Choose whichever method matches your team's workflow:

#### Method A: In RStudio (Recommended for R users)
Open the project in RStudio and run:
```r
source("build_db.R")
```
*(This automatically runs the pipeline, rebuilds `transit.db`, and executes verification checks).*

#### Method B: In Terminal
```bash
python build_db.py path/to/data -o transit.db --force
```

#### Method C: On GitHub (Zero Local Setup)
Go to the repository on GitHub -> **Actions** -> **Rebuild Transit Database** -> click **Run workflow**.

---

## 3. Verifying Database Integrity

Always run [`check_coverage.py`](check_coverage.py) after updating or adding data:

```bash
python check_coverage.py transit.db path/to/data
```

This verifies 5 critical data integrity checks:
1. **Load log row counts:** Verifies every sheet loaded into SQLite matches logged counts.
2. **Error audit:** Flags any skipped, malformed, or unrecognized files.
3. **CSV line counts:** Verifies raw CSV row counts match database rows.
4. **Key uniqueness:** Ensures no duplicate case-year pairs exist in `master_panel`.
5. **Source alignment:** Compares synthesized `master_panel` values against source tables (`manual_master_panel` and `lodes`).

---

## 4. Querying the Database in R

To analyze data directly in R without exporting CSV files:

```r
library(DBI)
library(RSQLite)

# 1. Connect to SQLite database
con <- dbConnect(RSQLite::SQLite(), "transit.db")

# 2. Inspect available tables
dbListTables(con)

# 3. Pull the master research panel into an R data.frame
df <- dbGetQuery(con, "
  SELECT 
    case_id, 
    year, 
    event_time, 
    phase, 
    ntd_upt_cal_all AS ridership, 
    opexp_ry_usd AS opexp_usd, 
    lodes_jobs_total AS jobs
  FROM master_panel
  WHERE event_time BETWEEN -3 AND 3
  ORDER BY case_id, year
")

# 4. Always close connection when finished
dbDisconnect(con)

# Inspect in R
head(df)
```

---

## 5. Web Viewer & Releases Architecture

* **Web Viewer (Inloop SQLite Viewer on GitHub Pages):**
  * Hosted at `https://erbarwick.github.io/transit-consolidation-db/`
  * Reads `docs/data/transit_core.db` (5.7 MB, containing all 24 core research tables).
  * Automatically updated whenever `build_db.py` runs with default `--export-docs docs/data`.
* **Full Database Releases (GitHub Releases):**
  * Hosted at `https://github.com/erbarwick/transit-consolidation-db/releases/latest`
  * Contains the full uncompressed `transit.db` (430 MB, including all 368,000 raw ACS long records) and `transit.db.gz` (27 MB).
