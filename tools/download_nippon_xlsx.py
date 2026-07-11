#!/usr/bin/env python3
"""Download every XLS in the Nippon portfolio-disclosure manifest to
cache/nippon/xlsx/<period>.xlsx (renamed from .xls — real content is a mix of
modern OOXML zip and legacy BIFF8/OLE2 depending on how old the month is;
openpyxl/xlrd dispatch on the file's own signature, not the extension — see
parse_nippon_xlsx.py). One workbook per month (many sheets, one per scheme) —
same shape as PPFAS's archive, unlike HDFC's one-file-per-scheme-per-month.

--limit N caps how many NEW files this run downloads, same as
download_hdfc_xlsx.py, so a big backfill can be chunked across runs."""
import json
import sys
import time
from pathlib import Path

from http_util import download_file

ROOT = Path(__file__).parent
MANIFEST = ROOT / "cache" / "nippon" / "xlsx_manifest.json"
XLSX_DIR = ROOT / "cache" / "nippon" / "xlsx"


def main():
    limit = None
    for arg in sys.argv[1:]:
        if arg.startswith("--limit="):
            limit = int(arg.split("=", 1)[1])

    entries = json.loads(MANIFEST.read_text())
    XLSX_DIR.mkdir(parents=True, exist_ok=True)
    ok, skipped, failed = 0, 0, []
    downloaded_this_run = 0

    for e in entries:
        if limit is not None and downloaded_this_run >= limit:
            print(f"\nHit --limit={limit}, stopping (resume by re-running).")
            break
        dest = XLSX_DIR / f"{e['period']}.xlsx"
        if dest.exists() and dest.stat().st_size > 5_000:
            skipped += 1
            continue
        try:
            size = download_file(e["url"], str(dest))
            print(f"  {e['period']}  {size/1024:.0f} KB")
            ok += 1
            downloaded_this_run += 1
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
