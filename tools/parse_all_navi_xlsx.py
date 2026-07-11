#!/usr/bin/env python3
"""Run parse_navi_xlsx over every downloaded (period, scheme) file, report a
compact per-file trust summary (weight sum vs Grand Total) so layout drift is
visible at a glance. Mirrors parse_all_hdfc_xlsx.py's reporting shape.

Pre-rebrand Essel-era single-workbook months (2019-01..2021-08, see
discover_navi_xlsx.py) are walked too but expected to report 0 funds parsed
per month (load_workbook_rows/parse_sheet find no matching header row in
that older schema and skip gracefully) — NOT counted as mismatches, since
they were never attempted, just unsupported and logged as such."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from parse_navi_xlsx import parse_sheet, load_workbook_rows

ROOT = Path(__file__).parent
XLSX_DIR = ROOT / "cache" / "navi" / "xlsx"
OUT_DIR = ROOT / "out" / "navi_xlsx"

TRUST_BAND = (99.0, 101.0)


def main():
    only_periods = set(sys.argv[1:]) or None
    periods = sorted(p.name for p in XLSX_DIR.iterdir() if p.is_dir())
    if only_periods:
        periods = [p for p in periods if p in only_periods]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    mismatches = []
    unsupported = []
    fund_month_count = 0
    passed_count = 0

    for period in periods:
        period_dir = XLSX_DIR / period
        funds = {}
        for xlsx_path in sorted(period_dir.glob("*.xls*")):
            try:
                sheets = load_workbook_rows(xlsx_path)
            except Exception as ex:
                unsupported.append((period, xlsx_path.name, str(ex)))
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
                funds[parsed["fund_name"]] = {"holdings": parsed["holdings"], "grand_total_pct": gt_pct}
        (OUT_DIR / f"{period}.json").write_text(json.dumps(funds, indent=2))
        print(f"{period}: {len(funds)} funds parsed")

    print(f"\n{fund_month_count} fund-months parsed across {len(periods)} months.")
    print(f"{passed_count} passed trust band, {len(mismatches)} mismatches:")
    for m in mismatches:
        print("  ", m)
    if unsupported:
        print(f"\n{len(unsupported)} files failed to open (pre-rebrand Essel-era / .xlsb / other unsupported format):")
        for u in unsupported[:20]:
            print("  ", u)
        if len(unsupported) > 20:
            print(f"   ... and {len(unsupported) - 20} more")


if __name__ == "__main__":
    main()
