# Transit Consolidation Research Database

Welcome to the **Transit Consolidation Database** project! This repository contains the data pipeline, schema definitions, and analysis tools for a nationwide study examining public transit agency consolidations (mergers) across 14 cases in the United States.

All source spreadsheets and CSV files created and collected by the research team are harmonized and funneled into a single, unified SQLite database (`transit.db`). You can inspect, query, edit, and export everything using a simple web interface (`sqlite_web`) or connect directly from R, Stata, or Python.

---

## Table of Contents
1. [Beginner Setup Guide](#1-beginner-setup-guide)
2. [Building the Database](#2-building-the-database)
3. [Exploring Data with the Web App (`sqlite_web`)](#3-exploring-data-with-the-web-app-sqlite_web)
4. [Database Structure & Table Guide](#4-database-structure--table-guide)
5. [Research SQL Recipes (Copy-and-Paste Queries)](#5-research-sql-recipes)
6. [Using the Database in R, Stata, or Python](#6-using-the-database-in-r-stata-or-python)
7. [Troubleshooting & FAQ](#7-troubleshooting--faq)

---

## 1. Beginner Setup Guide

> **Note for Research Students:** If you haven't used command line tools or Python virtual environments before, don't worry! Follow these steps in order. You only need to do the setup once.

### What is a Virtual Environment?
When working with Python, different projects may need different packages. A **virtual environment** is simply a dedicated, self-contained folder (usually named `.venv`) where Python packages are installed just for this project, keeping your computer tidy.

### Step-by-Step Installation:

1. **Open your IDE terminal:**
   - In **VS Code**: Go to the top menu -> `Terminal` -> `New Terminal`.
   - In **PyCharm**: Click the `Terminal` tab at the bottom.
   - On **Mac**: You can also use the `Terminal` app and navigate to the project folder.

2. **Create your virtual environment:**
   ```bash
   python3 -m venv .venv
   ```
   *(On Windows, you may type `python -m venv .venv`)*

3. **Activate the virtual environment:**
   - **Mac / Linux:**
     ```bash
     source .venv/bin/activate
     ```
   - **Windows (Command Prompt):**
     ```cmd
     .venv\Scripts\activate.bat
     ```
   - **Windows (PowerShell):**
     ```powershell
     .venv\Scripts\Activate.ps1
     ```
   *(When active, you will see `(.venv)` appear at the start of your terminal line.)*

4. **Install the required packages:**
   ```bash
   pip install -r requirements.txt
   ```
   This installs `pandas`, `openpyxl`, and `sqlite-web`.

---

## 2. Building the Database

Whenever new source files are added or updated in the `data/` folder, run the build script to recreate `transit.db`:

```bash
python build_db.py path/to/data -o transit.db --force
```

### What `build_db.py` does:
- Scans all 14 case directories (e.g., `CON-001` through `CON-016`).
- Cleans and standardizes column headers across different agencies and formats.
- Loads demographic data (ACS 5-Year Estimates, LODES, QWI).
- Loads ridership and operations data (NTD Monthly, NTD Annual, Operating Expenses).
- Records all human-curated panels into `manual_master_panel`.
- Synthesizes the master time-series panel (`master_panel`) for **all 14 cases** spanning 2000–2026.
- Automatically adds an `id PRIMARY KEY` to every table so you can edit and sort easily.

### Verifying Database Quality:
To check that all files and rows loaded accurately without missing data:
```bash
python check_coverage.py transit.db path/to/data
```

---

## 3. Exploring Data with the Web App (`sqlite_web`)

You do not need to install complex database software! We use **`sqlite_web`**, a lightweight web browser tool that runs locally on your machine.

### Starting the Web App:
In your activated terminal, run:
```bash
sqlite_web transit.db
```
*(Tip: To prevent accidental edits while browsing, add `-r` for read-only mode: `sqlite_web transit.db -r`)*

Once started, open your web browser (Chrome, Safari, Firefox, Edge) and go to:
👉 **`http://127.0.0.1:8080`**

### What You Can Do in the Web App:
- **Left Sidebar:** Lists all tables in the database. Click any table name to open it.
- **Content Tab:** Displays the spreadsheet-like grid of rows. You can click any column header to sort ascending/descending, or use the filter boxes at the top to search for a specific case (e.g., `CON-011`) or year.
- **Query Tab:** A full SQL console where you can type or paste SQL queries, click **Execute**, and view results immediately.
- **Export to CSV:** In the Content or Query tab, click **Export CSV** to download the data directly into Microsoft Excel or Google Sheets.
- **To Stop the Web App:** Go back to your terminal window and press `Ctrl + C`.

---

## 4. Database Structure & Table Guide

The database organizes data into four clear tiers:

### Tier 1: Master Summary Panels (Best for Cross-Case Analysis)
| Table Name | Description | Rows & Scope |
|---|---|---|
| **`master_panel`** | **Primary research panel.** Standardized time-series covering all 14 cases from 2000 to 2026 (378 rows). Contains event timing (`event_time`, `phase`, `post`), annual ridership (UPT), vehicle revenue miles (VRM), operating expenses, jobs, and demographic indicators. | 378 rows (14 cases × 27 years) |
| **`manual_master_panel`** | **Human-curated panel.** Stacks all human-written annual master panels created by research team members for the 10 documented cases. Includes `is_human_verified = 1`. | 183 rows |

### Tier 2: Case Metadata & Classification
| Table Name | Description | Key Columns |
|---|---|---|
| **`cases`** | Metadata on all 14 consolidation cases. | `case_id`, `case_name`, `consolidation_date`, `event_year`, `predecessor_agencies`, `successor` |
| **`case_folders`** | Mapping between folder names and case IDs. | `case_id`, `folder`, `short_name`, `event_year` |
| **`field_definitions`** | Master codebook defining variable names and descriptions. | `sheet_name`, `column_name`, `description`, `source` |
| **`reporter_type_flags`** | NTD reporter status by year (Full Reporter vs Reduced vs Rural). | `case_id`, `agency_name`, `year`, `reporter_type`, `reduced_reporter` |
| **`case_risk_summary`** | Risk assessments for potential data reporting artifacts. | `case_id`, `risk_level`, `risk_description` |
| **`load_log`** | Audit trail of every single file/sheet loaded into the database. | `source_file`, `table_name`, `rows`, `status` |

### Tier 3: Core Transit Operations Data
| Table Name | Description | Key Details |
|---|---|---|
| **`ntd_monthly`** | Monthly ridership and service melted to long format: `(metric, month, value)`. | Metrics: `UPT` (unlinked passenger trips), `VRM` (vehicle miles), `VRH` (vehicle hours), `VOMS` (vehicles in max service). |
| **`ntd_annual`** | Annual NTD service totals for predecessor and rural transit agencies. | Calendar/fiscal year totals by agency and mode. |
| **`opexp`** | Annual operating expenses in nominal USD ($) across the 10-year study window. | Year-by-year expenses for predecessors and merged agencies. |
| **`annual_financial`** | Detailed 27-metric financial breakdown from NTD financial workbooks. | Operating expenses by function (vehicle ops, maintenance, admin), fare revenues, capital expenditures. |

### Tier 4: Regional Demographics & Employment
| Table Name | Description | Key Details |
|---|---|---|
| **`lodes`** | Census LEHD annual workplace employment. | Total jobs, age brackets, earnings tiers, 20 NAICS industries. |
| **`qwi`** | Census Quarterly Workforce Indicators. | Harmonized quarterly employment, hires, separations, payroll. |
| **`acs_long`** | Full ACS 5-Year estimates in clean long format. | 367,000+ demographic data points covering 2009–2023. |
| **`acs_wide_dp02`** | ACS Social Characteristics (education, households, disability). | ~920 columns per case/year. |
| **`acs_wide_dp03`** | ACS Economic Characteristics (income, poverty, commute mode). | ~820 columns per case/year. |
| **`acs_wide_dp04`** | ACS Housing Characteristics (renters, vehicles available, rent). | ~860 columns per case/year. |
| **`acs_wide_dp05`** | ACS Demographic & Age Profile (race, Hispanic origin, age groups). | ~540 columns per case/year. |

---

## 5. Research SQL Recipes

Copy and paste these queries into the **Query** tab in `sqlite_web` to immediately inspect the research data:

### Recipe 1: Master Roster of Consolidation Cases
*See all 14 cases, when they consolidated, and the agencies involved:*
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

---

### Recipe 2: Ridership Trends Around Consolidation Event Window
*Analyze annual ridership (UPT) and operating expenses from 3 years before to 3 years after consolidation (`event_time = 0` is the consolidation year):*
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

---

### Recipe 3: Comparing Human-Curated vs Synthesized Values
*Verify how closely synthesized numbers match the researcher's manual master panel:*
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
WHERE m.case_id = 'CON-011' -- Sacramento Regional Transit (SacRT)
ORDER BY m.year;
```

---

### Recipe 4: Operating Cost Efficiency (Cost per Passenger Trip)
*Compute cost per passenger trip across pre-merger vs post-merger phases:*
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

---

### Recipe 5: Monthly Ridership Seasonality Before and After Consolidation
*Look at monthly ridership numbers from `ntd_monthly` for a specific case:*
```sql
SELECT 
    month,
    SUM(value) AS monthly_ridership
FROM ntd_monthly
WHERE case_id = 'CON-001' AND metric = 'UPT'
GROUP BY month
ORDER BY month ASC;
```

---

### Recipe 6: Demographic Profile of Service Areas
*Compare poverty rate, median household income, and renter percentage:*
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

---

### Recipe 7: Data Availability & Coverage Audit
*Check which data sources are populated for each case across all years:*
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

## 6. Using the Database in R, Stata, or Python

Because SQLite is an open standard, you can query `transit.db` directly from your favorite analysis environment without exporting CSVs:

### In R:
```R
library(DBI)
library(RSQLite)

# Connect to database
con <- dbConnect(RSQLite::SQLite(), "transit.db")

# Query into an R data.frame
panel <- dbGetQuery(con, "SELECT * FROM master_panel WHERE event_time BETWEEN -5 AND 5")

# Close connection when finished
dbDisconnect(con)
```

### In Python (pandas):
```python
import sqlite3
import pandas as pd

con = sqlite3.connect("transit.db")
df = pd.read_sql("SELECT * FROM master_panel", con)
con.close()
```

### In Stata:
You can export any query result directly from `sqlite_web` as a CSV by clicking **Export CSV**, and load it into Stata:
```stata
import delimited "master_panel.csv", clear
```

---

## 7. Troubleshooting & FAQ

#### Q: I get `command not found: python3` or `python`
- On Mac, open Terminal and check `which python3` or install Python via [python.org](https://www.python.org/downloads/).
- On Windows, make sure you checked "Add Python to PATH" when installing Python.

#### Q: I get `ModuleNotFoundError: No module named 'sqlite_web'`
- Make sure your virtual environment is active! You should see `(.venv)` in your terminal prompt.
- Run `pip install -r requirements.txt`.

#### Q: Port 8080 is already in use when launching `sqlite_web`
- Specify a different port using `-p`:
  ```bash
  sqlite_web transit.db -p 8081
  ```
  Then open `http://127.0.0.1:8081` in your browser.

#### Q: How do I undo accidental changes to the database?
- Simply re-run `python build_db.py path/to/data -o transit.db --force` to instantly regenerate a clean database from the original source files.

---

*Need help or found a data discrepancy? Contact the research team lead or open an issue in the project repository.*