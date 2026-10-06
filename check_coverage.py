"""check_coverage.py - Validate database integrity and compare master_panel against source tables.

Usage:
    python check_coverage.py transit.db [data_dir]

With data_dir, CSV line counts are also compared against database rows.
"""
import csv
import sqlite3
import sys
from pathlib import Path

from build_db import PA_COLUMNS, LODES_COLUMNS, PANEL_YEARS


def count_csv_rows(path):
    for enc in ("utf-8-sig", "latin-1"):
        try:
            with open(path, encoding=enc, newline="") as f:
                return sum(1 for r in csv.reader(f) if r) - 1   # minus header; blank lines skipped
        except UnicodeDecodeError:
            continue
    return None


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    uri = Path(sys.argv[1]).resolve().as_uri() + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    root = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    problems = 0

    def report(title, rows):
        nonlocal problems
        print(f"\n=== {title} ===")
        if not rows:
            print("ok")
            return
        problems += len(rows)
        for r in rows[:25]:
            print("  ", *r)
        if len(rows) > 25:
            print(f"   ... and {len(rows) - 25} more")

    def cols(table):
        return {r[1] for r in con.execute(f'PRAGMA table_info("{table}")')}

    # 1. Row counts in load_log vs table row counts
    rows = []
    for t, n in con.execute("SELECT table_name, SUM(rows) FROM load_log WHERE status='loaded' GROUP BY 1").fetchall():
        try:
            got = con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        except sqlite3.OperationalError:
            rows.append((t, f"logged {n}", "table missing"))
            continue
        if got != n:
            rows.append((t, f"logged {n}", f"table has {got}"))
    report("1. load_log row counts vs table row counts", rows)

    # 2. Files and sheets with errors or unrecognized status
    report("2. Errors and unrecognized files/sheets",
           con.execute("SELECT source_file, source_sheet, status FROM load_log "
                       "WHERE status LIKE 'ERROR%' OR status LIKE 'skipped: unrecognised%'").fetchall())

    # 3. CSV line counts vs loaded table rows
    if root:
        rows = []
        for src, n in con.execute("SELECT source_file, rows FROM load_log "
                                  "WHERE status='loaded' AND source_sheet IS NULL").fetchall():
            p = root / src
            if p.suffix.lower() == ".csv" and p.exists():
                got = count_csv_rows(p)
                if got != n:
                    rows.append((src, f"file has {got}", f"loaded {n}"))
        report("3. CSV files: rows in file vs rows loaded", rows)

    # 4. master_panel key constraints and year coverage
    report("4a. Duplicate case-year records in master_panel",
           con.execute("SELECT case_id, year, COUNT(*) FROM master_panel GROUP BY 1,2 HAVING COUNT(*)>1").fetchall())
    lo, hi = min(PANEL_YEARS), max(PANEL_YEARS)
    rows = []
    for t in ("manual_master_panel", "lodes", "acs_long"):
        rows += [(t, *r) for r in con.execute(
            f"SELECT case_id, CAST(year AS INTEGER), COUNT(*) FROM {t} "
            f"WHERE CAST(year AS INTEGER) NOT BETWEEN {lo} AND {hi} "
            f"   OR case_id NOT IN (SELECT case_id FROM case_folders) GROUP BY 1,2").fetchall()]
    report(f"4b. Source rows outside {lo}-{hi} or unmatched to a case", rows)

    # 5. Cell-by-cell comparison between master_panel and source tables
    rows = []
    for table, mapping in (("manual_master_panel", PA_COLUMNS), ("lodes", LODES_COLUMNS)):
        have = cols(table)
        alias = "p"
        for dst, src in mapping:
            if src not in have:
                rows.append((table, src, "column missing in source table"))
                continue
            n = con.execute(
                f"SELECT COUNT(*) FROM master_panel m JOIN {table} {alias} "
                f"ON {alias}.case_id = m.case_id AND {alias}.year = m.year "
                f"WHERE m.{dst} IS NOT {alias}.{src}").fetchone()[0]
            if n:
                rows.append((table, src, f"{n} cell(s) differ in master_panel.{dst}"))
    report("5. master_panel values vs source tables", rows)

    print(f"\n{problems} issue(s) found.")
    print("Note: Excel files (.xlsx) are not re-read independently; section 1 checks load_log against table counts.")


if __name__ == "__main__":
    main()