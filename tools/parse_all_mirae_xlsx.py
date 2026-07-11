#!/usr/bin/env python3
"""Run parse_mirae_xlsx over every downloaded (period, scheme-file), report a
compact per-month/per-fund trust summary (weight sum vs GRAND TOTAL) so
layout drift across schemes/eras is visible at a glance — mirrors
parse_all_ppfas_xlsx.py/parse_all_hdfc_xlsx.py's shape, adapted for Mirae's
one-file-per-scheme-per-period directory layout (cache/mirae/xlsx/<period>/
<scheme-slug>.xlsx) instead of one-workbook-per-period.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from parse_mirae_xlsx import parse_sheet, load_workbook_rows

ROOT = Path(__file__).parent
XLSX_DIR = ROOT / "cache" / "mirae" / "xlsx"
OUT_DIR = ROOT / "out" / "mirae_xlsx"

TRUST_BAND = (99.0, 101.0)


def main():
    only_periods = set(sys.argv[1:]) or None
    period_dirs = sorted(p for p in XLSX_DIR.iterdir() if p.is_dir())
    if only_periods:
        period_dirs = [p for p in period_dirs if p.name in only_periods]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    mismatches = []
    fund_month_count = 0

    for period_dir in period_dirs:
        period = period_dir.name
        funds = {}
        for xlsx_path in sorted(period_dir.glob("*.xlsx")):
            try:
                sheets = load_workbook_rows(xlsx_path)
            except Exception as ex:
                print(f"{period}/{xlsx_path.stem}: FAILED TO OPEN — {ex}")
                mismatches.append((period, xlsx_path.stem, "WORKBOOK", str(ex)))
                continue
            for sheet_name, rows in sheets.items():
                try:
                    parsed = parse_sheet(rows)
                except Exception as ex:
                    mismatches.append((period, xlsx_path.stem, sheet_name, f"PARSE ERROR: {ex}"))
                    continue
                if not parsed["fund_name"]:
                    continue
                fund_month_count += 1
                total = round(sum(h["weight"] for h in parsed["holdings"]), 2)
                gt = parsed["grand_total"]
                gt_pct = round(gt * 100, 2) if gt is not None else None
                ok = gt_pct is not None and TRUST_BAND[0] <= total <= TRUST_BAND[1] and abs(total - gt_pct) < 1.0
                if not ok:
                    mismatches.append((period, xlsx_path.stem, parsed["fund_name"],
                                        f"sum={total} gt={gt_pct} n={len(parsed['holdings'])}"))
                funds[parsed["fund_name"]] = {
                    "holdings": parsed["holdings"], "grand_total_pct": gt_pct, "metrics": parsed["metrics"],
                }
        (OUT_DIR / f"{period}.json").write_text(json.dumps(funds, indent=2))
        print(f"{period}: {len(funds)} funds parsed ({len(list(period_dir.glob('*.xlsx')))} files)")

    print(f"\n{fund_month_count} fund-months parsed across {len(period_dirs)} months.")
    print(f"{len(mismatches)} mismatches outside trust band:")
    for m in mismatches:
        print("  ", m)


if __name__ == "__main__":
    main()
