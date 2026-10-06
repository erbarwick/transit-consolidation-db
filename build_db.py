"""build_db.py - Build the unified transit consolidation database.

Reads CSV and Excel files from the 14 transit consolidation case folders
and loads them into a single SQLite database.

Tables created:
  - cases, case_folders         Case metadata and folder mapping
  - acs_long, acs_codebook      ACS demographic profiles (long format)
  - acs_wide_dp02..dp05         ACS wide tables (partitioned by profile group)
  - lodes                       LEHD LODES annual employment
  - qwi                         LEHD QWI quarterly workforce indicators
  - ntd_monthly                 NTD monthly ridership/service (long format)
  - ntd_annual, ntd_info        NTD annual totals and agency info
  - opexp                       Annual operating expenses
  - annual_financial, annual_financial_info   Detailed financials
  - panel_annual                Curated annual panels (from workbooks)
  - panel_annual_export         CSV exports of annual panels
  - panel_monthly_ntd           Monthly panel series
  - manual_master_panel         Stacked curated master panels
  - master_panel                Standardized panel for all 14 cases (2000-2026)
  - reporter_type_flags, case_risk_summary, field_definitions, sheet_notes
  - load_log                    Ingestion log for all files and sheets

Usage:
    python build_db.py path/to/data -o transit.db --force
"""

import argparse
import csv
import datetime as dt
import gzip
import re
import shutil
import sqlite3
import sys
import warnings
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

DEFAULT_CASE_INFO = {
    "CON-001": {
        "folder": "South East Vermont Transit (SEVT)",
        "name": "SEVT (Deerfield Valley Transit Association/DVTA + Connecticut River Transit/CRT -> Southeast Vermont Transit)",
        "date": "2015-07-01",
        "year": 2015,
        "predecessors": "Connecticut River Transit, Inc. / CRT (NTD 10141); Deerfield Valley Transit Association / DVTA (NTD 10144)",
        "successor": "Southeast Vermont Transit, Inc. / SEVT (NTD 10144)",
        "short_name": "sevt",
    },
    "CON-002": {
        "folder": "Greater Portland Transit District (Metro)",
        "name": "Metro (City of South Portland / South Portland Bus -> Greater Portland Transit District / Metro, expanded)",
        "date": "2024-12-29",
        "year": 2025,
        "predecessors": "City of South Portland / South Portland Bus (NTD 10098)",
        "successor": "Greater Portland Transit District / Metro (NTD 10029)",
        "short_name": "metro",
    },
    "CON-005": {
        "folder": "Western Piedmont Regional Transit Authority (Greenway Transit)",
        "name": "Greenway (Alexander County + Burke County + Caldwell County + Catawba County/Piedmont Wagon -> Western Piedmont Regional Transit Authority)",
        "date": "2008-07-01",
        "year": 2008,
        "predecessors": "Alexander County Transportation; Burke County Transportation; Caldwell County Transportation; Piedmont Wagon Transit System / City of Hickory",
        "successor": "Western Piedmont Regional Transit Authority / Greenway Transit (NTD 40158)",
        "short_name": "greenway",
    },
    "CON-006": {
        "folder": "MTA Bus Company (MTABUS)",
        "name": "MTA Bus (7 private NYC bus companies -> MTA Bus Company)",
        "date": "2005-01-03",
        "year": 2005,
        "predecessors": "Green Bus Lines (20114); Jamaica Buses (20115); Triboro Coach (20116); Liberty Lines Express (20117); New York Bus Service (20118); Command Bus (20119); Queens Surface (20121)",
        "successor": "MTA Bus Company (NTD 20188)",
        "short_name": "mtabus",
    },
    "CON-007": {
        "folder": "Victor Valley Transit Authority (VVTA)",
        "name": "VVTA (Barstow Area Transit/BAT -> Victor Valley Transit Authority, expanded)",
        "date": "2015-07-01",
        "year": 2015,
        "predecessors": "Barstow Area Transit / BAT (City of Barstow, NTD 90230)",
        "successor": "Victor Valley Transit Authority (NTD 90148)",
        "short_name": "vvta",
    },
    "CON-008": {
        "folder": "Susquehanna Regional Transportation Authority (SRTA)",
        "name": "SRTA (rabbittransit/CPTA + Capital Area Transit/CAT -> Susquehanna Regional Transportation Authority)",
        "date": "2022-01-01",
        "year": 2022,
        "predecessors": "Central Pennsylvania Transportation Authority / rabbittransit (NTD 30027); Cumberland-Dauphin-Harrisburg Transit Authority / CAT (NTD 30014)",
        "successor": "Susquehanna Regional Transportation Authority / SRTA (NTD 30206)",
        "short_name": "srta",
    },
    "CON-009": {
        "folder": "Capital District Transit Authority (CDTA)",
        "name": "CDTA (Greater Glens Falls Transit / GGFT -> Capital District Transportation Authority, expanded)",
        "date": "2024-01-01",
        "year": 2024,
        "predecessors": "Greater Glens Falls Transit / GGFT (City of Glens Falls, NTD 20120)",
        "successor": "Capital District Transportation Authority / CDTA (NTD 20002)",
        "short_name": "cdta",
    },
    "CON-010": {
        "folder": "Tulare County Regional Transit Agency (TCRT)",
        "name": "TCRTA (8 Tulare County operators -> Tulare County Regional Transit Agency)",
        "date": "2020-08-17",
        "year": 2020,
        "predecessors": "City of Dinuba, City of Porterville (90184), City of Tulare (90187), City of Visalia (90082), City of Woodlake, County of Tulare (90240), Exeter, Farmersville, Lindsay",
        "successor": "Tulare County Regional Transit Agency / TCRTA (NTD 90310)",
        "short_name": "tcrta",
    },
    "CON-011": {
        "folder": "Sacramento Regional Transit District (SAC RT)",
        "name": "SacRT (Elk Grove e-tran folded into Sacramento Regional Transit District)",
        "date": "2021-07-01",
        "year": 2021,
        "predecessors": "City of Elk Grove / e-tran (NTD 90205)",
        "successor": "Sacramento Regional Transit District / SacRT (NTD 90019)",
        "short_name": "sacrt",
    },
    "CON-012": {
        "folder": "Solano County Transit (SolTrans)",
        "name": "SolTrans (Vallejo Transit + Benicia Transit -> Solano County Transit)",
        "date": "2011-07-01",
        "year": 2011,
        "predecessors": "City of Vallejo / Vallejo Transit (NTD 90059); City of Benicia / Benicia Breeze (NTD 90150)",
        "successor": "Solano County Transit / SolTrans (NTD 90232)",
        "short_name": "soltrans",
    },
    "CON-013": {
        "folder": "York Adams Transportation Authority (rabbittransit)",
        "name": "rabbittransit (York County Transportation Authority + Adams County Transit Authority -> York Adams Transportation Authority / rabbittransit)",
        "date": "2011-09-28",
        "year": 2011,
        "predecessors": "York County Transportation Authority (NTD 30027); Adams County Transit Authority",
        "successor": "York Adams Transportation Authority / rabbittransit (NTD 30027)",
        "short_name": "rabbittransit",
    },
    "CON-014": {
        "folder": "San Diego Association of Governments (SANDAG)",
        "name": "SANDAG (CA Planning & Governance Consolidation: MTDB + NCTD planning into SANDAG under SB 1703)",
        "date": "2003-01-01",
        "year": 2003,
        "predecessors": "Metropolitan Transit Development Board (MTDB); North County Transit District (NCTD)",
        "successor": "San Diego Association of Governments (SANDAG)",
        "short_name": "sandag",
    },
    "CON-015": {
        "folder": "South Central Transit Authority (SCTA)",
        "name": "SCTA (Red Rose Transit Authority/RRTA + Berks Area Regional Transportation Authority/BARTA -> South Central Transit Authority)",
        "date": "2014-12-11",
        "year": 2016,
        "predecessors": "Red Rose Transit Authority / RRTA (NTD 30018); Berks Area Regional Transportation Authority / BARTA (NTD 30024)",
        "successor": "South Central Transit Authority / SCTA (NTD 30202)",
        "short_name": "scta",
        "alias": "CAND-004",
    },
    "CON-016": {
        "folder": "Stanislaus Regional Transit Authority (StanRTA)",
        "name": "StanRTA (City of Modesto MAX + Stanislaus County StaRT -> Stanislaus Regional Transit Authority)",
        "date": "2021-01-26",
        "year": 2021,
        "predecessors": "City of Modesto / Modesto Area Express MAX (NTD 90098); Stanislaus County / StaRT (NTD 90209)",
        "successor": "Stanislaus Regional Transit Authority / StanRTA (NTD 90306)",
        "short_name": "stanrta",
        "alias": "CAND-008",
    },
}

