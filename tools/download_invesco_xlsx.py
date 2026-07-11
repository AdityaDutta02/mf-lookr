#!/usr/bin/env python3
"""Download every entry in the Invesco portfolio-disclosure manifest to
cache/invesco/xlsx/<period>/<scheme-slug>.xlsx. One file per scheme per
month (same shape as HDFC's archive — see download_hdfc_xlsx.py) — resume-
if-exists is load-bearing, not optional: re-running after a partial/
interrupted run must not re-download anything already on disk.

--limit N caps how many NEW files this run downloads (existing-on-disk files
don't count against it), so a big backfill can be chunked across runs.
"""
import json
import re
import sys
from pathlib import Path

from http_util_invesco import download_file

ROOT = Path(__file__).parent
MANIFEST = ROOT / "cache" / "invesco" / "xlsx_manifest.json"
XLSX_DIR = ROOT / "cache" / "invesco" / "xlsx"

SLUG_RE = re.compile(r"[^a-z0-9]+")


def slug(name: str) -> str:
    return SLUG_RE.sub("-", name.lower()).strip("-")


def main():
    limit = None
    for arg in sys.argv[1:]:
        if arg.startswith("--limit="):
            limit = int(arg.split("=", 1)[1])

    entries = json.loads(MANIFEST.read_text())
    ok, skipped, failed = 0, 0, []
    downloaded_this_run = 0

    for e in entries:
        if limit is not None and downloaded_this_run >= limit:
            print(f"\nHit --limit={limit}, stopping (resume by re-running).")
            break
        period_dir = XLSX_DIR / e["period"]
        dest = period_dir / f"{slug(e['scheme_name'])}.xlsx"
        if dest.exists() and dest.stat().st_size > 5_000:
            skipped += 1
            continue
        period_dir.mkdir(parents=True, exist_ok=True)
        try:
            size = download_file(e["url"], str(dest))
            print(f"  {e['period']}  {e['scheme_name']}  {size/1024:.0f} KB")
            ok += 1
            downloaded_this_run += 1
        except Exception as ex:
            print(f"  {e['period']}  {e['scheme_name']}  FAILED: {ex}")
            failed.append((e["period"], e["scheme_name"]))

    print(f"\nDownloaded {ok}, already cached {skipped}, failed {len(failed)}")
    if failed:
        print("Failed:", failed[:30], "..." if len(failed) > 30 else "")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
