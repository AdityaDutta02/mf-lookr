#!/usr/bin/env python3
"""Download every entry in the SBI portfolio-disclosure manifest to
cache/sbi/xlsx/<period>/<scheme-slug>.xlsx. One file per scheme per month
(~120-140 schemes across 90 months = 11k+ files), same shape as HDFC's
download step — resume-if-exists is load-bearing here too.

--limit N caps how many NEW files this run downloads (existing-on-disk files
don't count against it), same chunking affordance as download_hdfc_xlsx.py.
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from http_util_sbi import download_file

ROOT = Path(__file__).parent
MANIFEST = ROOT / "cache" / "sbi" / "xlsx_manifest.json"
XLSX_DIR = ROOT / "cache" / "sbi" / "xlsx"

# SBI's site showed no rate-limiting/bot-protection during discovery (confirmed by
# direct testing — plain UA is enough, see http_util_sbi.py's docstring), and each
# curl call is its own OS process/socket, so a modest thread pool is safe here — with
# 11k+ files a purely sequential download (as PPFAS/HDFC's smaller archives use) would
# take hours. Kept conservative (8 workers) to stay a good citizen of a public site.
MAX_WORKERS = 8


def _download_one(e: dict):
    period_dir = XLSX_DIR / e["period"]
    dest = period_dir / f"{e['scheme_slug']}.xlsx"
    if dest.exists() and dest.stat().st_size > 2_000:
        return ("skipped", e, None)
    period_dir.mkdir(parents=True, exist_ok=True)
    try:
        size = download_file(e["url"], str(dest))
        return ("ok", e, size)
    except Exception as ex:
        return ("failed", e, str(ex))


def main():
    limit = None
    for arg in sys.argv[1:]:
        if arg.startswith("--limit="):
            limit = int(arg.split("=", 1)[1])

    entries = json.loads(MANIFEST.read_text())
    # Full historical depth (2019+) is nice-to-have; recent months are the load-bearing
    # bar. Newest-period-first so a time-boxed/limited run always covers the most
    # recent months before spending budget on older backfill — pure download order,
    # doesn't affect final on-disk completeness either way.
    entries = sorted(entries, key=lambda e: e["period"], reverse=True)
    if limit is not None:
        # Only NEW (not-yet-on-disk) entries count against --limit, so filter first —
        # otherwise a re-run would burn its whole budget re-skipping cached files.
        def on_disk(e):
            return (XLSX_DIR / e["period"] / f"{e['scheme_slug']}.xlsx").exists()
        already_done = [e for e in entries if on_disk(e)]
        pending = [e for e in entries if not on_disk(e)]
        entries = already_done + pending[:limit]

    ok, skipped, failed = 0, 0, []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [pool.submit(_download_one, e) for e in entries]
        for i, fut in enumerate(as_completed(futures), start=1):
            status, e, info = fut.result()
            if status == "skipped":
                skipped += 1
            elif status == "ok":
                ok += 1
                print(f"  {e['period']}  {e['title']}  {info/1024:.0f} KB")
            else:
                failed.append((e["period"], e["title"]))
                print(f"  {e['period']}  {e['title']}  FAILED: {info}")
            if i % 200 == 0:
                print(f"... {i}/{len(entries)} processed (ok={ok} skipped={skipped} failed={len(failed)})")

    print(f"\nDownloaded {ok}, already cached {skipped}, failed {len(failed)}")
    if failed:
        print("Failed:", failed[:30], "..." if len(failed) > 30 else "")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
