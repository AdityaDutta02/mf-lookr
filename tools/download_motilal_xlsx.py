#!/usr/bin/env python3
"""Download every XLS/XLSX in the Motilal Oswal portfolio-disclosure manifest to
cache/motilal/xlsx/<period>.xlsx. One workbook per period (many scheme sheets
inside — see parse_motilal_xlsx.py), same shape as PPFAS's cache/ppfas/xlsx/,
not one file per scheme. Older (pre-~2022) months are genuine legacy BIFF8
.xls files; newer ones are real OOXML .xlsx — parse_motilal_xlsx.py's
load_workbook_rows() dispatches on file signature, not extension, so we keep
whatever extension the source URL used."""
import json
import sys
import time
from pathlib import Path

from http_util import download_file

ROOT = Path(__file__).parent
MANIFEST = ROOT / "cache" / "motilal" / "xlsx_manifest.json"
XLSX_DIR = ROOT / "cache" / "motilal" / "xlsx"


def main():
    entries = json.loads(MANIFEST.read_text())
    XLSX_DIR.mkdir(parents=True, exist_ok=True)
    ok, skipped, failed = 0, 0, []
    for e in entries:
        ext = ".xlsx" if e["url"].lower().endswith(".xlsx") else ".xls"
        dest = XLSX_DIR / f"{e['period']}{ext}"
        if dest.exists() and dest.stat().st_size > 20_000:
            skipped += 1
            continue
        try:
            size = download_file(e["url"], str(dest))
            print(f"  {e['period']}  {size/1024:.0f} KB")
            ok += 1
            time.sleep(0.3)
        except Exception as ex:
            print(f"  {e['period']}  FAILED: {ex}")
            failed.append(e["period"])
    print(f"\nDownloaded {ok}, already cached {skipped}, failed {len(failed)}")
    if failed:
        print("Failed periods:", failed)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