def load_case_metadata(root_dir=None, custom_path=None):
    """Load case metadata from cases_metadata.csv, falling back to DEFAULT_CASE_INFO."""
    paths_to_check = []
    if custom_path:
        paths_to_check.append(Path(custom_path))
    if root_dir:
        paths_to_check.append(Path(root_dir) / "cases_metadata.csv")
    script_dir = Path(__file__).resolve().parent
    paths_to_check.append(script_dir / "cases_metadata.csv")

    for p in paths_to_check:
        if p.exists():
            try:
                df = pd.read_csv(p)
                cases = {}
                for _, r in df.iterrows():
                    cid = str(r["case_id"]).strip()
                    cases[cid] = {
                        "folder": str(r["folder"]).strip(),
                        "name": str(r["name"]).strip(),
                        "date": str(r["date"]).strip(),
                        "year": int(r["year"]),
                        "predecessors": str(r["predecessors"]).strip(),
                        "successor": str(r["successor"]).strip(),
                        "short_name": str(r.get("short_name", "")).strip().lower(),
                    }
                    if "alias" in r and pd.notna(r["alias"]) and str(r["alias"]).strip():
                        cases[cid]["alias"] = str(r["alias"]).strip()
                if cases:
                    print(f"Loaded {len(cases)} cases from {p}")
                    return cases
            except Exception as e:
                print(f"Warning: could not parse {p} ({e}), using default metadata.")
    return DEFAULT_CASE_INFO

# Active case info (populated from CSV or defaults)
CASE_INFO = DEFAULT_CASE_INFO

# Panel year range
PANEL_YEARS = range(2000, 2027)

PA_COLUMNS = [
    ("phase", "phase"),
    ("event_time", "event_time"),
    ("post", "post"),
    ("ntd_upt_ry", "ntd_upt_ry"),
    ("ntd_vrm_ry", "ntd_vrm_ry"),
    ("ntd_vrh_ry", "ntd_vrh_ry"),
    ("ntd_upt_cal_all", "ntd_upt_cal_all"),
    ("ntd_vrm_cal_all", "ntd_vrm_cal_all"),
    ("ntd_vrh_cal_all", "ntd_vrh_cal_all"),
    ("ntd_voms_cal_avg", "ntd_voms_cal_avg"),
    ("ntd_months_n", "ntd_months_n"),
    ("opexp_ry_usd", "opexp_ry_usd"),
]

