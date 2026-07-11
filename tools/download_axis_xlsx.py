#!/usr/bin/env python3
"""Download every entry in the Axis portfolio-disclosure manifest to
cache/axis/xlsx/<period>/<scheme-slug>.xlsx. One file per scheme per month
(same shape as HDFC's manifest, unlike PPFAS's one-workbook-per-month) — with
100+ schemes across many months this is a LOT of files, so resume-if-exists is
load-bearing, not optional: re-running after a partial/interrupted run must
not re-download anything already on disk.

Unlike discover_axis_xlsx.py's API step (blocked for plain curl by Akamai's
TLS fingerprinting, see that file's docstring), the actual FILE download
(from www.axismf.com/1/5/.../*.xls, a static asset path) is confirmed working
fine over plain curl with just a UA header — no bot-mitigation gate on the
file host itself, only on the /cms/get-scheme-documents API used to discover
the URLs.

Files are saved with their original .xls extension even though some are true
legacy BIFF8/OLE2 (confirmed by direct inspection: "Composite Document File
V2 Document" signature) — same as PPFAS/HDFC's occasional legacy-.xls
exception, see parse_axis_xlsx.py.

--limit N caps how many NEW files this run downloads (existing-on-disk files
don't count against it), so a big backfill can be chunked across runs.
"""
import json
import re
import sys
import time
from pathlib import Path

from http_util import download_file

ROOT = Path(__file__).parent
MANIFEST = ROOT / "cache" / "axis" / "xlsx_manifest.json"
XLSX_DIR = ROOT / "cache" / "axis" / "xlsx"

SLUG_RE = re.compile(r"[^a-z0-9]+")


def slug(name: str) -> str:
    return SLUG_RE.sub("-", name.lower()).strip("-")


def main():
    limit = None
    for arg in sys.argv[1:]:
        if arg.startswith("--limit="):
            limit = int(arg.split("=", 1)[1])

    if not MANIFEST.exists():
        print(f"No manifest at {MANIFEST} — run discover_axis_xlsx.py first.")
        return 1

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
            time.sleep(0.15)
        except Exception as ex:
            print(f"  {e['period']}  {e['scheme_name']}  FAILED: {ex}")
            failed.append((e["period"], e["scheme_name"]))

    print(f"\nDownloaded {ok}, already cached {skipped}, failed {len(failed)}")
    if failed:
        print("Failed:", failed[:30], "..." if len(failed) > 30 else "")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
