#!/usr/bin/env python3
"""Download every entry in the Navi portfolio-disclosure manifest to
cache/navi/xlsx/<period>/<scheme-slug>.xlsx. One file per scheme per month
from ~2021-09 onward (post-"Navi"-rebrand era); one file per MONTH (many
sheets inside, pre-rebrand "Essel Mutual Fund" era) for 2019-01..2021-08 —
those single-workbook months are still downloaded (to
cache/navi/xlsx/<period>/_workbook.xlsx) so nothing in the manifest is
silently dropped, but parse_navi_xlsx.py does not parse them (different,
older schema — see discover_navi_xlsx.py's docstring).

Resume-if-exists, same as download_hdfc_xlsx.py — re-running after a
partial/interrupted run must not re-download anything already on disk.
--limit N caps how many NEW files this run downloads.
"""
import json
import re
import sys
import time
from pathlib import Path

from http_util_navi import download_file

ROOT = Path(__file__).parent
MANIFEST = ROOT / "cache" / "navi" / "xlsx_manifest.json"
XLSX_DIR = ROOT / "cache" / "navi" / "xlsx"

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
        # Single-workbook-era manifest entries all share scheme_name derived from
        # the same monthly title (no per-scheme split possible pre-download) —
        # slug collapses to one fixed name so there's exactly one file per period.
        file_slug = slug(e["scheme_name"]) or "workbook"
        ext = ".xlsb" if e["url"].lower().endswith(".xlsb") else ".xlsx"
        dest = period_dir / f"{file_slug}{ext}"
        if dest.exists() and dest.stat().st_size > 3_000:
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