LODES_COLUMNS = [
    ("jobs_total", "jobs_total"),
    ("age_29_or_younger", "age_29_or_younger"),
    ("age_30_to_54", "age_30_to_54"),
    ("age_55_or_older", "age_55_or_older"),
    ("earn_low", "earnings_1250_or_less_per_month"),
    ("earn_mid", "earnings_1251_to_3333_per_month"),
    ("earn_high", "earnings_over_3333_per_month"),
]

# Reverse mapping from folder name to case_id
FOLDER_TO_CASE = {info["folder"]: cid for cid, info in CASE_INFO.items()}

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")
MONTH_RE = re.compile(r"^(\d{4})[-/](\d{1,2})")

tables = defaultdict(list)
notes = []
log = []


def clean_columns(names):
    """Normalize column names to lowercase snake_case identifiers."""
    out, seen = [], Counter()
    for n in names:
        if isinstance(n, float) and not pd.isna(n) and n.is_integer():
            n = int(n)
        s = "col" if pd.isna(n) else re.sub(r"[^0-9a-zA-Z]+", "_", str(n)).strip("_").lower()
        s = s or "col"
        if s[0].isdigit():
            s = "c_" + s
        seen[s] += 1
        out.append(s if seen[s] == 1 else f"{s}_{seen[s]}")
    return out


def as_month(cell):
    """Return 'YYYY-MM' if the cell is a date or month string."""
    if isinstance(cell, (dt.datetime, dt.date)):
        return cell.strftime("%Y-%m")
    if isinstance(cell, str):
        c = cell.strip()
        if DATE_RE.match(c):
            return c[:7]
        m = MONTH_RE.match(c)
        if m:
            yr, mo = m.group(1), int(m.group(2))
            return f"{yr}-{mo:02d}"
    return None


def record(src, sheet, table, rows, status):
    log.append({
        "source_file": src,
        "source_sheet": sheet,
        "table_name": table,
        "rows": rows,
        "status": status
    })


def read_grid(path, sheet):
    """Read an Excel sheet without header and detect the header row."""
    raw = pd.read_excel(path, sheet_name=sheet, header=None)
    raw = raw.dropna(how="all").dropna(axis=1, how="all").reset_index(drop=True)
    raw.columns = range(raw.shape[1])
    if raw.empty:
        return raw, None
    counts = raw.head(12).notna().sum(axis=1)
    if counts.max() == 0:
        return raw, None
    hdr = next(i for i, c in enumerate(counts) if c >= 0.8 * counts.max())
    return raw, hdr


def melt_ntd_matrix(raw, hdr, metric):
    """Melt wide monthly columns into long rows by metric."""
    header = list(raw.iloc[hdr])
    body = raw.iloc[hdr + 1:].reset_index(drop=True)
    month_pos = [i for i, h in enumerate(header) if as_month(h)]
    id_pos = [i for i in range(len(header)) if i not in month_pos]
    if not month_pos:
        return pd.DataFrame()
    ids = body[id_pos].copy()
    ids.columns = clean_columns([header[i] for i in id_pos])
    parts = []
    for i in month_pos:
        part = ids.copy()
        part["month"] = as_month(header[i])
        part["value"] = pd.to_numeric(body[i], errors="coerce")
        parts.append(part)
    long_df = pd.concat(parts, ignore_index=True)
    if not ids.columns.empty:
        long_df = long_df.dropna(subset=["value", ids.columns[0]])
    long_df.insert(0, "metric", metric.upper())
    return long_df


def load_acs_files(case_dir, case_id, root):
    acs_dir = case_dir / "ACS"
    if not acs_dir.exists():
        return

    for p in sorted(acs_dir.iterdir()):
        if not p.is_file() or p.name.startswith("."):
            continue
        rel = p.relative_to(root).as_posix()
        name = p.name.lower()

        if "data_long" in name:
            df = pd.read_csv(p, encoding="utf-8-sig", low_memory=False)
            df.columns = clean_columns(df.columns)
            df.insert(0, "case_id", case_id)
            df["source_file"] = rel
            tables["acs_long"].append(df)
            record(rel, None, "acs_long", len(df), "loaded")

        elif "codebook" in name:
            df = pd.read_csv(p, encoding="utf-8-sig", low_memory=False)
            df.columns = clean_columns(df.columns)
            df.insert(0, "case_id", case_id)
            df["source_file"] = rel
            tables["acs_codebook"].append(df)
            record(rel, None, "acs_codebook", len(df), "loaded")

        elif "wide_by_code" in name:
            df = pd.read_csv(p, encoding="utf-8-sig", low_memory=False)
            meta_cols = [c for c in ["year", "cbsa_code", "geography_name"] if c in df.columns]

            for group, target_table in [
                ("DP02_", "acs_wide_dp02"),
                ("DP03_", "acs_wide_dp03"),
                ("DP04_", "acs_wide_dp04"),
                ("DP05_", "acs_wide_dp05"),
            ]:
                group_cols = meta_cols + [c for c in df.columns if c.startswith(group)]
                if len(group_cols) > len(meta_cols):
                    df_slice = df[group_cols].copy()
                    df_slice.columns = clean_columns(df_slice.columns)
                    df_slice.insert(0, "case_id", case_id)
                    df_slice["source_file"] = rel
                    tables[target_table].append(df_slice)

            record(rel, None, "acs_wide_dp02..05", len(df), "loaded")


