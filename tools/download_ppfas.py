#!/usr/bin/env python3
"""Download every PDF in the PPFAS manifest to cache/ppfas/pdf/<period>.pdf."""
import json
import sys
import time
from pathlib import Path

from http_util import download_file

ROOT = Path(__file__).parent
MANIFEST = ROOT / "cache" / "ppfas" / "manifest.json"
PDF_DIR = ROOT / "cache" / "ppfas" / "pdf"


def main():
    entries = json.loads(MANIFEST.read_text())
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    ok, skipped, failed = 0, 0, []
    for e in entries:
        dest = PDF_DIR / f"{e['period']}.pdf"
        if dest.exists() and dest.stat().st_size > 10_000:
            skipped += 1
            continue
        try:
            size = download_file(e["url"], str(dest))
            print(f"  {e['period']}  {size/1024:.0f} KB  <- {e['url']}")
            ok += 1
            time.sleep(0.3)  # be polite to the AMC's server
        except Exception as ex:
            print(f"  {e['period']}  FAILED: {ex}")
            failed.append(e["period"])
    print(f"\nDownloaded {ok}, already cached {skipped}, failed {len(failed)}")
    if failed:
        print("Failed periods:", failed)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
