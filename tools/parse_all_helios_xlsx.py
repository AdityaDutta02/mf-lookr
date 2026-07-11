#!/usr/bin/env python3
"""Run parse_helios_xlsx over every downloaded (scheme, month) file, report a
compact per-file trust summary (weight sum vs GRAND TOTAL) so layout drift
across schemes/years is visible at a glance rather than eyeballing ~170 runs.

Unlike PPFAS (one workbook per month, many sheets), Helios is one workbook
per (scheme, month) — cache/helios/xlsx/<period>/<scheme-slug>.xlsx — so we
walk period directories and merge every scheme's result into out/helios_xlsx/
<period>.json, one fund entry per scheme, same as parse_helios_xlsx.py's own
incremental single-file behavior.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from parse_helios_xlsx import parse_sheet, load_workbook_rows

ROOT = Path(__file__).parent
XLSX_DIR = ROOT / "cache" / "helios" / "xlsx"
OUT_DIR = ROOT / "out" / "helios_xlsx"

TRUST_BAND = (99.0, 101.0)


def main():
    periods = sorted(p.name for p in XLSX_DIR.iterdir() if p.is_dir())
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    mismatches = []
    fund_month_count = 0

    for period in periods:
        period_dir = XLSX_DIR / period
        funds = {}
        for xlsx_path in sorted(period_dir.glob("*.xlsx")):
            try:
                sheets = load_workbook_rows(xlsx_path)
            except Exception as ex:
                print(f"{period}/{xlsx_path.name}: FAILED TO OPEN — {ex}")
                mismatches.append((period, xlsx_path.name, "WORKBOOK", str(ex)))
                continue
            for sheet_name, rows in sheets.items():
                parsed = parse_sheet(rows)
                if not parsed["fund_name"]:
                    # Legacy .xls-era downloads (2023) carry a second "Index" sheet
                    # (scheme code lookup table, no holdings) alongside the real
                    # data sheet — expected to have no fund name, not a parse failure.
                    continue
                fund_month_count += 1
                total = round(sum(h["weight"] for h in parsed["holdings"]), 2)
                gt_pct = round(parsed["grand_total"], 2) if parsed["grand_total"] is not None else None
                ok = gt_pct is not None and TRUST_BAND[0] <= total <= TRUST_BAND[1] and abs(total - gt_pct) < 1.0
                if not ok:
                    mismatches.append((period, parsed["fund_name"], f"sum={total} gt={gt_pct} n={len(parsed['holdings'])}"))
                funds[parsed["fund_name"]] = {"holdings": parsed["holdings"], "grand_total_pct": gt_pct}
        (OUT_DIR / f"{period}.json").write_text(json.dumps(funds, indent=2))
        print(f"{period}: {len(funds)} funds parsed")

    print(f"\n{fund_month_count} fund-months parsed across {len(periods)} months.")
    print(f"{len(mismatches)} mismatches outside trust band:")
    for m in mismatches:
        print("  ", m)


if __name__ == "__main__":
    main()