def load_lodes_file(case_dir, case_id, root):
    lehd_dir = case_dir / "LEHD"
    if not lehd_dir.exists():
        return

    for p in sorted(lehd_dir.iterdir()):
        if not p.is_file() or p.name.startswith("."):
            continue
        rel = p.relative_to(root).as_posix()
        name = p.name.lower()

        if "_lodes_" in name and p.suffix.lower() == ".csv":
            df = pd.read_csv(p, encoding="utf-8-sig", low_memory=False)
            df.columns = clean_columns(df.columns)
            df.insert(0, "case_id", case_id)
            df["source_file"] = rel
            tables["lodes"].append(df)
            record(rel, None, "lodes", len(df), "loaded")


def load_qwi_file(case_dir, case_id, root):
    lehd_dir = case_dir / "LEHD"
    if not lehd_dir.exists():
        return

    qwi_csv = [f for f in lehd_dir.iterdir() if f.is_file() and "_qwi_" in f.name.lower() and f.suffix.lower() == ".csv"]
    qwi_xl = [f for f in lehd_dir.iterdir() if f.is_file() and "_qwi_" in f.name.lower() and f.suffix.lower() in (".xlsx", ".xlsm")]

    target_file = qwi_csv[0] if qwi_csv else (qwi_xl[0] if qwi_xl else None)
    if not target_file:
        return

    rel = target_file.relative_to(root).as_posix()
    try:
        if target_file.suffix.lower() == ".csv":
            df = pd.read_csv(target_file, encoding="utf-8-sig", low_memory=False)
            first_col = df.columns[0]
            df = df.dropna(subset=[first_col])
            df = df[df[first_col].astype(str).str.contains(r"\d{4}\s*Q[1-4]", regex=True, na=False)].copy()
            df = df.rename(columns={first_col: "year_quarter"})
        else:
            xl = pd.ExcelFile(target_file)
            sheet_name = "All data" if "All data" in xl.sheet_names else xl.sheet_names[0]
            raw, hdr = read_grid(target_file, sheet_name)
            if hdr is None:
                record(rel, sheet_name, "qwi", 0, "skipped: empty sheet")
                return
            names = list(raw.iloc[hdr])
            names[0] = "year_quarter"
            df = raw.iloc[hdr + 1:].copy()
            df.columns = names
            df = df.dropna(subset=["year_quarter"])
            df = df[df["year_quarter"].astype(str).str.contains(r"\d{4}\s*Q[1-4]", regex=True, na=False)].copy()

        df.columns = clean_columns(df.columns)
        df.insert(0, "case_id", case_id)
        df["source_file"] = rel
        tables["qwi"].append(df)
        record(rel, getattr(target_file, "sheet_name", None), "qwi", len(df), "loaded")
    except Exception as e:
        record(rel, None, "qwi", 0, f"ERROR: {type(e).__name__}: {e}")


def load_ntd_workbook(case_dir, case_id, root):
    ntd_files = [f for f in case_dir.iterdir() if f.is_file() and f.name.lower().endswith("_ntd.xlsx")]
    if not ntd_files:
        return

    p = ntd_files[0]
    rel = p.relative_to(root).as_posix()
    xl = pd.ExcelFile(p)

    for sheet in xl.sheet_names:
        raw, hdr = read_grid(p, sheet)
        if hdr is None:
            record(rel, sheet, None, 0, "skipped: empty sheet")
            continue

        for i in range(hdr):
            text = " | ".join(str(v) for v in raw.iloc[i].dropna())
            if text:
                notes.append({"case_id": case_id, "source_file": rel, "source_sheet": sheet, "line": i, "text": text})

        s_lower = sheet.lower()
        if s_lower in ("upt", "vrm", "vrh", "voms"):
            long_df = melt_ntd_matrix(raw, hdr, sheet)
            if not long_df.empty:
                long_df.insert(0, "case_id", case_id)
                long_df["source_file"] = rel
                tables["ntd_monthly"].append(long_df)
                record(rel, sheet, "ntd_monthly", len(long_df), "loaded")
        elif s_lower == "info":
            df = raw.iloc[hdr + 1:].copy()
            df.columns = clean_columns(list(raw.iloc[hdr]))
            df.insert(0, "case_id", case_id)
            df["source_file"] = rel
            tables["ntd_info"].append(df)
            record(rel, sheet, "ntd_info", len(df), "loaded")
        elif s_lower == "annual":
            df = raw.iloc[hdr + 1:].copy()
            df.columns = clean_columns(list(raw.iloc[hdr]))
            df.insert(0, "case_id", case_id)
            df["source_file"] = rel
            tables["ntd_annual"].append(df)
            record(rel, sheet, "ntd_annual", len(df), "loaded")


def load_opexp_workbook(case_dir, case_id, root):
    opexp_files = [f for f in case_dir.iterdir() if f.is_file() and "_opexp.xlsx" in f.name.lower()]
    if not opexp_files:
        return

    p = opexp_files[0]
    rel = p.relative_to(root).as_posix()
    raw, hdr = read_grid(p, "OpExp")
    if hdr is None:
        record(rel, "OpExp", "opexp", 0, "skipped: empty sheet")
        return

    for i in range(hdr):
        text = " | ".join(str(v) for v in raw.iloc[i].dropna())
        if text:
            notes.append({"case_id": case_id, "source_file": rel, "source_sheet": "OpExp", "line": i, "text": text})

    df = raw.iloc[hdr + 1:].copy()
    df.columns = clean_columns(list(raw.iloc[hdr]))
    df.insert(0, "case_id", case_id)
    df["source_file"] = rel
    tables["opexp"].append(df)
    record(rel, "OpExp", "opexp", len(df), "loaded")


