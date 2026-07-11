#!/usr/bin/env python3
"""Download every XLSX in the Mirae portfolio-disclosure manifest to
cache/mirae/xlsx/<period>/<scheme-slug>.xlsx. Resumable: a destination that
already exists above a minimum size is skipped, same convention as
download_ppfas_xlsx.py/download_hdfc_xlsx.py.

Combined-workbook-era entries (scheme_name is None — see
discover_mirae_xlsx.py's docstring) are saved as <period>/combined.xlsx —
there's exactly one per period so no collision risk.
"""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from http_util_mirae import download_file

ROOT = Path(__file__).parent
MANIFEST = ROOT / "cache" / "mirae" / "xlsx_manifest.json"
XLSX_DIR = ROOT / "cache" / "mirae" / "xlsx"

SLUG_RE = re.compile(r"[^a-z0-9]+")
WORKERS = 12  # each a separate curl subprocess; site has shown no rate-limiting so far


def slugify(name: str) -> str:
    s = SLUG_RE.sub("-", name.lower()).strip("-")
    return s or "scheme"


def _fetch_one(e):
    period_dir = XLSX_DIR / e["period"]
    period_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify(e["scheme_name"]) if e["scheme_name"] else "combined"
    dest = period_dir / f"{slug}.xlsx"
    label = f"{e['period']}/{slug}"
    if dest.exists() and dest.stat().st_size > 5_000:
        return ("skipped", label, None)
    try:
        size = download_file(e["url"], str(dest))
        return ("ok", label, size)
    except Exception as ex:
        return ("failed", label, str(ex))


def main():
    only_periods = set(sys.argv[1:]) or None
    entries = json.loads(MANIFEST.read_text())
    if only_periods:
        entries = [e for e in entries if e["period"] in only_periods]

    ok, skipped, failed = 0, 0, []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(_fetch_one, e) for e in entries]
        for i, fut in enumerate(as_completed(futures)):
            status, label, info = fut.result()
            if status == "skipped":
                skipped += 1
            elif status == "ok":
                ok += 1
                if ok % 25 == 0:
                    print(f"  [{i+1}/{len(entries)}] {label}  {info/1024:.0f} KB")
            else:
                failed.append(label)
                print(f"  {label}  FAILED: {info}")

    print(f"\nDownloaded {ok}, already cached {skipped}, failed {len(failed)}")
    if failed:
        print("Failed:", failed[:30], "..." if len(failed) > 30 else "")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
