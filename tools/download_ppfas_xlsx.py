#!/usr/bin/env python3
"""Download every XLS in the PPFAS portfolio-disclosure manifest to
cache/ppfas/xlsx/<period>.xlsx (renamed from .xls — the file is real OOXML
zip content regardless of the server's .xls extension; openpyxl only
refuses to load based on file extension, see parse_ppfas_xlsx.py docstring)."""
import json
import sys
import time
from pathlib import Path

from http_util import download_file

ROOT = Path(__file__).parent
MANIFEST = ROOT / "cache" / "ppfas" / "xlsx_manifest.json"
XLSX_DIR = ROOT / "cache" / "ppfas" / "xlsx"


def main():
    entries = json.loads(MANIFEST.read_text())
    XLSX_DIR.mkdir(parents=True, exist_ok=True)
    ok, skipped, failed = 0, 0, []
    for e in entries:
        dest = XLSX_DIR / f"{e['period']}.xlsx"
        if dest.exists() and dest.stat().st_size > 5_000:
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