def load_annual_financial(case_dir, case_id, root):
    fin_files = [f for f in case_dir.iterdir() if f.is_file() and "_annual_financial.xlsx" in f.name.lower()]
    if not fin_files:
        return

    p = fin_files[0]
    rel = p.relative_to(root).as_posix()
    xl = pd.ExcelFile(p)

    for sheet in xl.sheet_names:
        raw, hdr = read_grid(p, sheet)
        if hdr is None:
            continue

        for i in range(hdr):
            text = " | ".join(str(v) for v in raw.iloc[i].dropna())
            if text:
                notes.append({"case_id": case_id, "source_file": rel, "source_sheet": sheet, "line": i, "text": text})

        df = raw.iloc[hdr + 1:].copy()
        df.columns = clean_columns(list(raw.iloc[hdr]))
        df.insert(0, "case_id", case_id)
        df["source_file"] = rel

        if sheet == "Annual_Metrics":
            tables["annual_financial"].append(df)
            record(rel, sheet, "annual_financial", len(df), "loaded")
        elif sheet == "INFO":
            tables["annual_financial_info"].append(df)
            record(rel, sheet, "annual_financial_info", len(df), "loaded")


def load_combined_master_panel(case_dir, case_id, root):
    combined_dir = case_dir / "Combined Data"
    search_dirs = [combined_dir] if combined_dir.exists() else [case_dir]

    master_files = []
    for s_dir in search_dirs:
        master_files += [f for f in s_dir.iterdir() if f.is_file() and "master_panel" in f.name.lower() and f.suffix.lower() in (".xlsx", ".xlsm")]

    if not master_files:
        return

    p = master_files[0]
    rel = p.relative_to(root).as_posix()
    xl = pd.ExcelFile(p)

    # 1. Panel_Annual: write to manual_master_panel and panel_annual
    if "Panel_Annual" in xl.sheet_names:
        raw, hdr = read_grid(p, "Panel_Annual")
        if hdr is not None:
            df = raw.iloc[hdr + 1:].copy()
            df.columns = clean_columns(list(raw.iloc[hdr]))
            df["case_id"] = case_id
            df["source_file"] = rel

            tables["manual_master_panel"].append(df)
            tables["panel_annual"].append(df)
            record(rel, "Panel_Annual", "manual_master_panel", len(df), "loaded")

    # 2. Panel_Monthly_NTD
    if "Panel_Monthly_NTD" in xl.sheet_names:
        raw, hdr = read_grid(p, "Panel_Monthly_NTD")
        if hdr is not None:
            df = raw.iloc[hdr + 1:].copy()
            df.columns = clean_columns(list(raw.iloc[hdr]))
            df["case_id"] = case_id
            df["source_file"] = rel
            tables["panel_monthly_ntd"].append(df)
            record(rel, "Panel_Monthly_NTD", "panel_monthly_ntd", len(df), "loaded")

    # 3. Panel_Annual_*.csv export
    csv_exports = [f for f in search_dirs[0].iterdir() if f.is_file() and f.name.lower().startswith("panel_annual_") and f.suffix.lower() == ".csv"]
    if csv_exports:
        csv_p = csv_exports[0]
        csv_rel = csv_p.relative_to(root).as_posix()
        try:
            df_csv = pd.read_csv(csv_p, encoding="utf-8-sig")
            df_csv.columns = clean_columns(df_csv.columns)
            df_csv["case_id"] = case_id
            df_csv["source_file"] = csv_rel
            tables["panel_annual_export"].append(df_csv)
            record(csv_rel, None, "panel_annual_export", len(df_csv), "loaded")
        except Exception:
            pass


def load_root_metadata(root):
    # reporter_type_flags.xlsx
    rf = root / "reporter_type_flags.xlsx"
    if rf.exists():
        rel = rf.name
        xl = pd.ExcelFile(rf)
        for s in xl.sheet_names:
            raw, hdr = read_grid(rf, s)
            if hdr is None:
                continue
            df = raw.iloc[hdr + 1:].copy()
            df.columns = clean_columns(list(raw.iloc[hdr]))
            df["source_file"] = rel

            if s == "Reporter_Type_Flags":
                tables["reporter_type_flags"].append(df)
                record(rel, s, "reporter_type_flags", len(df), "loaded")
            elif s == "Case_Risk_Summary":
                tables["case_risk_summary"].append(df)
                record(rel, s, "case_risk_summary", len(df), "loaded")

    # data_source_fields.xlsx
    ds = root / "data_source_fields.xlsx"
    if ds.exists():
        rel = ds.name
        xl = pd.ExcelFile(ds)
        field_frames = []
        for s in xl.sheet_names:
            if s.lower() == "readme":
                continue
            raw, hdr = read_grid(ds, s)
            if hdr is None:
                continue
            df = raw.iloc[hdr + 1:].copy()
            df.columns = clean_columns(list(raw.iloc[hdr]))
            df.insert(0, "sheet_name", s)
            field_frames.append(df)

        if field_frames:
            df_fields = pd.concat(field_frames, ignore_index=True)
            df_fields["source_file"] = rel
            tables["field_definitions"].append(df_fields)
            record(rel, "all", "field_definitions", len(df_fields), "loaded")


def write_table_with_pk(con, name, df):
    """Write DataFrame to SQLite with an autoincrementing 'id' primary key."""
    if "id" in df.columns:
        df = df.rename(columns={"id": "id_orig"})

    df.to_sql("_tmp", con, if_exists="replace", index=False)
    cols = con.execute("PRAGMA table_info(_tmp)").fetchall()

    defs = ", ".join(f'"{c[1]}" {c[2]}' for c in cols)
    col_names = ", ".join(f'"{c[1]}"' for c in cols)

    con.execute(f'CREATE TABLE "{name}" (id INTEGER PRIMARY KEY AUTOINCREMENT, {defs})')
    con.execute(f'INSERT INTO "{name}" ({col_names}) SELECT {col_names} FROM _tmp')
    con.execute("DROP TABLE _tmp")


