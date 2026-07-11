#!/usr/bin/env python3
"""Run parse_hdfc_xlsx over every downloaded (period, scheme) file, report a
compact per-file trust summary (weight sum vs Grand Total) so layout drift
across the ~100+ scheme types / dozens of months is visible at a glance
rather than eyeballing thousands of individual runs. Mirrors
parse_all_ppfas_xlsx.py's reporting shape."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from parse_hdfc_xlsx import parse_sheet, load_workbook_sheets

ROOT = Path(__file__).parent
XLSX_DIR = ROOT / "cache" / "hdfc" / "xlsx"
OUT_DIR = ROOT / "out" / "hdfc_xlsx"

TRUST_BAND = (99.0, 101.0)


def main():
    only_periods = set(sys.argv[1:]) or None
    periods = sorted(p.name for p in XLSX_DIR.iterdir() if p.is_dir())
    if only_periods:
        periods = [p for p in periods if p in only_periods]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    mismatches = []
    fund_month_count = 0
    passed_count = 0

    for period in periods:
        period_dir = XLSX_DIR / period
        funds = {}
        for xlsx_path in sorted(period_dir.glob("*.xlsx")):
            try:
                sheets = load_workbook_sheets(xlsx_path)
            except Exception as ex:
                print(f"{period}/{xlsx_path.name}: FAILED TO OPEN — {ex}")
                mismatches.append((period, xlsx_path.name, "WORKBOOK", str(ex)))
                continue
            for sheet_name, rows in sheets.items():
                parsed = parse_sheet(rows)
                if not parsed["fund_name"]:
                    continue
                fund_month_count += 1
                total = round(sum(h["weight"] for h in parsed["holdings"]), 2)
                gt = parsed["grand_total"]
                gt_pct = round(gt, 2) if gt is not None else None
                ok = gt_pct is not None and TRUST_BAND[0] <= total <= TRUST_BAND[1] and abs(total - gt_pct) < 1.0
                if ok:
                    passed_count += 1
                else:
                    mismatches.append((period, parsed["fund_name"], f"sum={total} gt={gt_pct} n={len(parsed['holdings'])}"))
                # A scheme with multiple share-class files (rare) or a stray duplicate
                # would collide here — last-write-wins, same tradeoff parse_all_ppfas
                # makes; flagged in mismatches only if trust band actually fails.
                funds[parsed["fund_name"]] = {"holdings": parsed["holdings"], "grand_total_pct": gt_pct}
        (OUT_DIR / f"{period}.json").write_text(json.dumps(funds, indent=2))
        print(f"{period}: {len(funds)} funds parsed")

    print(f"\n{fund_month_count} fund-months parsed across {len(periods)} months.")
    print(f"{passed_count} passed trust band, {len(mismatches)} mismatches:")
    for m in mismatches:
        print("  ", m)


if __name__ == "__main__":
    main()
