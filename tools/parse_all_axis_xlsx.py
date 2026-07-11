#!/usr/bin/env python3
"""Run parse_axis_xlsx over every downloaded (period, scheme) file, report a
compact per-file trust summary (weight sum vs GRAND TOTAL) so layout drift
across scheme types (equity/debt/ETF/FOF/index) is visible at a glance,
mirroring tools/parse_all_hdfc_xlsx.py exactly — one file per scheme per
period (unlike PPFAS's one-workbook-many-sheets), so periods accumulate
incrementally as parse_sheet() is called once per file.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from parse_axis_xlsx import parse_sheet, load_workbook_rows

ROOT = Path(__file__).parent
XLSX_DIR = ROOT / "cache" / "axis" / "xlsx"
OUT_DIR = ROOT / "out" / "axis_xlsx"

TRUST_BAND = (99.0, 101.0)


def main():
    if not XLSX_DIR.exists():
        print(f"No cache dir at {XLSX_DIR} — run discover_axis_xlsx.py + download_axis_xlsx.py first.")
        return 1

    periods = sorted(p.name for p in XLSX_DIR.iterdir() if p.is_dir())
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    mismatches = []
    fund_month_count = 0

    for period in periods:
        period_dir = XLSX_DIR / period
        funds = {}
        out_path = OUT_DIR / f"{period}.json"
        if out_path.exists():
            funds = json.loads(out_path.read_text())

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
                    continue
                fund_month_count += 1
                total = round(sum(h["weight"] for h in parsed["holdings"]), 2)
                gt = parsed["grand_total"]
                gt_pct = round(gt * 100, 2) if gt is not None else None
                ok = gt_pct is not None and TRUST_BAND[0] <= total <= TRUST_BAND[1] and abs(total - gt_pct) < 1.0
                if not ok:
                    mismatches.append((period, parsed["fund_name"], f"sum={total} gt={gt_pct} n={len(parsed['holdings'])}"))
                funds[parsed["fund_name"]] = {"holdings": parsed["holdings"], "grand_total_pct": gt_pct}

        out_path.write_text(json.dumps(funds, indent=2))
        print(f"{period}: {len(funds)} funds parsed")

    print(f"\n{fund_month_count} fund-months parsed across {len(periods)} months.")
    print(f"{len(mismatches)} mismatches outside trust band:")
    for m in mismatches:
        print("  ", m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
