#!/usr/bin/env python3
"""Run parse_motilal_xlsx over every downloaded month, report a compact
per-month/per-fund trust summary (weight sum vs GRAND TOTAL) so layout drift
across 13+ years of filings is visible at a glance rather than eyeballing
160+ runs. Mirrors tools/parse_all_ppfas_xlsx.py."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from parse_motilal_xlsx import parse_sheet, load_workbook_rows

ROOT = Path(__file__).parent
XLSX_DIR = ROOT / "cache" / "motilal" / "xlsx"
OUT_DIR = ROOT / "out" / "motilal_xlsx"

# Motilal's weight column is already a percentage (see parse_motilal_xlsx.py
# docstring point 2) — no *100 conversion needed to compare against this band.
TRUST_BAND = (99.0, 101.0)


def main():
    paths = sorted(XLSX_DIR.glob("*.xls*"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    mismatches = []
    open_failures = []
    fund_month_count = 0
    periods_ok = 0
    for path in paths:
        period = path.stem
        try:
            sheets = load_workbook_rows(path)
        except Exception as ex:
            print(f"{period}: FAILED TO OPEN — {ex}")
            open_failures.append((period, str(ex)))
            continue
        funds = {}
        for sheet_name, rows in sheets.items():
            if sheet_name.strip().lower() == "index":
                continue
            parsed = parse_sheet(rows)
            if not parsed["fund_name"]:
                continue
            fund_month_count += 1
            total = round(sum(h["weight"] for h in parsed["holdings"]), 2)
            gt_pct = round(parsed["grand_total"], 2) if parsed["grand_total"] is not None else None
            ok = gt_pct is not None and TRUST_BAND[0] <= total <= TRUST_BAND[1] and abs(total - gt_pct) < 1.0
            if not ok:
                mismatches.append((period, parsed["fund_name"], f"sum={total} gt={gt_pct} n={len(parsed['holdings'])}"))
            funds[parsed["fund_name"]] = {"holdings": parsed["holdings"], "grand_total_pct": gt_pct}
        (OUT_DIR / f"{period}.json").write_text(json.dumps(funds, indent=2))
        if funds:
            periods_ok += 1
        print(f"{period}: {len(funds)} funds parsed")

    print(f"\n{fund_month_count} fund-months parsed across {len(paths)} months ({periods_ok} months yielded >=1 fund).")
    print(f"{len(open_failures)} workbooks failed to open:")
    for f in open_failures:
        print("  ", f)
    print(f"{len(mismatches)} fund-months outside trust band:")
    for m in mismatches:
        print("  ", m)


if __name__ == "__main__":
    main()
