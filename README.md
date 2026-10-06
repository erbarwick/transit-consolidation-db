# Transit Consolidation Database

This repo contains the data pipeline and verification tools to ingest raw case files, NTD reporting, and Census/LEHD data into a unified SQLite database (`transit.db`).

---

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## Building the Database

To rebuild `transit.db` from the source data folder:

```bash
python build_db.py path/to/data -o transit.db --force
```

### Pipeline Overview (`build_db.py`)
- Reads the 14 case directories (`CON-001` through `CON-016`).
- Standardizes column names across agency spreadsheets and NTD reports.
- Ingests demographic data (ACS 5-Year estimates, LEHD LODES, QWI).
- Ingests operational data (NTD monthly metrics, NTD annual totals, operating expenses).
- Ingests researcher-curated panels into `manual_master_panel`.
- Constructs a balanced master panel (`master_panel`) for all 14 cases from 2000 to 2026.
- Adds an autoincrementing primary key (`id`) and indices to tables.
- Records all processed files and sheet counts in `load_log`.

---

## Data Verification

To run consistency and coverage checks against the built database:

```bash
python check_coverage.py transit.db path/to/data
```

This verifies:
1. Row counts in `load_log` match table counts.
2. Unhandled or failed files/sheets.
3. CSV source row counts vs. loaded database rows.
4. Key constraints and coverage ranges in `master_panel`.
5. Exact values in `master_panel` against source tables (`manual_master_panel`, `lodes`).

---

## Local Web Interface (`sqlite_web`)

To browse and query `transit.db` in a browser:

```bash
sqlite_web transit.db
```

For read-only mode (prevents accidental edits):
```bash
sqlite_web transit.db -r
```

By default the interface runs at `http://127.0.0.1:8080`. If port 8080 is in use:
```bash
sqlite_web transit.db -p 8081
```

Features:
- **Left sidebar:** Table browser and schema viewer.
- **Content:** Paginated table view with column sorting and filtering.
- **Query:** SQL editor with direct execution and CSV export.

---

## Database Tables

### Master Panels
| Table | Description | Scope |
|---|---|---|
| `master_panel` | Standardized research panel across all 14 cases from 2000 to 2026. Includes event timing (`event_time`, `phase`, `post`), annual ridership (UPT), vehicle revenue miles (VRM), operating expenses, jobs, and demographics. | 378 rows (14 cases × 27 years) |
| `manual_master_panel` | Stacked annual master panels curated by the research team for the 10 documented cases (`is_human_verified = 1`). | 183 rows |

### Case Metadata & Documentation
| Table | Description | Key Columns |
|---|---|---|
| `cases` | Metadata for all 14 consolidation cases. | `case_id`, `case_name`, `consolidation_date`, `event_year`, `predecessor_agencies`, `successor` |
| `case_folders` | Mapping between source folder names and case IDs. | `case_id`, `folder`, `short_name`, `event_year` |
| `field_definitions` | Variable descriptions and sources. | `sheet_name`, `column_name`, `description`, `source` |
| `reporter_type_flags` | NTD reporter status by agency and year. | `case_id`, `agency_name`, `year`, `reporter_type`, `reduced_reporter` |
| `case_risk_summary` | Reporting anomaly and data discontinuity notes. | `case_id`, `risk_level`, `risk_description` |
| `load_log` | Ingestion log for every source file and sheet. | `source_file`, `source_sheet`, `table_name`, `rows`, `status` |
| `sheet_notes` | Header notes extracted from source spreadsheets. | `case_id`, `source_file`, `source_sheet`, `line`, `text` |

### Transit Operations & Finance
| Table | Description | Key Columns / Metrics |
|---|---|---|
| `ntd_monthly` | Monthly ridership and service in long format. | `metric` (UPT, VRM, VRH, VOMS), `month`, `value`, `mode` |
| `ntd_annual` | Annual NTD service totals. | `case_id`, `agency`, `year`, mode totals |
| `ntd_info` | NTD agency metadata. | Agency IDs, names, reporting notes |
| `opexp` | Annual operating expenses in nominal USD. | Agency expense rows across study window |
| `annual_financial` | Financial breakdowns from NTD annual forms. | Operating expense functions, fare revenues, capital expenses |
| `annual_financial_info` | Metadata for annual financial workbooks. | Agency and year identifiers |