def synthesize_master_panel(con):
    """Construct standardized master_panel across all 14 cases from 2000 to 2026."""
    print("\nBuilding master_panel (2000-2026)...")

    # Define ACS variable map for demographic indicators
    # (column_name, label_text, stat_type)
    acs_indicators = [
        ("acs_pop", "SEX AND AGE!!Total population", "estimate"),
        ("acs_med_hh_income", "Median household income (dollars)", "estimate"),
        ("acs_med_age", "Median age (years)", "estimate"),
        ("acs_pct_poverty", "Percent below poverty level!!Population for whom poverty status is determined", "percent"),
        ("acs_pct_renter", "Renter-occupied", "percent"),
        ("acs_pct_nh_white", "Not Hispanic or Latino!!White alone", "percent"),
        ("acs_pct_hispanic", "Hispanic or Latino (of any race)", "percent"),
    ]

    # Pre-aggregate QWI quarterly indicators by case and year
    qwi_annual_records = defaultdict(dict)
    try:
        qwi_rows = con.execute("""
            SELECT case_id, CAST(substr(year_quarter, 1, 4) AS INT) AS yr,
                   beginning_of_quarter_employment_counts,
                   full_quarter_employment_stable_counts,
                   hires_all_counts_accessions,
                   separations_counts,
                   job_change_stable_net_change,
                   full_quarter_employment_stable_average_monthly_earnings
            FROM qwi
            WHERE year_quarter LIKE '____ Q%'
        """).fetchall()

        qwi_by_case_year = defaultdict(list)
        for r in qwi_rows:
            cid, yr = r[0], r[1]
            qwi_by_case_year[(cid, yr)].append(r[2:])

        for (cid, yr), rows in qwi_by_case_year.items():
            beg = [float(r[0]) for r in rows if r[0] is not None]
            fq = [float(r[1]) for r in rows if r[1] is not None]
            hires = [float(r[2]) for r in rows if r[2] is not None]
            seps = [float(r[3]) for r in rows if r[3] is not None]
            netchg = [float(r[4]) for r in rows if r[4] is not None]
            earn = [float(r[5]) for r in rows if r[5] is not None]

            qwi_annual_records[(cid, yr)] = {
                "qwi_emp_beg_avg": round(sum(beg) / len(beg), 1) if beg else None,
                "qwi_emp_fq_avg": round(sum(fq) / len(fq), 1) if fq else None,
                "qwi_hires": int(sum(hires)) if hires else None,
                "qwi_seps": int(sum(seps)) if seps else None,
                "qwi_netchg": int(sum(netchg)) if netchg else None,
                "qwi_fq_earn_avg": round(sum(earn) / len(earn), 1) if earn else None,
            }
    except Exception as e:
        print("Note on QWI annual derivation:", e)

    # Pre-aggregate NTD Monthly calendar sums by case and year
    ntd_m_sums = defaultdict(lambda: {"upt_all": 0, "upt_bus": 0, "vrm_all": 0, "vrm_bus": 0, "vrh_all": 0, "vrh_bus": 0, "months": set()})
    try:
        ntd_rows = con.execute("""
            SELECT case_id, metric, substr(month, 1, 4) AS yr, month, value, mode
            FROM ntd_monthly
            WHERE value IS NOT NULL
        """).fetchall()
        for cid, met, yr, mo, val, mode in ntd_rows:
            try:
                y = int(yr)
                entry = ntd_m_sums[(cid, y)]
                entry["months"].add(mo)
                v = float(val)
                is_bus = (mode == "MB" or str(mode).upper() == "BUS")
                if met == "UPT":
                    entry["upt_all"] += v
                    if is_bus:
                        entry["upt_bus"] += v
                elif met == "VRM":
                    entry["vrm_all"] += v
                    if is_bus:
                        entry["vrm_bus"] += v
                elif met == "VRH":
                    entry["vrh_all"] += v
                    if is_bus:
                        entry["vrh_bus"] += v
            except Exception:
                continue
    except Exception as e:
        print("Note on NTD Monthly aggregation:", e)

    # Pre-index LODES
    lodes_by_case_year = {}
    try:
        lo_cols = ["jobs_total", "age_29_or_younger", "age_30_to_54", "age_55_or_older",
                   "earnings_1250_or_less_per_month", "earnings_1251_to_3333_per_month", "earnings_over_3333_per_month"]
        for r in con.execute(f"SELECT case_id, year, {', '.join(lo_cols)} FROM lodes").fetchall():
            lodes_by_case_year[(r[0], int(r[1]))] = {col: r[i + 2] for i, col in enumerate(lo_cols)}
    except Exception as e:
        print("Note on LODES pre-indexing:", e)

    # Pre-index ACS
    acs_by_case_year = defaultdict(dict)
    try:
        for col, label, stat in acs_indicators:
            rows = con.execute("""
                SELECT case_id, year, value FROM acs_long
                WHERE stat_type = ? AND (label_full = ? OR label_full LIKE '%!!' || ?)
            """, (stat, label, label)).fetchall()
            for cid, yr, val in rows:
                try:
                    acs_by_case_year[(cid, int(yr))][col] = float(val)
                except Exception:
                    pass
    except Exception as e:
        print("Note on ACS pre-indexing:", e)

    # Index existing human/manual master panels
    manual_panel_rows = {}
    try:
        h_cols = [c[1] for c in con.execute("PRAGMA table_info(manual_master_panel)").fetchall() if c[1] not in ("id", "source_file")]
        for r in con.execute(f"SELECT {', '.join(h_cols)} FROM manual_master_panel").fetchall():
            d = dict(zip(h_cols, r))
            manual_panel_rows[(d["case_id"], int(d["year"]))] = d
    except Exception as e:
        print("Note on manual panel indexing:", e)

    # Construct balanced panel spine for all 14 cases from 2000 to 2026
    panel_records = []
    years = range(2000, 2027)

    for cid, cinfo in sorted(CASE_INFO.items()):
        event_year = cinfo["year"]

        for y in years:
            rec = {
                "case_id": cid,
                "case_name": cinfo["name"],
                "year": y,
                "event_year": event_year,
                "phase": "POST" if y >= event_year else "PRE",
                "event_time": y - event_year,
                "post": 1 if y >= event_year else 0,
            }

            # Use human-curated values if available for this case-year
            human_rec = manual_panel_rows.get((cid, y))
            if human_rec is not None:
                rec["is_human_verified"] = 1
                for k, v in human_rec.items():
                    rec[k] = v
            else:
                rec["is_human_verified"] = 0
                # Impute from source tables

                # 1. NTD Monthly
                m_info = ntd_m_sums.get((cid, y))
                if m_info and len(m_info["months"]) > 0:
                    rec["ntd_upt_cal_all"] = m_info["upt_all"]
                    rec["ntd_upt_cal_bus"] = m_info["upt_bus"]
                    rec["ntd_vrm_cal_all"] = m_info["vrm_all"]
                    rec["ntd_vrm_cal_bus"] = m_info["vrm_bus"]
                    rec["ntd_vrh_cal_all"] = m_info["vrh_all"]
                    rec["ntd_vrh_cal_bus"] = m_info["vrh_bus"]
                    rec["ntd_months_n"] = len(m_info["months"])
                else:
                    rec["ntd_upt_cal_all"] = None
                    rec["ntd_upt_cal_bus"] = None
                    rec["ntd_vrm_cal_all"] = None
                    rec["ntd_vrm_cal_bus"] = None
                    rec["ntd_vrh_cal_all"] = None
                    rec["ntd_vrh_cal_bus"] = None
                    rec["ntd_months_n"] = 0

                rec["ntd_upt_ry"] = None
                rec["ntd_vrm_ry"] = None
                rec["ntd_vrh_ry"] = None
                rec["ntd_voms_ry"] = None
                rec["ry_n_agencies"] = None

                # 2. Operating Expenses
                try:
                    yr_col = f"c_{y}"
                    opexp_row = con.execute(f"SELECT SUM({yr_col}), COUNT(DISTINCT agency) FROM opexp WHERE case_id = ? AND {yr_col} IS NOT NULL", (cid,)).fetchone()
                    if opexp_row and opexp_row[0] is not None:
                        rec["opexp_ry_usd"] = opexp_row[0]
                        rec["opexp_n_agencies"] = opexp_row[1]
                    else:
                        rec["opexp_ry_usd"] = None
                        rec["opexp_n_agencies"] = None
                except Exception:
                    rec["opexp_ry_usd"] = None
                    rec["opexp_n_agencies"] = None

                # 3. LODES
                lo = lodes_by_case_year.get((cid, y))
                if lo:
                    rec["lodes_jobs_total"] = lo.get("jobs_total")
                    rec["lodes_age_29minus"] = lo.get("age_29_or_younger")
                    rec["lodes_age_30_54"] = lo.get("age_30_to_54")
                    rec["lodes_age_55plus"] = lo.get("age_55_or_older")
                    rec["lodes_earn_low"] = lo.get("earnings_1250_or_less_per_month")
                    rec["lodes_earn_mid"] = lo.get("earnings_1251_to_3333_per_month")
                    rec["lodes_earn_high"] = lo.get("earnings_over_3333_per_month")
                else:
                    rec["lodes_jobs_total"] = None
                    rec["lodes_age_29minus"] = None
                    rec["lodes_age_30_54"] = None
                    rec["lodes_age_55plus"] = None
                    rec["lodes_earn_low"] = None
                    rec["lodes_earn_mid"] = None
                    rec["lodes_earn_high"] = None

                # 4. QWI
                qw = qwi_annual_records.get((cid, y))
                if qw:
                    rec.update(qw)
                else:
                    rec["qwi_emp_beg_avg"] = None
                    rec["qwi_emp_fq_avg"] = None
                    rec["qwi_hires"] = None
                    rec["qwi_seps"] = None
                    rec["qwi_netchg"] = None
                    rec["qwi_fq_earn_avg"] = None

                # 5. ACS
                ac = acs_by_case_year.get((cid, y), {})
                rec["acs_pop"] = ac.get("acs_pop")
                rec["acs_med_hh_income"] = ac.get("acs_med_hh_income")
                rec["acs_med_age"] = ac.get("acs_med_age")
                rec["acs_pct_poverty"] = ac.get("acs_pct_poverty")
                rec["acs_pct_renter"] = ac.get("acs_pct_renter")
                rec["acs_pct_nh_white"] = ac.get("acs_pct_nh_white")
                rec["acs_pct_hispanic"] = ac.get("acs_pct_hispanic")

            # Coverage flags
            rec["has_lodes"] = 1 if rec.get("lodes_jobs_total") is not None else 0
            rec["has_qwi"] = 1 if rec.get("qwi_emp_beg_avg") is not None else 0
            rec["has_acs"] = 1 if rec.get("acs_pop") is not None else 0
            rec["has_opexp"] = 1 if rec.get("opexp_ry_usd") is not None else 0
            rec["has_ntd_monthly"] = 1 if (rec.get("ntd_months_n") or 0) > 0 else 0

            # Column aliases
            rec["jobs_total"] = rec.get("lodes_jobs_total")
            rec["age_29_or_younger"] = rec.get("lodes_age_29minus")
            rec["age_30_to_54"] = rec.get("lodes_age_30_54")
            rec["age_55_or_older"] = rec.get("lodes_age_55plus")
            rec["earn_low"] = rec.get("lodes_earn_low")
            rec["earn_mid"] = rec.get("lodes_earn_mid")
            rec["earn_high"] = rec.get("lodes_earn_high")

            panel_records.append(rec)

    df_panel = pd.DataFrame(panel_records)
    write_table_with_pk(con, "master_panel", df_panel)
    con.execute("CREATE INDEX idx_master_panel_case_year ON master_panel (case_id, year)")
    con.commit()
    print(f"  master_panel generated: {len(df_panel):,} rows.")


