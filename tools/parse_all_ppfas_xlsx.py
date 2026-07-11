#!/usr/bin/env python3
"""Run parse_ppfas_xlsx over every downloaded month, report a compact
per-month/per-fund trust summary (weight sum vs GRAND TOTAL) so layout
drift across years is visible at a glance rather than eyeballing 89 runs."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from parse_ppfas_xlsx import parse_sheet, load_workbook_rows

ROOT = Path(__file__).parent
XLSX_DIR = ROOT / "cache" / "ppfas" / "xlsx"
OUT_DIR = ROOT / "out" / "ppfas_xlsx"

TRUST_BAND = (99.0, 101.0)


def main():
    periods = sorted(p.stem for p in XLSX_DIR.glob("*.xlsx"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    mismatches = []
    fund_month_count = 0
    for period in periods:
        path = XLSX_DIR / f"{period}.xlsx"
        try:
            sheets = load_workbook_rows(path)
        except Exception as ex:
            print(f"{period}: FAILED TO OPEN — {ex}")
            mismatches.append((period, "WORKBOOK", str(ex)))
            continue
        funds = {}
        for sheet_name, rows in sheets.items():
            parsed = parse_sheet(rows)
            if not parsed["fund_name"]:
                continue
            fund_month_count += 1
            total = round(sum(h["weight"] for h in parsed["holdings"]), 2)
            gt = parsed["grand_total"]
            gt_pct = round(gt * 100, 2) if gt is not None else None
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