### Demographics & Regional Employment
| Table | Description | Details |
|---|---|---|
| `lodes` | Census LEHD annual workplace employment. | Total jobs, age brackets, earnings tiers, 20 NAICS industries |
| `qwi` | Census Quarterly Workforce Indicators. | Quarterly employment, accessions, separations, payroll |
| `acs_long` | Full ACS 5-Year estimates in long format (2009–2023). | `table_id`, `line`, `label_full`, `stat_type`, `value` |
| `acs_codebook` | ACS variable reference dictionary. | Table metadata and variable labels |
| `acs_wide_dp02` | ACS DP02: Selected Social Characteristics. | Education, household types, disability |
| `acs_wide_dp03` | ACS DP03: Selected Economic Characteristics. | Income, poverty, commuting mode |
| `acs_wide_dp04` | ACS DP04: Selected Housing Characteristics. | Tenure, vehicles available, gross rent |
| `acs_wide_dp05` | ACS DP05: Demographic and Housing Estimates. | Age cohorts, race, Hispanic origin |

---

## Example Queries

### 1. Case Roster and Consolidation Dates
```sql
SELECT 
    case_id,
    case_name,
    consolidation_date,
    event_year,
    predecessor_agencies,
    successor
FROM cases
ORDER BY event_year ASC;
```

### 2. Ridership and Expenses Around Consolidation Window
```sql
SELECT 
    case_id,
    year,
    event_time,
    phase,
    ntd_upt_cal_all AS annual_ridership,
    opexp_ry_usd AS operating_expenses_usd,
    lodes_jobs_total AS regional_jobs
FROM master_panel
WHERE event_time BETWEEN -3 AND 3
ORDER BY case_id, year;
```

### 3. Comparing Manual Panel Values to Synthesized Values
```sql
SELECT 
    m.case_id,
    m.year,
    m.phase,
    m.ntd_upt_cal_all AS master_ridership,
    h.ntd_upt_cal_all AS manual_ridership,
    m.opexp_ry_usd AS master_opexp,
    h.opexp_ry_usd AS manual_opexp
FROM master_panel m
JOIN manual_master_panel h ON h.case_id = m.case_id AND h.year = m.year
WHERE m.case_id = 'CON-011'
ORDER BY m.year;
```

### 4. Operating Cost per Passenger Trip
```sql
SELECT 
    case_id,
    year,
    phase,
    event_time,
    ROUND(opexp_ry_usd / NULLIF(ntd_upt_cal_all, 0), 2) AS cost_per_trip_usd,
    ntd_upt_cal_all AS total_trips,
    opexp_ry_usd AS total_operating_cost
FROM master_panel
WHERE ntd_upt_cal_all > 0 AND opexp_ry_usd > 0
ORDER BY case_id, year;
```

### 5. Monthly Ridership Trend for a Single Case
```sql
SELECT 
    month,
    SUM(value) AS monthly_ridership
FROM ntd_monthly
WHERE case_id = 'CON-001' AND metric = 'UPT'
GROUP BY month
ORDER BY month ASC;
```

### 6. Demographic Indicators by Case-Year
```sql
SELECT 
    case_id,
    year,
    acs_pop AS total_population,
    acs_med_hh_income AS median_household_income,
    acs_pct_poverty AS poverty_rate_pct,
    acs_pct_renter AS renter_pct
FROM master_panel
WHERE acs_pop IS NOT NULL
ORDER BY case_id, year;
```

### 7. Source Coverage Audit by Case
```sql
SELECT 
    case_id,
    COUNT(CASE WHEN has_ntd_monthly = 1 THEN 1 END) AS years_with_monthly_ntd,
    COUNT(CASE WHEN has_opexp = 1 THEN 1 END) AS years_with_opexp,
    COUNT(CASE WHEN has_lodes = 1 THEN 1 END) AS years_with_lodes,
    COUNT(CASE WHEN has_qwi = 1 THEN 1 END) AS years_with_qwi,
    COUNT(CASE WHEN has_acs = 1 THEN 1 END) AS years_with_acs,
    COUNT(CASE WHEN is_human_verified = 1 THEN 1 END) AS human_verified_years,
    COUNT(*) AS total_panel_years
FROM master_panel
GROUP BY case_id
ORDER BY case_id;
```

---

## Direct Database Access

### Python (`pandas`)
```python
import sqlite3
import pandas as pd

con = sqlite3.connect("transit.db")
df = pd.read_sql("SELECT * FROM master_panel", con)
con.close()
```

### R
```R
library(DBI)
library(RSQLite)

con <- dbConnect(RSQLite::SQLite(), "transit.db")
panel <- dbGetQuery(con, "SELECT * FROM master_panel WHERE event_time BETWEEN -5 AND 5")
dbDisconnect(con)
```

### Stata
Export the query result to CSV via `sqlite_web` or a script, then import:
```stata
import delimited "master_panel.csv", clear
```