def export_core_db(source_db, target_dir):
    """Export lightweight core database (without large raw ACS long tables) and gzip archive for web."""
    out_dir = Path(target_dir)
    if not out_dir.exists():
        return
    core_db = out_dir / "transit_core.db"
    if core_db.exists():
        core_db.unlink()
    con_src = sqlite3.connect(source_db)
    con_dst = sqlite3.connect(core_db)
    tables = [r[0] for r in con_src.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('acs_long', 'acs_codebook', 'sqlite_sequence')").fetchall()]
    for t in tables:
        df_sql = con_src.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{t}'").fetchone()[0]
        con_dst.execute(df_sql)
        rows = con_src.execute(f"SELECT * FROM \"{t}\"").fetchall()
        if rows:
            placeholders = ",".join(["?"] * len(rows[0]))
            con_dst.executemany(f"INSERT INTO \"{t}\" VALUES ({placeholders})", rows)
    con_dst.commit()
    con_dst.execute("VACUUM")
    con_dst.close()
    con_src.close()

    gz_target = out_dir / "transit.db.gz"
    with open(source_db, "rb") as f_in:
        with gzip.open(gz_target, "wb", compresslevel=9) as f_out:
            shutil.copyfileobj(f_in, f_out)
    print(f"Updated web assets: {core_db} ({core_db.stat().st_size:,} bytes) and {gz_target} ({gz_target.stat().st_size:,} bytes).")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("data_dir", help="Path to data directory")
    parser.add_argument("-o", "--out", default="transit.db", help="Output SQLite database path")
    parser.add_argument("--force", action="store_true", help="Overwrite output database if it exists")
    parser.add_argument("--cases-csv", default=None, help="Path to custom cases_metadata.csv")
    parser.add_argument("--export-docs", default="docs/data", help="Directory to export web database files (or 'none' to skip)")
    args = parser.parse_args()

    global CASE_INFO, FOLDER_TO_CASE
    root = Path(args.data_dir)
    out_db = Path(args.out)

    CASE_INFO = load_case_metadata(root, args.cases_csv)
    FOLDER_TO_CASE = {info["folder"]: cid for cid, info in CASE_INFO.items()}

    if out_db.exists():
        if not args.force:
            sys.exit(f"{out_db} already exists. Use --force to overwrite.")
        out_db.unlink()

    print(f"Source data directory: {root}")
    print(f"Target SQLite database: {out_db}\n")

    # 1. Process case directories
    case_folders_meta = []
    case_definitions = []

    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name.startswith((".", "__")) or d.name in ("SOURCE DATA", "Susie Data", "LEHD Graphs and Exploratory Data Analysis"):
            continue

        cid = FOLDER_TO_CASE.get(d.name)
        if not cid:
            continue

        cinfo = CASE_INFO[cid]
        case_folders_meta.append({
            "case_id": cid,
            "folder": d.name,
            "short_name": cinfo["short_name"],
            "event_year": cinfo["year"],
            "consolidation_date": cinfo["date"],
        })
        case_definitions.append({
            "case_id": cid,
            "case_name": cinfo["name"],
            "consolidation_date": cinfo["date"],
            "event_year": cinfo["year"],
            "predecessor_agencies": cinfo["predecessors"],
            "successor": cinfo["successor"],
            "folder_name": d.name,
        })

        # Ingest case data files
        load_acs_files(d, cid, root)
        load_lodes_file(d, cid, root)
        load_qwi_file(d, cid, root)
        load_ntd_workbook(d, cid, root)
        load_opexp_workbook(d, cid, root)
        load_annual_financial(d, cid, root)
        load_combined_master_panel(d, cid, root)

    # 2. Ingest root metadata
    load_root_metadata(root)

    # 3. Add case definitions & case folders
    tables["case_folders"].append(pd.DataFrame(case_folders_meta))
    tables["cases"].append(pd.DataFrame(case_definitions))
    if notes:
        tables["sheet_notes"].append(pd.DataFrame(notes))

    # 4. Connect to database and write tables
    con = sqlite3.connect(out_db)

    print("Writing tables to SQLite...")
    for name, frames in sorted(tables.items()):
        if not frames:
            continue
        try:
            df = pd.concat(frames, ignore_index=True, sort=False)
            write_table_with_pk(con, name, df)
            print(f"  {name:30s} | {len(df):>8,} rows | {df.shape[1]:>4} cols")
        except Exception as e:
            print(f"  ERROR writing {name}: {e}")

    con.commit()

    # 5. Generate master_panel
    synthesize_master_panel(con)

    # 6. Ingest log
    df_log = pd.DataFrame(log)
    write_table_with_pk(con, "load_log", df_log)
    con.commit()

    con.close()
    print(f"\nWrote {out_db} ({out_db.stat().st_size:,} bytes).")

    if args.export_docs and args.export_docs.lower() != "none":
        export_core_db(out_db, args.export_docs)


if __name__ == "__main__":
    main()
